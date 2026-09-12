"""Build and deploy the Tebaki engine to Bedrock AgentCore Runtime.

Usage (from repo root, with AWS credentials live):
    .venv/bin/python infra/deploy_agentcore.py

Steps:
  1. docker build the engine image (infra/Dockerfile)
  2. create (or reuse) an ECR repo, push the image
  3. create (or update) the AgentCore Runtime with the image URI
  4. print the runtime's network session endpoint for API invocation

Idempotent: safe to re-run; reuses existing repo + runtime by name.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

REGION = "us-east-1"
RUNTIME_NAME = "tebaki-engine"
ECR_REPO = "tebaki-engine"
IMAGE_TAG = "latest"
ACCOUNT_ID = None  # resolved at runtime

AWS = "aws"


def sh(cmd: list[str], **kwargs) -> str:
    """Run a command, bail on failure with output shown."""
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        print(f"command failed: {' '.join(cmd)}", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(1)
    return result.stdout.strip()


def aws_json(*args: str) -> dict:
    out = sh([AWS, *args, "--region", REGION, "--output", "json"])
    return json.loads(out) if out else {}


def get_account_id() -> str:
    return aws_json("sts", "get-caller-identity")["Account"]


def build_image() -> None:
    print("[1/4] building engine image (this can take a few minutes)…")
    sh([
        "docker", "buildx", "build", "--platform", "linux/arm64", "--load",
        "-f", "infra/Dockerfile", "-t", "tebaki-engine:local", ".",
    ])
    print("      image built")


def ensure_repo_and_push(account_id: str) -> str:
    print("[2/4] pushing image to ECR…")
    try:
        aws_json("ecr", "describe-repositories", "--repository-names", ECR_REPO)
        print("      reusing ECR repo")
    except SystemExit:
        # describe-repositories failed -> repo doesn't exist
        global AWS
        result = subprocess.run(
            [AWS, "ecr", "create-repository",
             "--repository-name", ECR_REPO,
             "--region", REGION,
             "--image-scanning-configuration", "scanOnPush=false",
             "--output", "json"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            raise SystemExit(1)
        print("      created ECR repo")

    auth = sh([AWS, "ecr", "get-login-password", "--region", REGION])
    registry = f"{account_id}.dkr.ecr.{REGION}.amazonaws.com"
    sh(["docker", "login", "-u", "AWS", "--password-stdin", registry], input=auth)
    image_uri = f"{registry}/{ECR_REPO}:{IMAGE_TAG}"
    sh(["docker", "tag", "tebaki-engine:local", image_uri])
    sh(["docker", "push", image_uri])
    print(f"      pushed {image_uri}")
    return image_uri


def ensure_runtime(image_uri: str, role_arn: str) -> str:
    print("[3/4] ensuring AgentCore Runtime…")
    import boto3

    client = boto3.client("bedrock-agentcore-control", region_name=REGION)
    existing = None
    try:
        resp = client.list_agent_runtimes()
        for rt in resp.get("agentRuntimes", []):
            if rt.get("agentRuntimeName") == RUNTIME_NAME:
                existing = rt
                break
    except Exception as e:  # noqa: BLE001
        print(f"      list_runtimes failed: {e}", file=sys.stderr)

    if existing:
        runtime_id = existing["agentRuntimeId"]
        print(f"      runtime exists: {runtime_id}")
        try:
            client.update_agent_runtime(
                agentRuntimeId=runtime_id,
                agentRuntimeArtifact={"containerConfiguration": {"containerUri": image_uri}},
                roleArn=role_arn,
                protocolConfiguration={"serverProtocol": "HTTP"},
                environmentVariables={
                    "TEBAKI_CITY_PACK": "addis",
                    "TEBAKI_AWS_REGION": REGION,
                    "TEBAKI_LIVE_BEDROCK": "1",
                },
            )
            print("      runtime updated")
        except Exception as e:  # noqa: BLE001
            print(f"      update_runtime skipped: {e}")
        return runtime_id

    resp = client.create_agent_runtime(
        agentRuntimeName=RUNTIME_NAME,
        agentRuntimeArtifact={"containerConfiguration": {"containerUri": image_uri}},
        roleArn=role_arn,
        protocolConfiguration={"serverProtocol": "HTTP"},
        environmentVariables={
            "TEBAKI_CITY_PACK": "addis",
            "TEBAKI_AWS_REGION": REGION,
            "TEBAKI_LIVE_BEDROCK": "1",
        },
    )
    runtime_id = resp["agentRuntimeId"]
    print(f"      runtime created: {runtime_id}")

    # wait for READY
    for _ in range(60):
        status = client.get_agent_runtime(agentRuntimeId=runtime_id)["status"]
        print(f"      status: {status}")
        if status == "READY":
            break
        if status in ("FAILED", "DELETE_FAILED"):
            raise SystemExit(f"runtime entered {status}")
        time.sleep(10)
    return runtime_id


def print_invocation(runtime_id: str, account_id: str) -> None:
    print("[4/4] invocation info")
    endpoint = (
        f"https://{runtime_id}.{REGION}.bedrock-agentcore.{REGION}.amazonaws.com/"
    )
    print(f"""
Runtime: {runtime_id}
Invoke:  aws bedrock-agentcore invoke-runtime \\
           --runtime-identifier {runtime_id} \\
           --region {REGION} \\
           --payload '<json>'

Or via SDK:
    from bedrock_agentcore.runtime import BedrockAgentCoreClient
    client = BedrockAgentCoreClient(runtime_identifier="{runtime_id}", region_name="{REGION}")

Account: {account_id}
""")


def ensure_role(account_id: str) -> str:
    role_name = "TebakiAgentCoreRuntimeRole"
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
    trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": ["sts:AssumeRole", "sts:TagSession"],
            }
        ],
    }
    try:
        aws_json("iam", "get-role", "--role-name", role_name)
        print("      reusing IAM role")
    except SystemExit:
        result = subprocess.run(
            [AWS, "iam", "create-role",
             "--role-name", role_name,
             "--assume-role-policy-document", json.dumps(trust),
             "--output", "json"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            raise SystemExit(1)
        print("      created IAM role")

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BedrockInference",
                "Effect": "Allow",
                "Action": ["bedrock:InvokeModel*", "bedrock:Converse*"],
                "Resource": ["*"],
            },
            {
                "Sid": "DynamoDB",
                "Effect": "Allow",
                "Action": ["dynamodb:*"],
                "Resource": [
                    f"arn:aws:dynamodb:{REGION}:{account_id}:table/tebaki",
                    f"arn:aws:dynamodb:{REGION}:{account_id}:table/tebaki/*",
                ],
            },
            {
                "Sid": "SES",
                "Effect": "Allow",
                "Action": ["ses:SendEmail", "ses:SendRawEmail"],
                "Resource": ["*"],
            },
            {
                "Sid": "CloudWatch",
                "Effect": "Allow",
                "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": ["*"],
            },
        ],
    }
    policy_name = f"{role_name}-Policy"
    try:
        aws_json("iam", "get-policy", "--policy-arn", f"arn:aws:iam::{account_id}:policy/{policy_name}")
    except SystemExit:
        result = subprocess.run(
            [AWS, "iam", "create-policy",
             "--policy-name", policy_name,
             "--policy-document", json.dumps(policy),
             "--output", "json"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            raise SystemExit(1)
    sh([AWS, "iam", "attach-role-policy",
        "--role-name", role_name,
        "--policy-arn", f"arn:aws:iam::{account_id}:policy/{policy_name}"])
    return role_arn


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    import os

    os.chdir(repo_root)
    account_id = get_account_id()
    build_image()
    image_uri = ensure_repo_and_push(account_id)
    role_arn = ensure_role(account_id)
    runtime_id = ensure_runtime(image_uri, role_arn)
    print_invocation(runtime_id, account_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
