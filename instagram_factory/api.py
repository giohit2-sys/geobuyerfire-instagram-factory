from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class InstagramAPIError(RuntimeError):
    pass


class InstagramAPI:
    """Small client for Meta's official Instagram Content Publishing API."""

    def __init__(self, token: str, user_id: str, version: str = "v24.0",
                 host: str = "https://graph.facebook.com", timeout: int = 30):
        self.token = token
        self.user_id = user_id
        self.version = version
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.base = f"{self.host}/{self.version}"

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None) -> dict:
        payload = {k: v for k, v in (params or {}).items() if v is not None}
        payload["access_token"] = self.token
        url = path if path.startswith("https://") else f"{self.base}/{path.lstrip('/')}"
        encoded = urllib.parse.urlencode(payload).encode()
        if method == "GET":
            url += ("&" if "?" in url else "?") + encoded.decode()
            data = None
        else:
            data = encoded
        request = urllib.request.Request(url, data=data, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            raise InstagramAPIError(f"Instagram API HTTP {exc.code}: {body[:600]}") from exc
        except urllib.error.URLError as exc:
            raise InstagramAPIError(f"Instagram API network error: {exc.reason}") from exc

    def create_image_container(self, image_url: str, is_carousel_item: bool = True) -> str:
        response = self._request("POST", f"{self.user_id}/media", {
            "image_url": image_url,
            "is_carousel_item": str(is_carousel_item).lower(),
        })
        return str(response["id"])

    def create_carousel_container(self, children: list[str], caption: str) -> str:
        if not 2 <= len(children) <= 10:
            raise ValueError("Automated Instagram carousels must contain 2-10 slides")
        response = self._request("POST", f"{self.user_id}/media", {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption,
        })
        return str(response["id"])

    def container_status(self, container_id: str) -> dict:
        return self._request("GET", container_id, {"fields": "status_code,status"})

    def wait_until_ready(self, container_id: str, attempts: int = 20, delay: float = 3.0) -> None:
        for _ in range(attempts):
            status = self.container_status(container_id)
            code = status.get("status_code")
            if code == "FINISHED":
                return
            if code in {"ERROR", "EXPIRED"}:
                raise InstagramAPIError(f"Container {container_id}: {status.get('status') or code}")
            time.sleep(delay)
        raise InstagramAPIError(f"Container {container_id} did not become ready")

    def publish_container(self, container_id: str) -> str:
        response = self._request("POST", f"{self.user_id}/media_publish", {
            "creation_id": container_id,
        })
        return str(response["id"])

    def publish_carousel(self, image_urls: list[str], caption: str) -> str:
        child_ids = []
        for url in image_urls:
            child = self.create_image_container(url)
            self.wait_until_ready(child)
            child_ids.append(child)
        parent = self.create_carousel_container(child_ids, caption)
        self.wait_until_ready(parent)
        return self.publish_container(parent)

    def create_reel_container(
        self,
        video_url: str,
        caption: str,
        share_to_feed: bool = True,
    ) -> str:
        response = self._request("POST", f"{self.user_id}/media", {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": str(share_to_feed).lower(),
        })
        return str(response["id"])

    def publish_reel(
        self,
        video_url: str,
        caption: str,
        share_to_feed: bool = True,
    ) -> str:
        container = self.create_reel_container(video_url, caption, share_to_feed)
        self.wait_until_ready(container, attempts=60, delay=5.0)
        return self.publish_container(container)

    def create_story_container(self, media_url: str, is_video: bool = False) -> str:
        params = {"media_type": "STORIES"}
        params["video_url" if is_video else "image_url"] = media_url
        response = self._request("POST", f"{self.user_id}/media", params)
        return str(response["id"])

    def publish_story(self, media_url: str, is_video: bool = False) -> str:
        container = self.create_story_container(media_url, is_video=is_video)
        self.wait_until_ready(container, attempts=60 if is_video else 20, delay=5.0)
        return self.publish_container(container)

    def recent_media(self, limit: int = 25) -> list[dict]:
        response = self._request("GET", f"{self.user_id}/media", {
            "fields": "id,caption,media_type,media_product_type,permalink,timestamp",
            "limit": min(limit, 100),
        })
        return list(response.get("data", []))
