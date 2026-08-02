"""Settings and YAML loading.

Precedence, low to high: code defaults < `config/*.yaml` < `APEXFIN_*` env
vars < CLI flags (CLI_CONTRACT 一).

Secrets never live in YAML. A key that looks like a credential makes startup
fail with exit code 3 rather than being read and used, because the failure
mode we are guarding against is a committed API key, and a working program is
exactly what stops anyone from noticing.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from apexfin.core.errors import ConfigError

_SECRET_KEY_PATTERN = re.compile(r"(_key|_token|_secret|password|passwd)$", re.IGNORECASE)


class Settings(BaseSettings):
    """Runtime settings. Env prefix `APEXFIN_`."""

    model_config = SettingsConfigDict(env_prefix="APEXFIN_", extra="ignore")

    db: Path = Field(default=Path("data/apexfin.db"))
    config_dir: Path = Field(default=Path("config"))
    dist_dir: Path = Field(default=Path("dist"))
    log_level: str = Field(default="info")
    fred_api_key: str | None = Field(default=None)

    def resolved(self, root: Path) -> Settings:
        """Anchor relative paths to a project root."""
        return self.model_copy(
            update={
                "db": root / self.db if not self.db.is_absolute() else self.db,
                "config_dir": (
                    root / self.config_dir if not self.config_dir.is_absolute() else self.config_dir
                ),
                "dist_dir": (
                    root / self.dist_dir if not self.dist_dir.is_absolute() else self.dist_dir
                ),
            }
        )


def assert_no_secrets(data: Any, origin: Path, path: str = "") -> None:
    """Reject credential-shaped keys anywhere in a config tree."""
    if isinstance(data, dict):
        for key, value in data.items():
            where = f"{path}.{key}" if path else str(key)
            if isinstance(key, str) and _SECRET_KEY_PATTERN.search(key):
                raise ConfigError(
                    f"{origin}: key '{where}' looks like a credential. "
                    "Secrets must come from environment variables only "
                    "(for example APEXFIN_FRED_API_KEY), never from YAML."
                )
            assert_no_secrets(value, origin, where)
    elif isinstance(data, list):
        for index, item in enumerate(data):
            assert_no_secrets(item, origin, f"{path}[{index}]")


def load_yaml(path: Path) -> dict[str, Any]:
    """Load one YAML config file with the secret guard applied."""
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from exc
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: expected a mapping at the top level, got {type(raw).__name__}")
    assert_no_secrets(raw, path)
    return raw


def find_project_root(start: Path | None = None) -> Path:
    """Walk up until a directory holding `pyproject.toml` is found."""
    cursor = (start or Path.cwd()).resolve()
    for candidate in (cursor, *cursor.parents):
        if (candidate / "pyproject.toml").exists():
            return candidate
    return cursor
