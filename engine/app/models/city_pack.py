"""City Pack schema (v1).

A City Pack is the entire per-city configuration for the Tebaki engine:
metadata, boundary, admin levels, complaint channels, regulations, SLA
clocks, and the pitch stat. Everything city-specific is data; the engine
is code. Any city is a pull request.
"""

import re
from typing import Any, Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL_RE = re.compile(r"^https?://")


def _check_email(v: str) -> str:
    if not _EMAIL_RE.match(v):
        raise ValueError(f"invalid email address: {v!r}")
    return v


def _check_url(v: str) -> str:
    if not _URL_RE.match(v):
        raise ValueError(f"must be an http(s) URL, got {v!r}")
    return v


class CityMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    local_name: str = Field(min_length=1)
    languages: list[str] = Field(min_length=1)
    timezone: str
    locale: str = Field(min_length=1)

    @field_validator("languages")
    @classmethod
    def _languages(cls, v: list[str]) -> list[str]:
        for lang in v:
            if not re.fullmatch(r"[a-z]{2,3}", lang):
                raise ValueError(f"invalid ISO language code: {lang!r}")
        return v

    @field_validator("timezone")
    @classmethod
    def _timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError(f"invalid IANA timezone: {v!r}")
        return v


class Boundary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geojson: str = Field(min_length=1)
    note: str | None = None


class AdminLevel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: str = Field(min_length=1)
    source: Literal["geojson", "none"] = "geojson"


class EmailChannel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str = Field(min_length=1)
    address: str
    lang: str = "en"

    @field_validator("address")
    @classmethod
    def _address(cls, v: str) -> str:
        return _check_email(v)


class BrowserFormMap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str = Field(min_length=1)
    description: str = Field(min_length=1)
    location: str = Field(min_length=1)
    photo: str | None = None
    submit: str = Field(min_length=1)


class BrowserChannel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    form_map: BrowserFormMap

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        return _check_url(v)


class ApiChannel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["open311"]
    endpoint: str
    jurisdiction_id: str | None = None
    api_key_env: str | None = None
    service_code_map: dict[str, str] | None = None
    note: str | None = None

    @field_validator("endpoint")
    @classmethod
    def _endpoint(cls, v: str) -> str:
        return _check_url(v)


class EscalationLevel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: str = Field(min_length=1)
    target: str = Field(min_length=1)
    email: str | None = None
    lang: str | None = None
    after_days: int = Field(gt=0)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        return _check_email(v) if v else v


class Regulation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cite: str = Field(min_length=1)
    doc: str | None = None


class SLA(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acknowledge_days: int = Field(gt=0)
    resolve_days: int = Field(gt=0)

    @model_validator(mode="after")
    def _ordering(self) -> Self:
        if self.resolve_days < self.acknowledge_days:
            raise ValueError("resolve_days must be >= acknowledge_days")
        return self


class Pitch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: str = Field(min_length=1)
    source: str = Field(min_length=1)


class Coverage(BaseModel):
    """What geographic and delivery coverage is actually verified."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["verified", "city_fallback", "simulated"] = "verified"
    pilot_area: str | None = None
    boundary_source: str | None = None
    boundary_verified_at: str | None = None
    contact_source: str | None = None
    contact_verified_at: str | None = None


class Channels(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: list[EmailChannel] = Field(default_factory=list)
    browser: BrowserChannel | None = None
    api: ApiChannel | None = None
    escalation: list[EscalationLevel] = Field(min_length=1)

    @model_validator(mode="after")
    def _at_least_one_filing_channel(self) -> Self:
        if not self.email and not self.browser and not self.api:
            raise ValueError("at least one filing channel required: email, browser, or api")
        return self

    @model_validator(mode="after")
    def _escalation_ascending(self) -> Self:
        days = [e.after_days for e in self.escalation]
        if days != sorted(days):
            raise ValueError(f"escalation after_days must be ascending, got {days}")
        return self


class CityPack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: CityMeta
    boundary: Boundary
    admin: list[AdminLevel] = Field(min_length=1)
    channels: Channels
    regulations: list[Regulation] = Field(default_factory=list)
    sla: SLA
    pitch: Pitch
    coverage: Coverage = Field(default_factory=Coverage)

    @model_validator(mode="after")
    def _langs_consistent(self) -> Self:
        langs = set(self.city.languages)
        for channel in self.channels.email:
            if channel.lang not in langs:
                raise ValueError(f"email channel lang {channel.lang!r} not in city languages {sorted(langs)}")
        for level in self.channels.escalation:
            if level.lang and level.lang not in langs:
                raise ValueError(f"escalation lang {level.lang!r} not in city languages {sorted(langs)}")
        return self


def city_pack_json_schema() -> dict[str, Any]:
    return CityPack.model_json_schema()
