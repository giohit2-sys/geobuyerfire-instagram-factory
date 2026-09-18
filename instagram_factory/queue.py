from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


def load_queue(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_queue(path: Path, posts: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def due_posts(posts: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    due = []
    for post in posts:
        if post.get("status") != "ready":
            continue
        scheduled = datetime.fromisoformat(post["scheduled_at"])
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=now.tzinfo)
        if scheduled <= now:
            due.append(post)
    return sorted(due, key=lambda item: item["scheduled_at"])
