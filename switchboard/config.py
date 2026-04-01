"""Environment-backed settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    manifest_dir: Path = ROOT_DIR / "switchboard" / "manifests"
    evidence_dir: Path = ROOT_DIR / "docs" / "evidence"
    archive_dir: Path = ROOT_DIR / "docs" / "evidence" / "archive"
    private_state_dir: Path = ROOT_DIR / "state" / "private"
    downloads_dir: Path = ROOT_DIR / "downloads"
    max_files_per_path: int = 200
    ssh_timeout_seconds: int = 10

    model_config = SettingsConfigDict(
        env_prefix="SWITCHBOARD_",
        env_file=(".env.local", ".env"),
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
