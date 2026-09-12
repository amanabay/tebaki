"""Configuration invariants that must hold from any launch directory."""

from __future__ import annotations

from pathlib import Path

from app.config import Settings


def test_env_file_is_absolute_and_repo_stable(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    env_file = Path(Settings.model_config["env_file"])

    assert env_file.is_absolute()
    assert env_file.name == ".env"
    assert env_file.parent.name == "engine"
