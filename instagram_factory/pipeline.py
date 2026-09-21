from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from .api import InstagramAPI, InstagramAPIError
from .config import Settings
from .editor import validate_post
from .queue import due_posts, load_queue, save_queue
from .renderer import render_carousel


class Pipeline:
    def __init__(self, settings: Settings):
        self.s = settings
        self.api = InstagramAPI(settings.access_token, settings.user_id,
                                settings.api_version, settings.api_host) if settings.access_token else None

    def render_ready(self) -> dict:
        posts = load_queue(self.s.queue_path)
        rendered = rejected = 0
        previous: list[str] = []
        for post in posts:
            if post.get("status") not in {"draft", "ready"}:
                continue
            if str(post.get("media_type") or "carousel").lower() == "reel":
                video_asset = Path(str(post.get("video_asset") or ""))
                if video_asset.as_posix() == "." or not video_asset.exists():
                    post["status"] = "needs_review"
                    post["review_reasons"] = ["missing_video_asset"]
                    rejected += 1
                else:
                    post["status"] = "ready"
                continue
            reasons = validate_post(post, previous)
            if reasons:
                post["status"] = "needs_review"
                post["review_reasons"] = reasons
                rejected += 1
                continue
            paths = render_carousel(post, self.s.output_dir)
            post["assets"] = [str(path) for path in paths]
            post["status"] = "ready"
            previous.append(" ".join(post["slides"]))
            rendered += 1
        save_queue(self.s.queue_path, posts)
        return {"rendered": rendered, "needs_review": rejected}

    def publish_due(self, force: bool = False) -> dict:
        if not self.s.autopublish_enabled and not force:
            return {"published": 0, "reason": "AUTOPUBLISH_ENABLED=false"}
        self.s.require_publish()
        assert self.api
        posts = load_queue(self.s.queue_path)
        now = datetime.now(self.s.timezone)
        candidates = due_posts(posts, now)
        if not candidates:
            return {"published": 0, "reason": "nothing_due"}
        post = candidates[0]

        # Meta exposes the account's actual rolling quota. At high frequency,
        # trust that live value instead of a hard-coded/documentation value.
        try:
            limit_payload = self.api.content_publishing_limit()
            rows = limit_payload.get("data") or []
            if rows:
                usage = int(rows[0].get("quota_usage", 0) or 0)
                config = rows[0].get("config") or {}
                total = int(config.get("quota_total", 0) or 0)
                if total and usage >= total:
                    return {
                        "published": 0,
                        "reason": "content_publishing_quota_reached",
                        "quota_usage": usage,
                        "quota_total": total,
                    }
        except InstagramAPIError as exc:
            # A missing quota permission must not blindly block an otherwise
            # valid publish, but the normal API error handling still protects
            # the account if Meta rejects the actual publish operation.
            limit_payload = {"warning": str(exc)[:240]}
        reasons = validate_post(post)
        if reasons:
            post["status"] = "needs_review"
            post["review_reasons"] = reasons
            save_queue(self.s.queue_path, posts)
            return {"published": 0, "reason": "review_failed", "details": reasons}
        media_type = str(post.get("media_type") or "carousel").lower()
        if media_type == "reel":
            video_asset = Path(str(post.get("video_asset") or ""))
            if not video_asset.as_posix() or video_asset.as_posix() == ".":
                return {"published": 0, "reason": "missing_video_asset"}
            video_url = f"{self.s.asset_base_url}/{video_asset.as_posix()}"
            media_id = self.api.publish_reel(
                video_url,
                post["caption"],
                bool(post.get("share_to_feed", True)),
            )
        elif len(post.get("assets") or []) > 10:
            return {
                "published": 0,
                "reason": "native_20_publish_required",
                "details": "Instagram Content Publishing API currently accepts at most 10 carousel children",
            }
        else:
            urls = [f"{self.s.asset_base_url}/{Path(asset).as_posix()}" for asset in post["assets"]]
            media_id = self.api.publish_carousel(urls, post["caption"])
        post["status"] = "published"
        post["published_media_id"] = media_id
        post["published_at"] = now.isoformat()
        save_queue(self.s.queue_path, posts)
        return {
            "published": 1,
            "post_id": post["id"],
            "media_id": media_id,
            "publishing_limit": limit_payload,
        }

    def status(self) -> dict:
        posts = load_queue(self.s.queue_path)
        counts: dict[str, int] = {}
        for post in posts:
            state = post.get("status", "unknown")
            counts[state] = counts.get(state, 0) + 1
        return {
            "autopublish_enabled": self.s.autopublish_enabled,
            "credentials_present": bool(self.s.access_token and self.s.user_id),
            "asset_host_present": bool(self.s.asset_base_url),
            "queue": counts,
        }

    @staticmethod
    def _metric_value(payload: dict) -> int | float:
        data = payload.get("data") or []
        if not data:
            return 0
        row = data[0]
        total = row.get("total_value")
        if isinstance(total, dict) and isinstance(total.get("value"), (int, float)):
            return total["value"]
        values = row.get("values") or []
        if values and isinstance(values[-1].get("value"), (int, float)):
            return values[-1]["value"]
        return 0

    @staticmethod
    def _checkpoint_due(snapshots: list[dict], age_hours: float) -> int | None:
        for target in (6, 24, 72):
            if age_hours < target:
                continue
            if any(snapshot.get("checkpoint_hours") == target for snapshot in snapshots):
                continue
            # Honor older hand-entered snapshots that predate checkpoint_hours.
            if any(abs(float(snapshot.get("age_hours_approx", -999)) - target) <= (4 if target == 6 else 12)
                   for snapshot in snapshots):
                continue
            return target
        return None

    def collect_insights(self) -> dict:
        self.s.require_publish()
        assert self.api
        posts = load_queue(self.s.queue_path)
        if self.s.insights_path.exists():
            insights = json.loads(self.s.insights_path.read_text(encoding="utf-8"))
        else:
            insights = {"schema_version": 1, "account": "geobuyerfire", "posts": []}
        records = {row["post_id"]: row for row in insights.setdefault("posts", [])}
        now = datetime.now(self.s.timezone)
        captured = errors = 0
        for post in posts:
            if post.get("status") != "published" or not post.get("published_media_id"):
                continue
            published_at = datetime.fromisoformat(post["published_at"])
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=self.s.timezone)
            age_hours = (now - published_at.astimezone(self.s.timezone)).total_seconds() / 3600
            record = records.setdefault(post["id"], {
                "post_id": post["id"],
                "permalink": post.get("permalink", ""),
                "slide_count": len(post.get("slides") or []),
                "topic": post.get("topic") or post.get("title") or "",
                "snapshots": [],
            })
            checkpoint = self._checkpoint_due(record["snapshots"], age_hours)
            if checkpoint is None:
                continue
            media_id = str(post["published_media_id"])
            try:
                metadata = self.api.media_metadata(media_id)
                metrics: dict[str, int | float] = {}
                for metric in ("views", "reach", "likes", "comments", "saved", "shares",
                               "profile_visits", "follows", "total_interactions"):
                    try:
                        metrics[metric] = self._metric_value(self.api.media_insight(media_id, metric))
                    except InstagramAPIError:
                        # Metric support differs by media product type; retain the rest.
                        continue
            except InstagramAPIError:
                errors += 1
                continue
            reach = int(metrics.get("reach", 0) or 0)
            likes = int(metrics.get("likes", metadata.get("like_count", 0)) or 0)
            comments = int(metrics.get("comments", metadata.get("comments_count", 0)) or 0)
            saves = int(metrics.get("saved", 0) or 0)
            shares = int(metrics.get("shares", 0) or 0)
            profile_visits = int(metrics.get("profile_visits", 0) or 0)
            follows = int(metrics.get("follows", 0) or 0)
            per_1000 = lambda value: round(value * 1000 / reach, 2) if reach else 0
            snapshot = {
                "captured_at": now.isoformat(),
                "checkpoint_hours": checkpoint,
                "age_hours_approx": round(age_hours),
                "media_product_type": metadata.get("media_product_type"),
                "views": int(metrics.get("views", 0) or 0),
                "accounts_reached": reach,
                "likes": likes,
                "comments": comments,
                "saves": saves,
                "shares": shares,
                "profile_visits": profile_visits,
                "follows": follows,
                "total_interactions": int(metrics.get("total_interactions", 0) or 0),
                "rates_per_1000_reached": {
                    "saves": per_1000(saves),
                    "shares": per_1000(shares),
                    "profile_visits": per_1000(profile_visits),
                    "follows": per_1000(follows),
                },
                "decision_status": "insufficient_sample",
            }
            record["permalink"] = metadata.get("permalink") or record.get("permalink", "")
            record["snapshots"].append(snapshot)
            captured += 1
        insights["updated_at"] = now.isoformat()
        self.s.insights_path.parent.mkdir(parents=True, exist_ok=True)
        self.s.insights_path.write_text(json.dumps(insights, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"captured": captured, "errors": errors}
