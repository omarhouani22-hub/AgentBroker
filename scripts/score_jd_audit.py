#!/usr/bin/env python3
"""Offline evidence checklist for a real JD audit response.

Usage:
  python scripts/score_jd_audit.py path/to/real_model_output.txt

This is a screening aid, NOT a validated HR quality score. A human must inspect
whether every claimed finding is correct and supported by the job description.
"""
import argparse
import json
import re
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "jd_audit_sample_ar.json"

def screen(output: str) -> dict:
    checks = {
        "performance_indicators": bool(re.search(r"مؤشر|قياس الأداء|مقياس|KPI", output, re.I)),
        "other_duties_scope": bool(re.search(r"مهام أخرى|يكلف بها|نطاق المهام", output)),
        "tasks_vs_competencies": bool(re.search(r"مهام|مسؤوليات", output)) and bool(re.search(r"كفايات|مهارات", output)),
        "data_privacy_and_authority": bool(re.search(r"صلاحيات|تفويض", output)) and bool(re.search(r"بيانات شخصية|حماية البيانات|خصوصية", output)),
        "reporting_frequency": bool(re.search(r"دورية|تكرار|شهري|أسبوعي|التقارير", output)),
        "employer_questions": "؟" in output or bool(re.search(r"أسئلة|استفسارات|Questions", output, re.I)),
    }
    return {
        "automated_screen_passed": sum(checks.values()),
        "automated_screen_total": len(checks),
        "keyword_presence_only": checks,
        "human_review_required": True,
        "warning": "Keyword matches do not establish correctness, evidence, or commercial quality. Do not interpret as score out of 100.",
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_file", type=Path)
    args = parser.parse_args()
    sample = json.loads(FIXTURE.read_text(encoding="utf-8"))
    output = args.output_file.read_text(encoding="utf-8")
    if len(output.strip()) < 100:
        raise SystemExit("Real model output is missing or too short.")
    result = screen(output)
    result["fixture_title"] = sample["title"]
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
