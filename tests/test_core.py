import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from instagram_factory.editor import validate_post
from instagram_factory.queue import due_posts
from instagram_factory.renderer import render_carousel
from instagram_factory.api import InstagramAPI


class FactoryTests(unittest.TestCase):
    def sample(self):
        return {
            "id": "sample",
            "slides": ["Первый слайд", "Второй слайд"],
            "caption": "Тест",
            "rights_status": "original",
            "commercial": False,
            "commercial_reviewed": True,
        }

    def test_valid_post(self):
        self.assertEqual(validate_post(self.sample()), [])

    def test_accepts_native_twenty_slide_carousel(self):
        post = self.sample()
        post["slides"] = [f"Карточка {index}" for index in range(20)]
        self.assertEqual(validate_post(post), [])

    def test_rejects_replica_claim(self):
        post = self.sample()
        post["caption"] = "Точная копия 1:1"
        self.assertTrue(any(x.startswith("banned_claim") for x in validate_post(post)))

    def test_commercial_needs_review(self):
        post = self.sample()
        post["commercial"] = True
        post["commercial_reviewed"] = False
        self.assertIn("commercial_review_required", validate_post(post))

    def test_due_queue(self):
        post = self.sample() | {"status": "ready", "scheduled_at": "2026-01-01T00:00:00+00:00"}
        self.assertEqual(due_posts([post], datetime(2026, 1, 2, tzinfo=timezone.utc))[0]["id"], "sample")

    def test_renderer(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = render_carousel(self.sample(), Path(folder))
            self.assertEqual(len(paths), 2)
            self.assertTrue(all(path.exists() and path.stat().st_size > 10_000 for path in paths))

    def test_reel_container_parameters(self):
        api = InstagramAPI("token", "123")
        captured = {}

        def fake_request(method, path, params=None):
            captured.update({"method": method, "path": path, "params": params})
            return {"id": "container-1"}

        api._request = fake_request
        container = api.create_reel_container(
            "https://cdn.example/reel.mp4",
            "Подпись",
            share_to_feed=True,
        )
        self.assertEqual(container, "container-1")
        self.assertEqual(captured["params"]["media_type"], "REELS")
        self.assertEqual(captured["params"]["share_to_feed"], "true")


if __name__ == "__main__":
    unittest.main()
