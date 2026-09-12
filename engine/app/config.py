from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Engine configuration. AWS-side config; local dev defaults to sandbox pack."""

    model_config = SettingsConfigDict(
        env_prefix="TEBAKI_", env_file=".env", extra="ignore"
    )

    # City pack selection
    city_pack: str = Field(default="addis", description="Name of city pack under cities/")
    cities_dir: Path = Field(default=_REPO_ROOT / "cities")

    # AWS / Bedrock
    aws_region: str = "us-east-1"
    # Nova Lite is the cost-conscious live model used for testing. It supports
    # the reliable tool-calling needed by the multi-agent filing workflow.
    # Override with TEBAKI_BEDROCK_MODEL_ID for Nova Micro or Nova Pro.
    bedrock_model_id: str = "amazon.nova-lite-v1:0"

    # Intake / API
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # Storage (local dev: dynamodb-local via LocalStack; prod: real)
    dynamodb_table: str = "tebaki"

    # Run schedule
    nightly_cron: str = "0 2 * * *"  # 02:00 in city timezone


settings = Settings()
