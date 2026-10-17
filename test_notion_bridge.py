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

    @patch.dict(os.environ, {}, clear=True)
    def test_no_credentials_no_publish(self):
        with self.assertRaises(notion_bridge.NotionSyncError):
            notion_bridge.publish({"parent": {"database_id": "fake"}})


if __name__ == "__main__":
    unittest.main()
