from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .api import InstagramAPI
from .config import Settings
from .editor import validate_post
from .queue import due_posts, load_queue, save_queue
from .renderer import render_carousel, render_reel, render_story


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
            reasons = validate_post(post, previous)
            if reasons:
                post["status"] = "needs_review"
                post["review_reasons"] = reasons
                rejected += 1
                continue
            media_type = str(post.get("media_type") or "carousel").lower()
            if media_type == "reel":
                path = render_reel(post, self.s.output_dir)
                post["video_asset"] = str(path)
            elif media_type == "story":
                path = render_story(post, self.s.output_dir)
                post["story_asset"] = str(path)
            else:
                paths = render_carousel(post, self.s.output_dir)
                post["assets"] = [str(path) for path in paths]
            post["status"] = "ready"
            if media_type == "carousel":
                previous.append(" ".join(map(str, post.get("slides") or [])))
            elif media_type == "reel":
                previous.append(" ".join(str(scene.get("text") or "") for scene in post.get("scenes") or []))
            else:
                previous.append(str(post.get("text") or ""))
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
        elif media_type == "story":
            story_asset = Path(str(post.get("story_asset") or ""))
            if story_asset.as_posix() == "." or not story_asset.as_posix():
                return {"published": 0, "reason": "missing_story_asset"}
            story_url = f"{self.s.asset_base_url}/{story_asset.as_posix()}"
            media_id = self.api.publish_story(story_url, is_video=False)
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
        return {"published": 1, "post_id": post["id"], "media_id": media_id}

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
