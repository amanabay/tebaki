"""DynamoDB-backed run store (same surface as RunStore).

Single-table design (default table name: tebaki):
  pk: "<ENTITY>#<id>"     e.g. REPORT#R-1, COMPLAINT#C-1, CARD#D-1, RUN#RUN-1
  sk: "META"
  GSI gsi1: pk "entity" (REPORT|COMPLAINT|CARD|RUN), sk "<status>#<created_at>"

Hot queries (new reports, pending cards, active filings) use gsi1;
entity-wide listings use Scan (fine at hackathon scale). None and empty-
string values are dropped on write (DynamoDB restrictions); from_dict
defaults restore them on read.

Configuration:
  TEBAKI_STORE=dynamodb            selects this store
  TEBAKI_DDB_ENDPOINT=<url>        DynamoDB Local endpoint for dev/CI
  TEBAKI_DYNAMODB_TABLE=<name>     table name (default: tebaki)
"""

from __future__ import annotations

import os
from typing import Any

import boto3
import botocore

from app.store import (
    AgentRun,
    Complaint,
    DecisionCard,
    Report,
    RunStore,
    _now,
)

ENTITY_REPORT = "REPORT"
ENTITY_COMPLAINT = "COMPLAINT"
ENTITY_CARD = "CARD"
ENTITY_RUN = "RUN"


def _clean(value: Any) -> Any:
    """Normalize values for DynamoDB: drop None/empty strings, floats -> Decimal."""
    from decimal import Decimal

    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, (int, Decimal)):
        return value
    if isinstance(value, str):
        return value if value else None
    if isinstance(value, dict):
        return {k: v for k, v in ((k, _clean(v)) for k, v in value.items()) if v is not None}
    if isinstance(value, list):
        return [v for v in (_clean(i) for i in value) if v is not None]
    return value


class DynamoDBStore(RunStore):
    """DynamoDB-backed implementation of the run-store interface.

    Note: unlike the in-memory store, fetched objects are copies — mutate
    then call the matching save_* method to persist.
    """

    def __init__(
        self,
        table_name: str | None = None,
        endpoint_url: str | None = None,
        region: str | None = None,
    ) -> None:
        self.table_name = table_name or os.getenv("TEBAKI_DYNAMODB_TABLE", "tebaki")
        self.endpoint_url = endpoint_url or os.getenv("TEBAKI_DDB_ENDPOINT") or None
        region = region or os.getenv("TEBAKI_AWS_REGION", "us-east-1")
        self._dynamodb = boto3.resource("dynamodb", region_name=region, endpoint_url=self.endpoint_url)
        self.table = self._dynamodb.Table(self.table_name)
        self._ensure_table()

    def _ensure_table(self) -> None:
        try:
            self.table.load()
            return
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
        self._dynamodb.create_table(
            TableName=self.table_name,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
                {"AttributeName": "entity", "AttributeType": "S"},
                {"AttributeName": "status_key", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "gsi1",
                    "KeySchema": [
                        {"AttributeName": "entity", "KeyType": "HASH"},
                        {"AttributeName": "status_key", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        self.table.wait_until_exists()

    # --- item helpers -----------------------------------------------------------

    def _put(self, entity: str, object_id: str, data: dict[str, Any]) -> None:
        item = _clean({"pk": f"{entity}#{object_id}", "sk": "META", "entity": entity, **data})
        self.table.put_item(Item=item)

    def _get_item(self, entity: str, object_id: str) -> dict[str, Any] | None:
        resp = self.table.get_item(Key={"pk": f"{entity}#{object_id}", "sk": "META"})
        return resp.get("Item")

    def _query_by_status(self, entity: str, status_prefixes: tuple[str, ...]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for prefix in status_prefixes:
            kwargs: dict[str, Any] = {
                "IndexName": "gsi1",
                "KeyConditionExpression": boto3.dynamodb.conditions.Key("entity").eq(entity)
                & boto3.dynamodb.conditions.Key("status_key").begins_with(prefix),
            }
            resp = self.table.query(**kwargs)
            items.extend(resp.get("Items", []))
            while "LastEvaluatedKey" in resp:
                kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
                resp = self.table.query(**kwargs)
                items.extend(resp.get("Items", []))
        return items

    def _scan_entity(self, entity: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {"FilterExpression": boto3.dynamodb.conditions.Attr("entity").eq(entity)}
        resp = self.table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        while "LastEvaluatedKey" in resp:
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
            resp = self.table.scan(**kwargs)
            items.extend(resp.get("Items", []))
        return items

    # --- reports ------------------------------------------------------------------

    def add_report(self, report: Report) -> Report:
        self._put(ENTITY_REPORT, report.report_id, self._report_item(report))
        return report

    def save_report(self, report: Report) -> None:
        self._put(ENTITY_REPORT, report.report_id, self._report_item(report))

    @staticmethod
    def _report_item(report: Report) -> dict[str, Any]:
        data = report.to_dict()
        data["status_key"] = f"{report.status}#{report.created_at}"
        return data

    def get_report(self, report_id: str) -> Report | None:
        item = self._get_item(ENTITY_REPORT, report_id)
        return Report.from_dict(_num(item)) if item else None

    def list_reports(self) -> list[Report]:
        return [Report.from_dict(_num(i)) for i in self._scan_entity(ENTITY_REPORT)]

    def new_reports(self) -> list[Report]:
        return [Report.from_dict(_num(i)) for i in self._query_by_status(ENTITY_REPORT, ("new#",))]

    def update_report_status(self, report_id: str, status: str) -> None:
        report = self.get_report(report_id)
        if report is None:
            raise KeyError(f"unknown report {report_id}")
        report.status = status
        self.save_report(report)

    # --- complaints -----------------------------------------------------------------

    def add_complaint(self, complaint: Complaint) -> Complaint:
        self._put(ENTITY_COMPLAINT, complaint.complaint_id, self._complaint_item(complaint))
        return complaint

    def save_complaint(self, complaint: Complaint) -> None:
        self._put(ENTITY_COMPLAINT, complaint.complaint_id, self._complaint_item(complaint))

    @staticmethod
    def _complaint_item(complaint: Complaint) -> dict[str, Any]:
        data = complaint.to_dict()
        data["status_key"] = f"{complaint.status}#{complaint.created_at}"
        return data

    def get_complaint(self, complaint_id: str) -> Complaint | None:
        item = self._get_item(ENTITY_COMPLAINT, complaint_id)
        return Complaint.from_dict(_num(item)) if item else None

    def list_complaints(self) -> list[Complaint]:
        return [Complaint.from_dict(_num(i)) for i in self._scan_entity(ENTITY_COMPLAINT)]

    def filed_complaints(self) -> list[Complaint]:
        items = self._query_by_status(ENTITY_COMPLAINT, ("filed#", "escalated_"))
        return [c for c in (Complaint.from_dict(_num(i)) for i in items) if c.ticket_id]

    # --- decision cards ----------------------------------------------------------------

    def add_decision_card(self, card: DecisionCard) -> DecisionCard:
        self._put(ENTITY_CARD, card.card_id, self._card_item(card))
        return card

    def save_card(self, card: DecisionCard) -> None:
        self._put(ENTITY_CARD, card.card_id, self._card_item(card))

    @staticmethod
    def _card_item(card: DecisionCard) -> dict[str, Any]:
        data = card.to_dict()
        data["status_key"] = f"{card.status}#{card.created_at}"
        return data

    def get_card(self, card_id: str) -> DecisionCard | None:
        item = self._get_item(ENTITY_CARD, card_id)
        return DecisionCard.from_dict(item) if item else None

    def list_cards(self) -> list[DecisionCard]:
        return [DecisionCard.from_dict(i) for i in self._scan_entity(ENTITY_CARD)]

    def pending_cards(self) -> list[DecisionCard]:
        return [DecisionCard.from_dict(i) for i in self._query_by_status(ENTITY_CARD, ("pending#",))]

    def resolve_card(self, card_id: str, resolution: str, response: dict[str, Any] | None = None) -> DecisionCard:
        card = self.get_card(card_id)
        if card is None:
            raise ValueError(f"unknown decision card {card_id!r}")
        if card.status != "pending":
            raise ValueError(f"card {card_id} already resolved ({card.status})")
        if resolution not in {"approved", "edited", "dropped"}:
            raise ValueError(f"invalid resolution {resolution!r}: approved|edited|dropped")
        card.status = resolution
        card.response = response
        self.save_card(card)
        return card

    # --- agent runs -----------------------------------------------------------------------

    def start_run(self, city: str) -> AgentRun:
        run = AgentRun(city)
        self._put(ENTITY_RUN, run.run_id, self._run_item(run))
        return run

    @staticmethod
    def _run_item(run: AgentRun) -> dict[str, Any]:
        data = run.to_dict()
        data["status_key"] = f"{'done' if run.finished_at else 'open'}#{run.started_at}"
        return data

    def get_run(self, run_id: str) -> AgentRun | None:
        item = self._get_item(ENTITY_RUN, run_id)
        return AgentRun.from_dict(item) if item else None

    def list_runs(self) -> list[AgentRun]:
        return [AgentRun.from_dict(i) for i in self._scan_entity(ENTITY_RUN)]

    def save_run(self, run: AgentRun) -> None:
        self._put(ENTITY_RUN, run.run_id, self._run_item(run))

    def finish_run(self, run: AgentRun) -> None:
        run.finished_at = _now()
        self._put(ENTITY_RUN, run.run_id, self._run_item(run))


def _num(item: dict[str, Any]) -> dict[str, Any]:
    """Convert DynamoDB Decimals back to int/float for from_dict constructors."""
    from decimal import Decimal

    def conv(v: Any) -> Any:
        if isinstance(v, Decimal):
            return float(v) if v != v.to_integral_value() else int(v)
        if isinstance(v, dict):
            return {k: conv(x) for k, x in v.items()}
        if isinstance(v, list):
            return [conv(x) for x in v]
        return v

    return {k: conv(v) for k, v in item.items()}
