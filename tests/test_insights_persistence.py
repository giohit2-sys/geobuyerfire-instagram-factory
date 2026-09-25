import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from instagram_factory.api import InstagramAPIError
from instagram_factory.config import Settings
from instagram_factory.pipeline import Pipeline


class FakeAPI:
    def media_metadata(self, media_id):
        return {"permalink": "https://www.instagram.com/p/test/", "like_count": 3,
                "comments_count": 1, "media_product_type": "FEED"}

    def media_insight(self, media_id, metric):
        values = {"reach": 200, "saved": 0, "shares": 4, "views": 350}
        if metric not in values:
            raise InstagramAPIError("unsupported metric")
        return {"data": [{"values": [{"value": values[metric]}]}]}


class InsightsPersistenceTests(unittest.TestCase):
    def test_first_capture_survives_reload_and_is_not_recaptured(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            queue = root / "queue.json"
            history = root / "insights.json"
            queue.write_text(json.dumps([{
                "id": "new-post", "status": "published", "published_media_id": "123",
                "published_at": (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat(),
                "slides": ["one", "two"],
            }]))
            history.write_text(json.dumps({"posts": [{"post_id": "old-post", "snapshots": [{"marker": "keep"}]}]}))
            settings = Settings(access_token="test", user_id="test", asset_base_url="https://example.test",
                                queue_path=queue, insights_path=history, timezone_name="UTC")
            pipeline = Pipeline(settings)
            pipeline.api = FakeAPI()
            result = pipeline.collect_insights()
            self.assertEqual(result["captured"], 1)
            self.assertEqual(result["stored_posts"], 2)
            data = json.loads(history.read_text())
            self.assertEqual(data["posts"][0]["snapshots"], [{"marker": "keep"}])
            snap = data["posts"][1]["snapshots"][0]
            self.assertEqual(snap["rates_per_1000_reached"]["shares"], 20)
            self.assertEqual(snap["saves"], 0)
            self.assertIsNone(snap["profile_visits"])
            self.assertIsNone(snap["rates_per_1000_reached"]["profile_visits"])
            self.assertEqual(snap["likes"], 3)
            self.assertIn("profile_visits", snap["unavailable_metrics"])
            self.assertEqual(snap["raw_metric_responses"]["shares"]["data"][0]["values"][0]["value"], 4)
            reloaded = Pipeline(settings)
            reloaded.api = FakeAPI()
            self.assertEqual(reloaded.collect_insights()["captured"], 0)
            self.assertEqual(len(json.loads(history.read_text())["posts"][1]["snapshots"]), 1)

    def test_empty_metric_response_is_unknown(self):
        self.assertIsNone(Pipeline._metric_value({"data": []}))
        self.assertEqual(Pipeline._metric_value({"data": [{"total_value": {"value": 0}}]}), 0)

    def test_late_recovery_does_not_claim_to_recreate_early_snapshots(self):
        self.assertEqual(Pipeline._checkpoint_due([], 100), 72)
        self.assertEqual(Pipeline._checkpoint_due([], 25), 24)
        self.assertIsNone(Pipeline._checkpoint_due([{"checkpoint_hours": 72}], 101))


if __name__ == "__main__":
    unittest.main()
