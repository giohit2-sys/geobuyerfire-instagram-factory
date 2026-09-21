from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from zoneinfo import ZoneInfo


def load_env(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    access_token: str = field(default_factory=lambda: os.getenv("INSTAGRAM_ACCESS_TOKEN", ""))
    user_id: str = field(default_factory=lambda: os.getenv("INSTAGRAM_USER_ID", ""))
    api_version: str = field(default_factory=lambda: os.getenv("INSTAGRAM_API_VERSION", "v24.0"))
    api_host: str = field(default_factory=lambda: os.getenv("INSTAGRAM_API_HOST", "https://graph.facebook.com"))
    asset_base_url: str = field(default_factory=lambda: os.getenv("PUBLIC_ASSET_BASE_URL", "").rstrip("/"))
    ai_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    ai_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    autopublish_enabled: bool = field(default_factory=lambda: _bool("AUTOPUBLISH_ENABLED", False))
    timezone_name: str = field(default_factory=lambda: os.getenv("TIMEZONE", "Europe/Moscow"))
    daily_carousel_target: int = field(default_factory=lambda: int(os.getenv("DAILY_CAROUSEL_TARGET", "1")))
    publish_hours: tuple[int, ...] = field(default_factory=lambda: tuple(
        int(x) for x in os.getenv("PUBLISH_HOURS", "19").split(",") if x.strip()
    ))
    max_consecutive_errors: int = field(default_factory=lambda: int(os.getenv("MAX_CONSECUTIVE_ERRORS", "3")))
    output_dir: Path = field(default_factory=lambda: Path(os.getenv("OUTPUT_DIR", "published")))
    queue_path: Path = field(default_factory=lambda: Path(os.getenv("QUEUE_PATH", "data/queue.json")))
    insights_path: Path = field(default_factory=lambda: Path(os.getenv("INSIGHTS_PATH", "data/insights.json")))

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    def require_publish(self) -> None:
        missing = []
        if not self.access_token:
            missing.append("INSTAGRAM_ACCESS_TOKEN")
        if not self.user_id:
            missing.append("INSTAGRAM_USER_ID")
        if not self.asset_base_url:
            missing.append("PUBLIC_ASSET_BASE_URL")
        if missing:
            raise RuntimeError("Missing publishing settings: " + ", ".join(missing))
