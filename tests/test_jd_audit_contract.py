"""Deterministic JD audit endpoint contract tests; no provider calls or payments."""
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import app as agent_app

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "jd_audit_sample_ar.json").read_text(encoding="utf-8"))


class JobDescriptionAuditContractTest(unittest.TestCase):
    def setUp(self):
        self.client = agent_app.app.test_client()

    def test_operator_authentication_required(self):
        with patch.dict(os.environ, {"AGENT_ACCESS_TOKEN": "test-only-secret-123"}):
            response = self.client.post("/offers/jd-audit/draft", json={
                "title": FIXTURE["title"], "description": FIXTURE["description"]
            })
        self.assertEqual(response.status_code, 401)

    def test_invalid_description_rejected(self):
        with patch.dict(os.environ, {"AGENT_ACCESS_TOKEN": "test-only-secret-123"}):
            response = self.client.post(
                "/offers/jd-audit/draft",
                headers={"Authorization": "Bearer test-only-secret-123"},
                json={"title": FIXTURE["title"], "description": "short"},
            )
        self.assertEqual(response.status_code, 400)

    def test_valid_input_reaches_model_and_requires_human_review(self):
        captured = []
        def fake_model(messages):
            captured.extend(messages)
            return {"content": "ملخص: بطاقة الاختصاصي واضحة جزئياً. " +
                    "الفجوات: لا تحدد دورية التقارير ولا مؤشرات الأداء أو حدود الصلاحيات. " +
                    "المقترح: تحديد المسؤوليات ومؤشرات الأداء بالاتفاق مع الإدارة. " +
                    "أسئلة لصاحب العمل: ما مصادر البيانات والصلاحيات المعتمدة؟"}
        with patch.dict(os.environ, {"AGENT_ACCESS_TOKEN": "test-only-secret-123"}), \
             patch.object(agent_app, "model_configured", return_value=True), \
             patch.object(agent_app, "model_call", side_effect=fake_model):
            response = self.client.post(
                "/offers/jd-audit/draft",
                headers={"Authorization": "Bearer test-only-secret-123"},
                json={"title": FIXTURE["title"], "description": FIXTURE["description"]},
            )
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["status"], "draft")
        self.assertTrue(result["human_review_required"])
        self.assertIn(FIXTURE["description"], captured[1]["content"])

    def test_unconfigured_model_is_not_a_success(self):
        with patch.dict(os.environ, {"AGENT_ACCESS_TOKEN": "test-only-secret-123"}), \
             patch.object(agent_app, "model_configured", return_value=False):
            response = self.client.post(
                "/offers/jd-audit/draft",
                headers={"Authorization": "Bearer test-only-secret-123"},
                json={"title": FIXTURE["title"], "description": FIXTURE["description"]},
            )
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
