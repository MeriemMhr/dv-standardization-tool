import unittest

from scripts.validate_schema import validate_new_format


class ValidateSchemaTests(unittest.TestCase):
    def test_validate_new_format_allows_auxiliary_schema_without_label_cluster(self):
        schema = {
            "version": "1.0",
            "schema_type": "sensor",
            "dvs": [
                {
                    "id": "eye_gaze_forward",
                    "aliases": ["gaze.forward"],
                }
            ],
        }

        issues = validate_new_format(schema)

        self.assertEqual(issues, [])

    def test_validate_new_format_rejects_ambiguous_case_insensitive_aliases(self):
        schema = {
            "version": "2.1",
            "dvs": [
                {
                    "id": "trust_rating",
                    "label": "Trust",
                    "cluster": "ux_satisfaction",
                    "aliases": ["TrustScore"],
                },
                {
                    "id": "user_satisfaction",
                    "label": "Satisfaction",
                    "cluster": "ux_satisfaction",
                    "aliases": ["trustscore"],
                },
            ],
        }

        issues = validate_new_format(schema)

        self.assertTrue(any("Ambiguous aliases found across DVs" in issue for issue in issues))

    def test_validate_new_format_rejects_duplicate_ids(self):
        schema = {
            "version": "2.1",
            "dvs": [
                {
                    "id": "trust_rating",
                    "label": "Trust",
                    "cluster": "ux_satisfaction",
                    "aliases": ["TrustScore"],
                },
                {
                    "id": "trust_rating",
                    "label": "Trust Again",
                    "cluster": "ux_satisfaction",
                    "aliases": ["TrustScore2"],
                },
            ],
        }

        issues = validate_new_format(schema)

        self.assertIn("Duplicate DV ID found: 'trust_rating'", issues)


if __name__ == "__main__":
    unittest.main()
