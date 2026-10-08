import unittest

from pydantic import ValidationError
from sqlalchemy import String, Text

from app.ai_engine.schemas import SkillGapReport
from app.models import SkillGapAnalysis
from migrate_db import _readiness_category


class SkillGapPersistenceTests(unittest.TestCase):
    def test_report_requires_categorical_readiness(self):
        report = SkillGapReport(overall_summary="Readiness rationale.", readiness="DEVELOPING")
        self.assertEqual(report.readiness, "DEVELOPING")
        with self.assertRaises(ValidationError):
            SkillGapReport(
                overall_summary="Readiness rationale.",
                readiness="You are currently in progress for Level 3.",
            )

    def test_legacy_readiness_prose_maps_to_category_and_is_retained(self):
        category, details = _readiness_category(
            "You are currently in progress for Level 3. Target database indexing."
        )
        self.assertEqual(category, "DEVELOPING")
        self.assertEqual(
            details,
            "You are currently in progress for Level 3. Target database indexing.",
        )

    def test_categorical_readiness_is_normalized_without_extra_details(self):
        self.assertEqual(_readiness_category("not ready"), ("NOT_READY", None))
        self.assertEqual(_readiness_category("developing"), ("DEVELOPING", None))
        self.assertEqual(_readiness_category("READY"), ("READY", None))

    def test_database_column_types_match_report_contract(self):
        columns = SkillGapAnalysis.__table__.c
        self.assertIsInstance(columns.overall_summary.type, Text)
        self.assertIsInstance(columns.readiness.type, String)
        self.assertEqual(columns.readiness.type.length, 20)
        for name in (
            "strengths",
            "gaps",
            "next_level_priorities",
            "recommended_plan",
            "priority_topics",
        ):
            self.assertEqual(columns[name].type.__class__.__name__, "JSON")


if __name__ == "__main__":
    unittest.main()
