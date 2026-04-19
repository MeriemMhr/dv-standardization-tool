import importlib.util
import json
import tempfile
import warnings
import unittest
from pathlib import Path

import pandas as pd
import yaml


from scripts.convert_dv import (
    build_original_column_lookup,
    detect_single_file,
    build_schema_suggestion_template,
    export_with_metadata,
    identify_unmapped_columns,
    write_schema_suggestion_file,
    load_schema,
    resolve_io_paths,
    standardize_columns,
    load_input_file,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas" / "standard_dv_mapping.yaml"


class ConvertDVTests(unittest.TestCase):
    def test_load_input_file_detects_semicolon_delimited_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "observations.csv"
            csv_path.write_text("User_ID;MentalLoad\n1;2.5\n", encoding="utf-8")

            df = load_input_file(str(csv_path))

            self.assertEqual(df.columns.tolist(), ["User_ID", "MentalLoad"])
            self.assertEqual(df.loc[0, "MentalLoad"], 2.5)

    def test_load_input_file_does_not_misdetect_alpha_delimiter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "single_column.csv"
            csv_path.write_text("DurationX\n1.0\n2.0\n", encoding="utf-8")

            df = load_input_file(str(csv_path))

            self.assertEqual(df.columns.tolist(), ["DurationX"])
            self.assertEqual(df.shape[1], 1)

    def test_load_input_file_falls_back_to_cp1252_for_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "cp1252.csv"
            csv_path.write_bytes("Label,Value\nCaf\xe9,1\n".encode("cp1252"))

            df = load_input_file(str(csv_path))

            self.assertEqual(df.columns.tolist(), ["Label", "Value"])
            self.assertEqual(df.loc[0, "Label"], "Café")


    def test_load_input_file_reads_pickled_dataframe(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pickle_path = Path(tmpdir) / "study.pkl"
            expected = pd.DataFrame({"DurationX": [1.0, 2.0], "Trust": [4.0, 5.0]})
            expected.to_pickle(pickle_path)

            df = load_input_file(str(pickle_path))

            pd.testing.assert_frame_equal(df, expected)

    def test_case_insensitive_mapping_works(self):
        schema_data = load_schema(str(SCHEMA_PATH))
        mapping = schema_data["mapping"]

        df = pd.DataFrame({"Task_Completion_Time": [1.0], "foo": [2]})
        standardized = standardize_columns(df.copy(), mapping)

        self.assertEqual(standardized.columns.tolist()[0], "task_completion_time")
        self.assertEqual(standardized.columns.tolist()[1], "foo")

    def test_load_schema_combines_custom_and_standard_with_standard_priority(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_schema = Path(tmpdir) / "custom_mapping.yaml"
            custom_schema.write_text(
                """
version: "2.1"
dvs:
  - id: custom_task_time
    aliases:
      - task_time
      - novel_alias
""".strip()
            )

            loaded = load_schema(str(custom_schema), str(SCHEMA_PATH))

            self.assertTrue(loaded["standard_mappings_applied"])
            self.assertEqual(loaded["mapping"]["task_time"], "task_completion_time")
            self.assertEqual(loaded["mapping"]["novel_alias"], "custom_task_time")
            self.assertEqual(loaded["alias_conflict_policy"], "prefer_standard")
            self.assertGreaterEqual(len(loaded["alias_conflicts"]), 1)

    def test_load_schema_prefer_custom_policy_keeps_custom_target_on_conflict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_schema = Path(tmpdir) / "custom_mapping.yaml"
            custom_schema.write_text(
                """
version: "2.1"
dvs:
  - id: custom_task_time
    aliases:
      - task_time
""".strip()
            )

            loaded = load_schema(
                str(custom_schema),
                str(SCHEMA_PATH),
                alias_conflict_policy="prefer_custom",
            )

            self.assertEqual(loaded["mapping"]["task_time"], "custom_task_time")
            self.assertEqual(loaded["alias_conflict_policy"], "prefer_custom")

    def test_load_schema_error_policy_raises_on_conflict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_schema = Path(tmpdir) / "custom_mapping.yaml"
            custom_schema.write_text(
                """
version: "2.1"
dvs:
  - id: custom_task_time
    aliases:
      - task_time
""".strip()
            )

            with self.assertRaises(ValueError):
                load_schema(
                    str(custom_schema),
                    str(SCHEMA_PATH),
                    alias_conflict_policy="error",
                )


    def test_load_schema_raises_for_empty_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "empty.yaml"
            schema_path.write_text("", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "empty or only contains null"):
                load_schema(str(schema_path))

    def test_load_schema_handles_null_dvs_as_empty_mapping(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "null_dvs.yaml"
            schema_path.write_text("version: '2.1'\ndvs: null\n", encoding="utf-8")

            loaded = load_schema(str(schema_path))

            self.assertEqual(loaded["mapping"], {})
            self.assertFalse(loaded["standard_mappings_applied"])

    def test_identify_unmapped_columns_lists_unknown_values(self):
        mapping = {"task_time": "task_completion_time", "task_completion_time": "task_completion_time"}

        unknown = identify_unmapped_columns(["task_time", "unknown_dv", "Task_Time"], mapping)

        self.assertEqual(unknown, ["unknown_dv"])


    def test_build_schema_suggestion_template_creates_yaml_ready_entries(self):
        template = build_schema_suggestion_template(["Time to Complete", "NASA-TLX?"])

        self.assertIn("dvs", template)
        self.assertEqual(template["dvs"][0]["id"], "time_to_complete")
        self.assertEqual(template["dvs"][0]["aliases"], ["Time to Complete"])
        self.assertEqual(template["dvs"][1]["id"], "nasa_tlx")

    def test_write_schema_suggestion_file_writes_expected_yaml_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "standardized.csv"
            suggestion_path = write_schema_suggestion_file(str(output_path), ["Rare Metric"])

            self.assertTrue(suggestion_path.exists())
            self.assertTrue(suggestion_path.name.endswith("_schema_suggestions.yaml"))

            loaded = yaml.safe_load(suggestion_path.read_text())
            self.assertEqual(loaded["dvs"][0]["aliases"], ["Rare Metric"])

    def test_original_column_lookup_tracks_source_aliases(self):
        mapping = {
            "task_time": "task_completion_time",
            "tasktime": "task_completion_time",
        }
        df = pd.DataFrame({"task_time": [1], "tasktime": [2], "other": [3]})

        lookup = build_original_column_lookup(df, mapping)

        self.assertEqual(
            lookup["task_completion_time"],
            ["task_time", "tasktime"],
        )
        self.assertEqual(lookup["other"], ["other"])

    def test_detect_single_file_returns_none_when_multiple_matches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            (folder / "a.csv").write_text("x\n1\n")
            (folder / "b.csv").write_text("x\n2\n")

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = detect_single_file(folder, (".csv",), "input data")

            self.assertIsNone(result)
            self.assertTrue(any("Multiple input data files" in str(w.message) for w in caught))

    def test_resolve_io_paths_infers_files_and_default_output_in_folder_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            (folder / "study.csv").write_text("Task_Completion_Time\n1\n")
            (folder / "mapping.yaml").write_text("dvs: []\n")

            resolved_input, resolved_output, resolved_schema = resolve_io_paths(
                str(folder),
                output_arg=None,
                schema_arg=None,
            )

            self.assertEqual(resolved_input.name, "study.csv")
            self.assertEqual(resolved_schema.name, "mapping.yaml")
            self.assertEqual(resolved_output.name, "study-standardized.csv")


    def test_resolve_io_paths_raises_on_multiple_input_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            (folder / "study.csv").write_text("a\n1\n")
            (folder / "study2.xlsx").write_text("placeholder")

            with self.assertRaises(ValueError):
                resolve_io_paths(str(folder), output_arg=None, schema_arg=None)

    def test_resolve_io_paths_raises_on_multiple_schema_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            (folder / "study.csv").write_text("a\n1\n")
            (folder / "s1.yaml").write_text("dvs: []\n")
            (folder / "s2.yml").write_text("dvs: []\n")

            with self.assertRaises(ValueError):
                resolve_io_paths(str(folder), output_arg=None, schema_arg=None)

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "openpyxl not installed")
    def test_export_with_metadata_honors_xlsx_extension(self):
        df = pd.DataFrame({"task_completion_time": [1.2, 2.3]})
        meta = {
            "task_completion_time": {
                "category": "continuous",
                "needs_review": False,
                "original_name": ["Task_Completion_Time"],
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "standardized.xlsx"
            export_with_metadata(df, meta, str(output_path), schema_version="2.1")

            self.assertTrue(output_path.exists())
            sidecar = output_path.with_suffix("")
            sidecar_json = Path(str(sidecar) + "_metadata.json")
            self.assertTrue(sidecar_json.exists())

            parsed = json.loads(sidecar_json.read_text())
            self.assertEqual(parsed["summary"]["total_columns"], 1)

    def test_export_with_metadata_includes_unknown_mapping_recommendation(self):
        df = pd.DataFrame({"task_completion_time": [1.2, 2.3]})
        meta = {
            "task_completion_time": {
                "category": "continuous",
                "needs_review": False,
                "original_name": ["Task_Completion_Time"],
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "standardized.csv"
            export_with_metadata(
                df,
                meta,
                str(output_path),
                schema_version="2.1",
                unknown_columns=["rare_metric"],
            )

            sidecar_json = Path(tmpdir) / "standardized_metadata.json"
            parsed = json.loads(sidecar_json.read_text())

            self.assertEqual(parsed["summary"]["unknown_columns"], ["rare_metric"])
            self.assertIn("Consider proposing", parsed["summary"]["recommendation"])
            self.assertIn("schema_suggestion_template", parsed["summary"])
            suggestion_file = Path(parsed["summary"]["schema_suggestion_file"])
            self.assertTrue(suggestion_file.exists())


if __name__ == "__main__":
    unittest.main()

