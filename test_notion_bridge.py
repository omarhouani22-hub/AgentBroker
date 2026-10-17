"""Offline tests: no external API or credentials required."""
import os
import unittest
from unittest.mock import patch
import notion_bridge


class NotionBridgeTests(unittest.TestCase):
    def setUp(self):
        self.note = {
            "topic": "Public HR methods",
            "note": "A short reviewed, public research note.",
            "sources": [{"url": "https://example.org/research", "title": "Source"}],
        }

    @patch.dict(os.environ, {"NOTION_KNOWLEDGE_DATABASE_ID": "db-example"}, clear=True)
    def test_preview_has_no_network_and_maps_properties(self):
        payload = notion_bridge.preview(self.note)
        self.assertEqual(payload["parent"]["database_id"], "db-example")
        self.assertEqual(payload["properties"]["Topic"]["title"][0]["text"]["content"], "Public HR methods")
        self.assertEqual(payload["properties"]["Source URL"]["url"], "https://example.org/research")

    def test_rejects_missing_evidence(self):
        self.note["sources"] = []
        with self.assertRaises(ValueError):
            notion_bridge.preview(self.note)

    def test_rejects_long_note(self):
        self.note["note"] = "x" * 1801
        with self.assertRaises(ValueError):
            notion_bridge.preview(self.note)

    @patch.dict(os.environ, {"NOTION_API_KEY": "fake", "NOTION_KNOWLEDGE_DATABASE_ID": "db-test"}, clear=True)
    @patch("notion_bridge.urlopen")
    def test_pull_returns_only_verified_shape(self, mocked_urlopen):
        import io
        raw = {
            "results": [
                {"id": "note-1", "created_time": "2026-10-17T00:00:00Z",
                 "properties": {
                     "Topic": {"title": [{"plain_text": "Public HR"}]},
                     "Summary": {"rich_text": [{"plain_text": "Reviewed public evidence"}]},
                     "Source URL": {"url": "https://example.org"},
                 }},
                {"id": "note-2", "properties": {
                    "Topic": {"title": [{"plain_text": "Bad"}]},
                    "Summary": {"rich_text": [{"plain_text": "No source"}]},
                    "Source URL": {"url": None},
                }},
            ],
            "has_more": False,
        }
        mocked_urlopen.return_value.__enter__.return_value = io.BytesIO(
            __import__("json").dumps(raw).encode())
        result = notion_bridge.pull_records(20)
        self.assertEqual(len(result["notes"]), 1)
        self.assertEqual(result["notes"][0]["id"], "note-1")

    def test_pull_limit(self):
        with self.assertRaises(ValueError):
            notion_bridge.pull_records(200)

    @patch.dict(os.environ, {}, clear=True)
    def test_no_credentials_no_publish(self):
        with self.assertRaises(notion_bridge.NotionSyncError):
            notion_bridge.publish({"parent": {"database_id": "fake"}})


if __name__ == "__main__":
    unittest.main()
