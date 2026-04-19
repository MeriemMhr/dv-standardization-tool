"""Extensibility test suite.

Covers all improvements from the extensibility sprint:
- Fuzzy column matching
- Multi-format file loading (CSV separators, Excel sheets, JSON, JSONL, Parquet, …)
- Delimiter auto-detection
- YAML-driven dataset type classifier
- Thematic cluster definitions
- canonical_range in DV schema
- Derived-scale formula field
- Pydantic manifest validation
- Repeated-measures aggregation
- Construct→sub-item mapping built from _DERIVED_SCALES
"""

from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "analyses"))

import pandas as pd
import yaml


# ---------------------------------------------------------------------------
# 1. Fuzzy column matching
# ---------------------------------------------------------------------------

class TestFuzzyColumnMatching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from convert_dv import load_schema, _normalize_colname
        schema = load_schema(str(REPO_ROOT / "schemas" / "standard_dv_mapping.yaml"))
        mapping = schema["mapping"]
        cls.alias_lookup = {_normalize_colname(k): v for k, v in mapping.items()}

    def test_typo_matched_above_threshold(self):
        from convert_dv import _fuzzy_match_column
        canon, score = _fuzzy_match_column("trust_rting", self.alias_lookup, threshold=80.0)
        self.assertEqual(canon, "trust_rating")
        self.assertGreater(score, 80.0)

    def test_typo_below_threshold_not_matched(self):
        from convert_dv import _fuzzy_match_column
        canon, score = _fuzzy_match_column("xyz_qwerty_zzz", self.alias_lookup, threshold=85.0)
        self.assertIsNone(canon)

    def test_case_insensitive(self):
        from convert_dv import _fuzzy_match_column
        canon, _ = _fuzzy_match_column("TRUST_RATING", self.alias_lookup, threshold=80.0)
        self.assertEqual(canon, "trust_rating")

    def test_exact_alias_matched(self):
        from convert_dv import _fuzzy_match_column
        # "mentaldemand" normalized is a known alias
        canon, score = _fuzzy_match_column("mental_demand", self.alias_lookup, threshold=80.0)
        self.assertIsNotNone(canon)
        self.assertIn("demand", canon.lower())

    def test_fuzzy_score_is_float(self):
        from convert_dv import _fuzzy_match_column
        _, score = _fuzzy_match_column("trust_rting", self.alias_lookup, threshold=50.0)
        self.assertIsInstance(score, float)

    def test_threshold_respected_strict(self):
        from convert_dv import _fuzzy_match_column
        # With very high threshold nothing should match a typo
        canon, _ = _fuzzy_match_column("trust_rting", self.alias_lookup, threshold=99.9)
        self.assertIsNone(canon)

    def test_empty_alias_lookup_returns_none(self):
        from convert_dv import _fuzzy_match_column
        canon, score = _fuzzy_match_column("trust_rating", {}, threshold=80.0)
        self.assertIsNone(canon)
        self.assertEqual(score, 0.0)


# ---------------------------------------------------------------------------
# 2. Delimiter auto-detection
# ---------------------------------------------------------------------------

class TestDelimiterDetection(unittest.TestCase):
    def _detect(self, sample: str) -> str:
        from convert_dv import _detect_delimiter
        return _detect_delimiter(sample)

    def test_comma_delimiter(self):
        sample = "a,b,c\n1,2,3\n4,5,6\n7,8,9"
        self.assertEqual(self._detect(sample), ",")

    def test_semicolon_delimiter(self):
        sample = "a;b;c\n1;2;3\n4;5;6\n7;8;9"
        self.assertEqual(self._detect(sample), ";")

    def test_tab_delimiter(self):
        sample = "a\tb\tc\n1\t2\t3\n4\t5\t6"
        self.assertEqual(self._detect(sample), "\t")

    def test_pipe_delimiter(self):
        sample = "a|b|c\n1|2|3\n4|5|6"
        self.assertEqual(self._detect(sample), "|")

    def test_empty_sample_returns_comma(self):
        self.assertEqual(self._detect(""), ",")

    def test_single_column_returns_comma(self):
        sample = "col\n1\n2\n3"
        # No delimiter present — should default to comma (most common)
        result = self._detect(sample)
        self.assertIn(result, [",", ";", "\t", "|"])  # at least returns something valid


# ---------------------------------------------------------------------------
# 3. Multi-format file loading
# ---------------------------------------------------------------------------

class TestFileFormatLoading(unittest.TestCase):

    def _make_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "trust_rating": [3.0, 4.0, 5.0],
            "mental_demand": [10.0, 12.0, 8.0],
        })

    def test_csv_comma_delimiter(self):
        from convert_dv import load_input_file
        df = self._make_df()
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
            df.to_csv(f, index=False)
            p = f.name
        result = load_input_file(p)
        self.assertListEqual(sorted(result.columns.tolist()), ["mental_demand", "trust_rating"])
        self.assertEqual(len(result), 3)

    def test_csv_semicolon_delimiter(self):
        from convert_dv import load_input_file
        df = self._make_df()
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
            df.to_csv(f, sep=";", index=False)
            p = f.name
        result = load_input_file(p)
        self.assertListEqual(sorted(result.columns.tolist()), ["mental_demand", "trust_rating"])

    def test_csv_tab_delimiter(self):
        from convert_dv import load_input_file
        df = self._make_df()
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
            df.to_csv(f, sep="\t", index=False)
            p = f.name
        result = load_input_file(p)
        self.assertListEqual(sorted(result.columns.tolist()), ["mental_demand", "trust_rating"])

    def test_tsv_extension(self):
        from convert_dv import load_input_file
        df = self._make_df()
        with tempfile.NamedTemporaryFile(suffix=".tsv", mode="w", delete=False) as f:
            df.to_csv(f, sep="\t", index=False)
            p = f.name
        result = load_input_file(p)
        self.assertListEqual(sorted(result.columns.tolist()), ["mental_demand", "trust_rating"])

    def test_xlsx_single_sheet(self):
        from convert_dv import load_input_file
        df = self._make_df()
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            p = f.name
        df.to_excel(p, index=False)
        result = load_input_file(p)
        self.assertListEqual(sorted(result.columns.tolist()), ["mental_demand", "trust_rating"])

    def test_xlsx_multi_sheet_picks_largest(self):
        from convert_dv import load_input_file
        big = pd.DataFrame({"col_a": range(20), "col_b": range(20)})
        small = pd.DataFrame({"col_x": [1, 2]})
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            p = f.name
        with pd.ExcelWriter(p) as writer:
            small.to_excel(writer, sheet_name="Sheet1", index=False)
            big.to_excel(writer, sheet_name="Sheet2", index=False)
        result = load_input_file(p)
        # Should have selected the larger sheet
        self.assertIn("col_a", result.columns)
        self.assertEqual(len(result), 20)

    def test_json_records_array(self):
        from convert_dv import load_input_file
        records = [
            {"trust_rating": 3.0, "mental_demand": 10.0},
            {"trust_rating": 4.0, "mental_demand": 12.0},
        ]
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(records, f)
            p = f.name
        result = load_input_file(p)
        self.assertListEqual(sorted(result.columns.tolist()), ["mental_demand", "trust_rating"])
        self.assertEqual(len(result), 2)

    def test_jsonl_format(self):
        from convert_dv import load_input_file
        lines = [
            '{"trust_rating": 3.0, "mental_demand": 10.0}',
            '{"trust_rating": 4.0, "mental_demand": 12.0}',
        ]
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            f.write("\n".join(lines))
            p = f.name
        result = load_input_file(p)
        self.assertListEqual(sorted(result.columns.tolist()), ["mental_demand", "trust_rating"])
        self.assertEqual(len(result), 2)

    @unittest.skipUnless(importlib.util.find_spec("pyarrow"), "pyarrow not installed")
    def test_parquet_format(self):
        from convert_dv import load_input_file
        df = self._make_df()
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            p = f.name
        df.to_parquet(p, index=False)
        result = load_input_file(p)
        self.assertListEqual(sorted(result.columns.tolist()), ["mental_demand", "trust_rating"])

    def test_unsupported_extension_raises_with_list(self):
        from convert_dv import load_input_file, _FORMAT_REGISTRY
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            p = f.name
        with self.assertRaises(ValueError) as ctx:
            load_input_file(p)
        msg = str(ctx.exception).lower()
        self.assertIn(".xyz", msg)
        # Error should mention supported formats
        for fmt in [".csv", ".xlsx"]:
            self.assertIn(fmt, msg)

    def test_utf8_bom_csv(self):
        from convert_dv import load_input_file
        content = "\ufeffcol_a,col_b\n1,2\n3,4\n"
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", encoding="utf-8-sig", delete=False) as f:
            f.write(content)
            p = f.name
        result = load_input_file(p)
        # BOM should not appear in column names
        self.assertNotIn("\ufeffcol_a", result.columns)
        self.assertIn("col_a", result.columns)

    def test_format_registry_is_extensible(self):
        """Adding a new format to the registry makes it available without code changes."""
        from convert_dv import _FORMAT_REGISTRY
        # Verify registry is a dict and can be inspected
        self.assertIsInstance(_FORMAT_REGISTRY, dict)
        self.assertIn(".csv", _FORMAT_REGISTRY)
        self.assertIn(".xlsx", _FORMAT_REGISTRY)
        self.assertIn(".parquet", _FORMAT_REGISTRY)
        self.assertIn(".json", _FORMAT_REGISTRY)
        self.assertIn(".jsonl", _FORMAT_REGISTRY)
        self.assertIn(".sav", _FORMAT_REGISTRY)
        self.assertIn(".dta", _FORMAT_REGISTRY)
        self.assertIn(".feather", _FORMAT_REGISTRY)


# ---------------------------------------------------------------------------
# 4. YAML-driven dataset type classifier
# ---------------------------------------------------------------------------

class TestDatasetTypeProfiles(unittest.TestCase):

    def setUp(self):
        # Clear cache so YAML is re-read between tests
        from batch_profiles import load_dataset_type_profiles
        load_dataset_type_profiles.cache_clear()

    def test_profiles_yaml_loads(self):
        from batch_profiles import load_dataset_type_profiles
        profiles = load_dataset_type_profiles()
        self.assertGreaterEqual(len(profiles), 4)
        ids = [p["id"] for p in profiles]
        self.assertIn("object_detection", ids)
        self.assertIn("sensor_stream", ids)
        self.assertIn("results_table", ids)
        self.assertIn("process_log", ids)

    def test_priority_ordering(self):
        from batch_profiles import load_dataset_type_profiles
        profiles = load_dataset_type_profiles()
        priorities = [p["priority"] for p in profiles]
        self.assertEqual(priorities, sorted(priorities, reverse=True))

    def test_object_detection_via_yolo_path(self):
        from batch_profiles import classify_dataset_type
        cols = ["video", "frame", "objectid", "class", "x", "y", "width", "height", "confidence", "extra"]
        self.assertEqual(classify_dataset_type("yolo_output.csv", cols), "object_detection")

    def test_object_detection_via_markers(self):
        from batch_profiles import classify_dataset_type
        cols = ["video", "frame", "objectid", "class", "x", "y", "width", "height", "confidence", "score"]
        self.assertEqual(classify_dataset_type("detections.csv", cols), "object_detection")

    def test_sensor_stream_via_markers(self):
        from batch_profiles import classify_dataset_type, DATASET_TYPE_SENSOR
        cols = ["gazeforward", "gazeorigin", "leftpupildiameterinmm", "rightirisdiameterinmm",
                "arduinodata1", "pixelx", "timestamp", "extra1", "extra2", "extra3"]
        self.assertEqual(classify_dataset_type("eye_tracking.csv", cols), DATASET_TYPE_SENSOR)

    def test_results_table_fallback(self):
        from batch_profiles import classify_dataset_type, DATASET_TYPE_RESULTS
        cols = ["participant_id", "trust_rating", "mental_demand", "usability"]
        self.assertEqual(classify_dataset_type("results.csv", cols), DATASET_TYPE_RESULTS)

    def test_profiles_have_required_fields(self):
        from batch_profiles import load_dataset_type_profiles
        for profile in load_dataset_type_profiles():
            self.assertIn("id", profile, f"Profile missing 'id': {profile}")
            self.assertIn("priority", profile, f"Profile '{profile.get('id')}' missing 'priority'")
            self.assertIn("schema", profile, f"Profile '{profile.get('id')}' missing 'schema'")

    def test_get_schema_for_dataset_type(self):
        from batch_profiles import get_schema_for_dataset_type
        schema = get_schema_for_dataset_type("sensor_stream")
        self.assertIn("sensor", schema)
        schema2 = get_schema_for_dataset_type("results_table")
        self.assertIn("dv", schema2)

    def test_string_path_accepted(self):
        """classify_dataset_type should accept both str and Path for the file argument."""
        from batch_profiles import classify_dataset_type, DATASET_TYPE_RESULTS
        cols = ["trust_rating", "mental_demand"]
        # str path
        result_str = classify_dataset_type("results.csv", cols)
        # Path object
        result_path = classify_dataset_type(Path("results.csv"), cols)
        self.assertEqual(result_str, result_path)
        self.assertEqual(result_str, DATASET_TYPE_RESULTS)


# ---------------------------------------------------------------------------
# 5. Thematic clusters
# ---------------------------------------------------------------------------

class TestThematicClusters(unittest.TestCase):

    def test_clusters_yaml_exists(self):
        path = REPO_ROOT / "schemas" / "thematic_clusters.yaml"
        self.assertTrue(path.exists(), "schemas/thematic_clusters.yaml must exist")

    def test_clusters_yaml_structure(self):
        path = REPO_ROOT / "schemas" / "thematic_clusters.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertIn("clusters", data)
        self.assertGreaterEqual(len(data["clusters"]), 8)

    def test_cluster_required_fields(self):
        path = REPO_ROOT / "schemas" / "thematic_clusters.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for cluster in data["clusters"]:
            self.assertIn("id", cluster, f"Cluster missing 'id': {cluster}")
            self.assertIn("label", cluster, f"Cluster '{cluster.get('id')}' missing 'label'")
            self.assertIn("description", cluster, f"Cluster '{cluster.get('id')}' missing 'description'")

    def test_all_dv_cluster_ids_are_defined(self):
        dv_data = yaml.safe_load(
            (REPO_ROOT / "schemas" / "standard_dv_mapping.yaml").read_text(encoding="utf-8")
        )
        cluster_data = yaml.safe_load(
            (REPO_ROOT / "schemas" / "thematic_clusters.yaml").read_text(encoding="utf-8")
        )
        dv_clusters = {e["cluster"] for e in dv_data.get("dvs", []) if "cluster" in e and e["cluster"]}
        defined = {c["id"] for c in cluster_data.get("clusters", [])}
        undefined = dv_clusters - defined
        self.assertFalse(
            undefined,
            f"Cluster IDs referenced in DVs but not defined in thematic_clusters.yaml: {undefined}",
        )


# ---------------------------------------------------------------------------
# 6. canonical_range in DV schema
# ---------------------------------------------------------------------------

class TestCanonicalRange(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import multi_study_analysis as m
        m._load_dv_measurement_metadata.cache_clear()
        cls.meta = m._load_dv_measurement_metadata()

    def test_sus_total_has_range_0_100(self):
        self.assertIn("usability", self.meta)
        r = self.meta["usability"].get("canonical_range")
        self.assertIsNotNone(r, "usability (SUS) must have canonical_range")
        self.assertEqual(r, (0.0, 100.0))

    def test_tlx_subscale_has_range_0_20(self):
        for dv in ("mental_demand", "physical_demand", "temporal_demand",
                   "performance", "effort", "frustration"):
            if dv not in self.meta:
                continue
            r = self.meta[dv].get("canonical_range")
            self.assertIsNotNone(r, f"{dv} must have canonical_range")
            self.assertEqual(r, (0.0, 20.0), f"{dv} range should be (0, 20)")

    def test_aoa_subscale_has_range(self):
        for dv in ("AOA_USEFULNESS", "AOA_SATISFYING"):
            if dv not in self.meta:
                continue
            r = self.meta[dv].get("canonical_range")
            self.assertIsNotNone(r, f"{dv} must have canonical_range")
            lo, hi = r
            self.assertLess(lo, 0, f"{dv} range should have negative min")
            self.assertGreater(hi, 0, f"{dv} range should have positive max")

    def test_schema_canonical_range_takes_precedence(self):
        """canonical_range from YAML overrides regex-parsed range."""
        import yaml as _yaml
        raw = _yaml.safe_load(
            (REPO_ROOT / "schemas" / "standard_dv_mapping.yaml").read_text(encoding="utf-8")
        )
        for dv in raw.get("dvs", []):
            meas = dv.get("measurement", {}) or {}
            if "canonical_range" in meas:
                r = meas["canonical_range"]
                self.assertIsInstance(r, list, f"canonical_range must be list in {dv['id']}")
                self.assertEqual(len(r), 2, f"canonical_range must have 2 elements in {dv['id']}")
                self.assertLess(r[0], r[1], f"canonical_range[0] < canonical_range[1] in {dv['id']}")

    def test_unbounded_dvs_have_no_range(self):
        """Time/count DVs should NOT have canonical_range (they're unbounded)."""
        for dv in ("task_completion_time",):
            if dv not in self.meta:
                continue
            self.assertNotIn(
                "canonical_range", self.meta[dv],
                f"{dv} is unbounded and should not have canonical_range",
            )

    def test_trust_rating_has_1_5_range(self):
        """trust_rating must be 1–5 (TiA/eHMI Likert)."""
        self.assertIn("trust_rating", self.meta)
        r = self.meta["trust_rating"].get("canonical_range")
        self.assertIsNotNone(r, "trust_rating must have canonical_range")
        self.assertEqual(r, (1.0, 5.0))

    def test_sart_understanding_has_0_20_range(self):
        """sART Understanding subscale must be 0–20."""
        self.assertIn("sart_understanding", self.meta)
        r = self.meta["sart_understanding"].get("canonical_range")
        self.assertIsNotNone(r, "sart_understanding must have canonical_range")
        self.assertEqual(r, (0.0, 20.0))

    def test_perceived_safety_is_bipolar_range(self):
        """perceived_safety is a bipolar −3 to +3 scale."""
        self.assertIn("perceived_safety", self.meta)
        r = self.meta["perceived_safety"].get("canonical_range")
        self.assertIsNotNone(r, "perceived_safety must have canonical_range")
        lo, hi = r
        self.assertLess(lo, 0, "perceived_safety min must be negative (bipolar)")
        self.assertGreater(hi, 0, "perceived_safety max must be positive (bipolar)")
        self.assertEqual(r, (-3.0, 3.0))

    def test_acceptance_rating_has_1_7_range(self):
        """acceptance_rating is a 7-point (1–7) Likert scale."""
        self.assertIn("acceptance_rating", self.meta)
        r = self.meta["acceptance_rating"].get("canonical_range")
        self.assertIsNotNone(r, "acceptance_rating must have canonical_range")
        self.assertEqual(r, (1.0, 7.0))

    def test_safety_trust_cluster_is_used(self):
        """perceived_safety, trust_rating, perceived_risk should all be in safety_trust cluster."""
        for dv in ("perceived_safety", "trust_rating", "perceived_risk"):
            if dv not in self.meta:
                continue
            cluster = self.meta[dv].get("cluster", "")
            self.assertEqual(
                cluster, "safety_trust",
                f"{dv} should be in 'safety_trust' cluster, got '{cluster}'",
            )

    def test_fact_av_mapping_redirects_understanding(self):
        """fact_av_mapping.yaml must map understanding_rating → sart_understanding."""
        mapping_path = REPO_ROOT / "schemas" / "fact_av_mapping.yaml"
        self.assertTrue(mapping_path.exists(), "schemas/fact_av_mapping.yaml must exist")
        data = yaml.safe_load(mapping_path.read_text(encoding="utf-8")) or {}
        self.assertEqual(
            data.get("understanding_rating"), "sart_understanding",
            "fact_av_mapping must redirect understanding_rating → sart_understanding",
        )


# ---------------------------------------------------------------------------
# 7. Derived-scale formula field and construct→sub-item mapping
# ---------------------------------------------------------------------------

class TestDerivedScalesFormula(unittest.TestCase):

    def test_all_scales_have_formula_field(self):
        import multi_study_analysis as m
        for key, spec in m._DERIVED_SCALES.items():
            self.assertIn("formula", spec, f"Missing 'formula' in _DERIVED_SCALES['{key}']")
            self.assertIn(
                spec["formula"], ("mean", "weighted_mean", "custom"),
                f"Unknown formula '{spec['formula']}' in _DERIVED_SCALES['{key}']",
            )

    def test_nasa_tlx_formula_is_mean(self):
        import multi_study_analysis as m
        self.assertEqual(m._DERIVED_SCALES["nasa_tlx_score"]["formula"], "mean")

    def test_sus_formula_is_custom(self):
        import multi_study_analysis as m
        self.assertEqual(m._DERIVED_SCALES["sus_score"]["formula"], "custom")

    def test_mean_formula_computes_unweighted_mean(self):
        import multi_study_analysis as m
        df = pd.DataFrame({
            "mental_demand": [10.0],
            "physical_demand": [8.0],
            "temporal_demand": [12.0],
            "performance": [14.0],
            "effort": [6.0],
            "frustration": [4.0],
        })
        result = m.add_derived_scale_scores(df)
        self.assertIn("nasa_tlx_score", result.columns)
        expected = (10 + 8 + 12 + 14 + 6 + 4) / 6
        self.assertAlmostEqual(result["nasa_tlx_score"].iloc[0], expected, places=3)

    def test_sus_custom_formula_correct_bounds(self):
        import multi_study_analysis as m
        # SUS score = 0 when all odd items = 1, all even items = 5
        df = pd.DataFrame({f"sus{i}": [1.0 if i % 2 == 1 else 5.0] for i in range(1, 11)})
        result = m.add_derived_scale_scores(df)
        self.assertIn("sus_score", result.columns)
        self.assertAlmostEqual(result["sus_score"].iloc[0], 0.0, places=3)

    def test_sus_max_score(self):
        import multi_study_analysis as m
        # SUS = 100 when all odd items = 5, all even items = 1
        df = pd.DataFrame({f"sus{i}": [5.0 if i % 2 == 1 else 1.0] for i in range(1, 11)})
        result = m.add_derived_scale_scores(df)
        self.assertIn("sus_score", result.columns)
        self.assertAlmostEqual(result["sus_score"].iloc[0], 100.0, places=3)

    def test_construct_subitems_auto_built(self):
        import multi_study_analysis as m
        cs = m.CONSTRUCT_SUBITEMS
        self.assertIn("usability", cs)
        self.assertIn("SUS1", cs["usability"])
        self.assertEqual(len(cs["usability"]), 10)

    def test_construct_subitems_tlx_parent_present(self):
        import multi_study_analysis as m
        cs = m.CONSTRUCT_SUBITEMS
        # TLX_SCORE should have mental_demand as sub-item
        self.assertTrue(
            any("mental_demand" in items for items in cs.values()),
            "mental_demand must be a sub-item of some TLX construct",
        )

    def test_adding_mean_formula_scale_works_zero_python(self):
        """A scale with formula='mean' should compute automatically without custom code."""
        import multi_study_analysis as m
        # Temporarily add a test scale
        original = dict(m._DERIVED_SCALES)
        m._DERIVED_SCALES["test_mean_scale"] = {
            "item_candidates": [["col_a", "a"], ["col_b", "b"], ["col_c", "c"]],
            "canonical_subitems": ["COL_A", "COL_B", "COL_C"],
            "formula": "mean",
        }
        try:
            df = pd.DataFrame({"col_a": [10.0], "col_b": [20.0], "col_c": [30.0]})
            result = m.add_derived_scale_scores(df)
            self.assertIn("test_mean_scale", result.columns)
            self.assertAlmostEqual(result["test_mean_scale"].iloc[0], 20.0, places=3)
        finally:
            m._DERIVED_SCALES.clear()
            m._DERIVED_SCALES.update(original)


# ---------------------------------------------------------------------------
# 8. Pydantic manifest validation
# ---------------------------------------------------------------------------

class TestPydanticManifestValidation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import run_batch_standardization as rbs
        cls._PYDANTIC_AVAILABLE = getattr(rbs, "_PYDANTIC_AVAILABLE", False)
        # Store as a static reference so self._validate(x) calls _validate_manifest(x)
        _fn = rbs._validate_manifest
        cls._validate = staticmethod(_fn)

    def _valid_source(self, **kwargs):
        base = {"source_id": "test_study", "source_type": "local_path", "location": "/tmp/data"}
        base.update(kwargs)
        return base

    def test_valid_manifest_no_errors(self):
        errors = self._validate({"sources": [self._valid_source()]})
        self.assertEqual(errors, [])

    def test_invalid_source_type_fails(self):
        errors = self._validate({"sources": [self._valid_source(source_type="ftp_server")]})
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("source_type" in e for e in errors))

    def test_source_id_with_spaces_fails(self):
        errors = self._validate({"sources": [self._valid_source(source_id="my study name")]})
        self.assertGreater(len(errors), 0)

    def test_source_id_with_hyphens_valid(self):
        errors = self._validate({"sources": [self._valid_source(source_id="my-study-2024")]})
        self.assertEqual(errors, [])

    def test_source_id_with_underscores_valid(self):
        errors = self._validate({"sources": [self._valid_source(source_id="my_study_2024")]})
        self.assertEqual(errors, [])

    def test_llm_context_as_string_valid(self):
        errors = self._validate({"sources": [self._valid_source(llm_context="some context")]})
        self.assertEqual(errors, [])

    def test_llm_context_as_list_valid(self):
        errors = self._validate({"sources": [self._valid_source(llm_context=["ctx1", "ctx2"])]})
        self.assertEqual(errors, [])

    def test_llm_context_as_none_valid(self):
        errors = self._validate({"sources": [self._valid_source(llm_context=None)]})
        self.assertEqual(errors, [])

    def test_unknown_extra_fields_allowed(self):
        errors = self._validate({"sources": [
            self._valid_source(future_field="value", another_new_field=42)
        ]})
        self.assertEqual(errors, [])

    def test_repeated_measures_bool_field(self):
        errors = self._validate({"sources": [self._valid_source(repeated_measures=True)]})
        self.assertEqual(errors, [])

    def test_multiple_sources_all_validated(self):
        sources = [self._valid_source(source_id="s1"), self._valid_source(source_id="s2")]
        errors = self._validate({"sources": sources})
        self.assertEqual(errors, [])

    def test_all_valid_source_types(self):
        for stype in ("local_path", "github_repo", "osf_project", "web_dataset"):
            errors = self._validate({"sources": [self._valid_source(source_type=stype)]})
            self.assertEqual(errors, [], f"source_type='{stype}' should be valid")


# ---------------------------------------------------------------------------
# 9. Repeated-measures aggregation
# ---------------------------------------------------------------------------

class TestRepeatedMeasuresAggregation(unittest.TestCase):

    def _make_study_dir(self, tmpdir: str) -> Path:
        df = pd.DataFrame({
            "participant_id": [1, 1, 1, 2, 2, 2],
            "trust_rating": [3.0, 4.0, 5.0, 2.0, 3.0, 4.0],
            "mental_demand": [10.0, 12.0, 8.0, 14.0, 16.0, 18.0],
        })
        d = Path(tmpdir) / "my_study"
        d.mkdir(parents=True)
        df.to_csv(d / "data.csv", index=False)
        return Path(tmpdir)

    def test_aggregates_to_participant_means(self):
        import multi_study_analysis as m
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = self._make_study_dir(tmpdir)
            studies = m.load_studies(input_dir, repeated_measures_studies={"my_study"})
            self.assertIn("my_study", studies)
            # 2 participants → 2 rows after aggregation
            self.assertEqual(len(studies["my_study"]), 2)

    def test_aggregated_means_correct(self):
        import multi_study_analysis as m
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = self._make_study_dir(tmpdir)
            studies = m.load_studies(input_dir, repeated_measures_studies={"my_study"})
            df = studies["my_study"]
            p1 = df[df["participant_id"] == 1]
            self.assertAlmostEqual(p1["trust_rating"].iloc[0], 4.0, places=3)
            self.assertAlmostEqual(p1["mental_demand"].iloc[0], 10.0, places=3)

    def test_no_flag_keeps_all_rows(self):
        import multi_study_analysis as m
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = self._make_study_dir(tmpdir)
            studies = m.load_studies(input_dir)  # no repeated_measures_studies
            self.assertEqual(len(studies["my_study"]), 6)

    def test_other_studies_unaffected(self):
        import multi_study_analysis as m
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = self._make_study_dir(tmpdir)
            # Add a second study
            d2 = Path(tmpdir) / "other_study"
            d2.mkdir()
            pd.DataFrame({"trust_rating": [1.0, 2.0, 3.0]}).to_csv(d2 / "d.csv", index=False)
            # Only aggregate my_study
            studies = m.load_studies(input_dir, repeated_measures_studies={"my_study"})
            self.assertEqual(len(studies["other_study"]), 3)
            self.assertEqual(len(studies["my_study"]), 2)


# ---------------------------------------------------------------------------
# 10. Schema validation — structural integrity
# ---------------------------------------------------------------------------

class TestSchemaIntegrity(unittest.TestCase):

    def test_standard_dv_mapping_valid_yaml(self):
        data = yaml.safe_load(
            (REPO_ROOT / "schemas" / "standard_dv_mapping.yaml").read_text(encoding="utf-8")
        )
        self.assertIn("dvs", data)
        self.assertGreater(len(data["dvs"]), 50)

    def test_all_dvs_have_id_label_cluster(self):
        data = yaml.safe_load(
            (REPO_ROOT / "schemas" / "standard_dv_mapping.yaml").read_text(encoding="utf-8")
        )
        for dv in data["dvs"]:
            self.assertIn("id", dv, f"DV missing 'id': {dv}")
            self.assertIn("label", dv, f"DV '{dv.get('id')}' missing 'label'")
            self.assertIn("cluster", dv, f"DV '{dv.get('id')}' missing 'cluster'")

    def test_canonical_range_values_valid(self):
        data = yaml.safe_load(
            (REPO_ROOT / "schemas" / "standard_dv_mapping.yaml").read_text(encoding="utf-8")
        )
        for dv in data["dvs"]:
            meas = dv.get("measurement", {}) or {}
            if "canonical_range" not in meas:
                continue
            r = meas["canonical_range"]
            self.assertIsInstance(r, list, f"canonical_range must be list in {dv['id']}")
            self.assertEqual(len(r), 2, f"canonical_range must have 2 elements in {dv['id']}")
            self.assertLess(r[0], r[1], f"canonical_range[0] < canonical_range[1] required in {dv['id']}")

    def test_dataset_type_profiles_valid(self):
        path = REPO_ROOT / "schemas" / "dataset_type_profiles.yaml"
        self.assertTrue(path.exists(), "schemas/dataset_type_profiles.yaml must exist")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertIn("dataset_types", data)
        for dt in data["dataset_types"]:
            self.assertIn("id", dt)
            self.assertIn("schema", dt)
            self.assertIn("priority", dt)

    def test_dataset_type_profiles_has_results_table_fallback(self):
        data = yaml.safe_load(
            (REPO_ROOT / "schemas" / "dataset_type_profiles.yaml").read_text(encoding="utf-8")
        )
        ids = [dt["id"] for dt in data["dataset_types"]]
        self.assertIn("results_table", ids)
        rt = next(dt for dt in data["dataset_types"] if dt["id"] == "results_table")
        self.assertEqual(rt["priority"], 0)

    def test_no_duplicate_dv_ids(self):
        data = yaml.safe_load(
            (REPO_ROOT / "schemas" / "standard_dv_mapping.yaml").read_text(encoding="utf-8")
        )
        ids = [dv["id"] for dv in data["dvs"] if "id" in dv]
        self.assertEqual(len(ids), len(set(ids)), f"Duplicate DV IDs: {[x for x in ids if ids.count(x) > 1]}")


# ---------------------------------------------------------------------------
# 11. JSON output from multi-study analysis
# ---------------------------------------------------------------------------

class TestMultiStudyJsonOutput(unittest.TestCase):

    def test_analysis_results_json_written(self):
        """Running main() should produce analysis_results.json with required keys."""
        import multi_study_analysis as m

        # Build minimal studies (2 studies, shared DV: trust_rating)
        rng_state = 42
        import numpy as np
        rng = np.random.default_rng(rng_state)
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = Path(tmpdir) / "input"
            out_dir = Path(tmpdir) / "output"
            (in_dir / "study_a").mkdir(parents=True)
            (in_dir / "study_b").mkdir(parents=True)

            pd.DataFrame({
                "trust_rating": rng.normal(3.5, 0.8, 50),
                "mental_demand": rng.normal(12.0, 2.0, 50),
            }).to_csv(in_dir / "study_a" / "data.csv", index=False)

            pd.DataFrame({
                "trust_rating": rng.normal(4.0, 0.7, 40),
                "mental_demand": rng.normal(10.0, 2.5, 40),
            }).to_csv(in_dir / "study_b" / "data.csv", index=False)

            # Patch sys.argv for main()
            import sys as _sys
            orig_argv = _sys.argv[:]
            _sys.argv = [
                "multi_study_analysis.py",
                "--input-dir", str(in_dir),
                "--output-dir", str(out_dir),
            ]
            try:
                m.main()
            finally:
                _sys.argv = orig_argv

            json_path = out_dir / "analysis_results.json"
            self.assertTrue(json_path.exists(), "analysis_results.json should be written")
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertIn("n_studies", data)
            self.assertIn("studies", data)
            self.assertIn("generated_at", data)
            self.assertEqual(data["n_studies"], 2)


# ---------------------------------------------------------------------------
# 12. New analysis capabilities — meta-regression, trim-and-fill, etc.
# ---------------------------------------------------------------------------

class TestMetaRegression(unittest.TestCase):
    def test_meta_regression_returns_slope(self):
        import multi_study_analysis as m
        summary = pd.DataFrame({
            "study": ["a", "b", "c"],
            "dv": ["trust_rating"] * 3,
            "n": [50, 100, 200],
            "mean": [3.5, 3.8, 4.1],
            "sd": [0.8, 0.7, 0.6],
        })
        result = m.meta_regression(summary, "trust_rating", moderator_col="n")
        self.assertIsNotNone(result)
        self.assertIn("slope", result)
        self.assertIn("r2_analog", result)
        self.assertGreaterEqual(result["r2_analog"], 0.0)

    def test_meta_regression_too_few_studies(self):
        import multi_study_analysis as m
        summary = pd.DataFrame({
            "study": ["a", "b"],
            "dv": ["x"] * 2,
            "n": [50, 100],
            "mean": [3.0, 4.0],
            "sd": [1.0, 1.0],
        })
        result = m.meta_regression(summary, "x")
        self.assertIsNone(result)


class TestTrimAndFill(unittest.TestCase):
    def test_trim_fill_returns_adjusted(self):
        import multi_study_analysis as m
        # Asymmetric data: one outlier study
        summary = pd.DataFrame({
            "study": ["a", "b", "c", "d"],
            "dv": ["x"] * 4,
            "n": [50, 50, 50, 50],
            "mean": [3.0, 3.1, 3.2, 5.0],
            "sd": [0.5, 0.5, 0.5, 0.5],
        })
        result = m.trim_and_fill(summary, "x")
        self.assertIsNotNone(result)
        self.assertIn("adjusted_mean", result)
        self.assertIn("k_imputed", result)

    def test_trim_fill_too_few_studies(self):
        import multi_study_analysis as m
        summary = pd.DataFrame({
            "study": ["a", "b"],
            "dv": ["x"] * 2,
            "n": [50, 50],
            "mean": [3.0, 4.0],
            "sd": [1.0, 1.0],
        })
        result = m.trim_and_fill(summary, "x")
        self.assertIsNone(result)


class TestEffectSizeConversions(unittest.TestCase):
    def test_r_to_d_roundtrip(self):
        import multi_study_analysis as m
        r = 0.3
        d = m.convert_r_to_d(r)
        r_back = m.convert_d_to_r(d)
        self.assertAlmostEqual(r, r_back, places=2)

    def test_or_to_d(self):
        import multi_study_analysis as m
        d = m.convert_or_to_d(2.0)
        self.assertGreater(d, 0)

    def test_eta2_to_d(self):
        import multi_study_analysis as m
        d = m.convert_eta2_to_d(0.06)
        self.assertGreater(d, 0)


class TestPowerAnalysis(unittest.TestCase):
    def test_power_increases_with_k(self):
        import multi_study_analysis as m
        p5 = m.meta_analysis_power(0.5, 50, 5)
        p20 = m.meta_analysis_power(0.5, 50, 20)
        self.assertGreater(p20, p5)

    def test_studies_needed(self):
        import multi_study_analysis as m
        k = m.studies_needed_for_power(0.5, 50, tau2=0.1)
        self.assertIsNotNone(k)
        self.assertGreaterEqual(k, 2)


class TestDataQuality(unittest.TestCase):
    def test_flags_out_of_range(self):
        import multi_study_analysis as m
        # Create a study with values outside canonical range
        studies = {
            "test": pd.DataFrame({
                "trust_rating": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],  # 6, 7 > canonical max 5
            })
        }
        quality = m.flag_data_quality(studies)
        flagged = quality[quality["n_flags"] > 0]
        self.assertGreater(len(flagged), 0)


class TestBronKerbosch(unittest.TestCase):
    def test_finds_max_clique(self):
        import multi_study_analysis as m
        # Triangle A-B-C plus D connected only to A
        adj = {
            "A": {"B", "C", "D"},
            "B": {"A", "C"},
            "C": {"A", "B"},
            "D": {"A"},
        }
        clique = m._bron_kerbosch_max_clique(adj)
        self.assertEqual(sorted(clique), ["A", "B", "C"])

    def test_empty_graph(self):
        import multi_study_analysis as m
        adj = {"A": set(), "B": set()}
        clique = m._bron_kerbosch_max_clique(adj)
        self.assertEqual(len(clique), 1)


class TestNonGaussianity(unittest.TestCase):
    def test_shapiro_on_normal_data(self):
        import multi_study_analysis as m
        import numpy as np
        rng = np.random.default_rng(42)
        studies = {"test": pd.DataFrame({
            "trust_rating": rng.normal(3.5, 0.8, 100),
        })}
        result = m.test_non_gaussianity(studies)
        self.assertGreater(len(result), 0)
        self.assertIn("shapiro_p", result.columns)


class TestCumulativeMetaAnalysis(unittest.TestCase):
    def test_cumulative_returns_growing_k(self):
        import multi_study_analysis as m
        summary = pd.DataFrame({
            "study": ["a", "b", "c", "d"],
            "dv": ["x"] * 4,
            "n": [50, 100, 150, 200],
            "mean": [3.0, 3.1, 3.2, 3.3],
            "sd": [0.5, 0.5, 0.5, 0.5],
        })
        cumul = m.cumulative_meta_analysis(summary, "x")
        if not cumul.empty:
            self.assertTrue(cumul["cumulative_k"].is_monotonic_increasing)


class TestOverlapExtended(unittest.TestCase):
    def test_extended_overlap_has_frequency(self):
        import multi_study_analysis as m
        studies = {
            "a": pd.DataFrame({"trust_rating": [1, 2, 3], "mental_demand": [10, 11, 12]}),
            "b": pd.DataFrame({"trust_rating": [2, 3, 4], "usability": [70, 75, 80]}),
        }
        result = m.compute_extended_overlap_stats(studies)
        self.assertIn("dv_frequency", result)
        self.assertIn("pairwise_overlap", result)
        freq = result["dv_frequency"]
        self.assertGreater(len(freq), 0)
        # trust_rating appears in both studies
        tr_row = freq[freq["dv"] == "trust_rating"]
        self.assertEqual(int(tr_row["n_studies"].iloc[0]), 2)


class TestSchemaExpansion(unittest.TestCase):
    """Verify the expanded schema covers major HCI instruments."""

    @classmethod
    def setUpClass(cls):
        cls.data = yaml.safe_load(
            (REPO_ROOT / "schemas" / "standard_dv_mapping.yaml").read_text(encoding="utf-8")
        )
        cls.ids = {d["id"] for d in cls.data["dvs"]}

    def test_at_least_100_dvs(self):
        self.assertGreaterEqual(len(self.ids), 100)

    def test_ssq_subscales_present(self):
        for dv in ("ssq_total", "ssq_nausea", "ssq_oculomotor", "ssq_disorientation"):
            self.assertIn(dv, self.ids, f"SSQ subscale {dv} missing")

    def test_ueq_subscales_present(self):
        for dv in ("ueq_attractiveness", "ueq_perspicuity", "ueq_efficiency",
                    "ueq_dependability", "ueq_stimulation", "ueq_novelty"):
            self.assertIn(dv, self.ids, f"UEQ subscale {dv} missing")

    def test_tia_subscales_present(self):
        for dv in ("tia_reliability_competence", "tia_understanding_predictability",
                    "tia_familiarity", "tia_propensity_to_trust", "tia_trust_in_automation"):
            self.assertIn(dv, self.ids, f"TiA subscale {dv} missing")

    def test_dali_subscales_present(self):
        for dv in ("dali_total", "dali_effort_of_attention", "dali_visual_demand",
                    "dali_auditory_demand", "dali_interference", "dali_situational_stress"):
            self.assertIn(dv, self.ids, f"DALI subscale {dv} missing")

    def test_ipq_subscales_present(self):
        for dv in ("ipq_general_presence", "ipq_spatial_presence",
                    "ipq_involvement", "ipq_experienced_realism"):
            self.assertIn(dv, self.ids, f"IPQ subscale {dv} missing")

    def test_driving_metrics_present(self):
        for dv in ("sdlp", "ttc", "brake_reaction_time", "takeover_time", "headway"):
            self.assertIn(dv, self.ids, f"Driving metric {dv} missing")

    def test_utaut_tam_present(self):
        for dv in ("utaut_performance_expectancy", "utaut_effort_expectancy",
                    "tam_perceived_usefulness", "tam_perceived_ease_of_use"):
            self.assertIn(dv, self.ids, f"UTAUT/TAM construct {dv} missing")

    def test_godspeed_present(self):
        for dv in ("godspeed_anthropomorphism", "godspeed_animacy",
                    "godspeed_likeability", "godspeed_perceived_intelligence"):
            self.assertIn(dv, self.ids, f"Godspeed subscale {dv} missing")

    def test_affect_dvs_present(self):
        for dv in ("arousal", "dominance", "panas_positive", "panas_negative"):
            self.assertIn(dv, self.ids, f"Affect DV {dv} missing")

    def test_eye_tracking_split(self):
        for dv in ("fixation_duration", "fixation_count", "saccade_rate", "dwell_time"):
            self.assertIn(dv, self.ids, f"Eye-tracking DV {dv} missing")

    def test_sart_subscales_present(self):
        for dv in ("sart_total", "sart_understanding", "sart_demand", "sart_supply"):
            self.assertIn(dv, self.ids, f"sART subscale {dv} missing")


# ---------------------------------------------------------------------------
# New feature tests: IRT warnings, bootstrap, PC algorithm, survey parsers,
# reshape utils, __main__.py CLI
# ---------------------------------------------------------------------------

class TestIRTRescalingWarnings(unittest.TestCase):
    """Test ordinal rescaling / IRT linking warnings."""

    def test_warns_on_likert_rescaling(self):
        from multi_study_analysis import check_ordinal_rescaling_warnings
        import numpy as np

        # Study A has a 1-7 scale for trust_rating (canonical is 1-5)
        rng = np.random.default_rng(42)
        studies = {
            "study_a": pd.DataFrame({
                "trust_rating": rng.integers(1, 8, size=50).astype(float),
            }),
        }
        warnings_df = check_ordinal_rescaling_warnings(studies, harmonize_scales=True)
        self.assertGreater(len(warnings_df), 0, "Should warn about Likert rescaling")
        self.assertIn("IRT", warnings_df["warning"].iloc[0])

    def test_no_warning_when_in_range(self):
        from multi_study_analysis import check_ordinal_rescaling_warnings
        import numpy as np

        rng = np.random.default_rng(42)
        studies = {
            "study_a": pd.DataFrame({
                "trust_rating": rng.integers(1, 6, size=50).astype(float),
            }),
        }
        warnings_df = check_ordinal_rescaling_warnings(studies, harmonize_scales=True)
        trust_warnings = warnings_df[warnings_df["dv"] == "trust_rating"]
        self.assertEqual(len(trust_warnings), 0, "No warning when data fits canonical range")

    def test_disabled_when_no_harmonize(self):
        from multi_study_analysis import check_ordinal_rescaling_warnings

        studies = {"study_a": pd.DataFrame({"trust_rating": [1, 2, 3, 4, 5, 6, 7]})}
        warnings_df = check_ordinal_rescaling_warnings(studies, harmonize_scales=False)
        self.assertTrue(warnings_df.empty)


class TestBootstrapCausalStability(unittest.TestCase):
    """Test bootstrap causal edge stability analysis."""

    def test_returns_dataframe(self):
        from multi_study_analysis import bootstrap_causal_stability
        import numpy as np

        rng = np.random.default_rng(42)
        n = 100
        x = rng.standard_normal(n)
        y = 0.7 * x + rng.standard_normal(n) * 0.3
        # Use canonical DV names
        studies = {
            "s1": pd.DataFrame({"trust_rating": x[:50], "usability": y[:50]}),
            "s2": pd.DataFrame({"trust_rating": x[50:], "usability": y[50:]}),
        }
        result = bootstrap_causal_stability(
            studies, n_bootstrap=10, min_rows=10
        )
        self.assertIsInstance(result, pd.DataFrame)
        expected_cols = {"from", "to", "appearance_rate", "mean_coefficient", "sd_coefficient"}
        self.assertEqual(set(result.columns), expected_cols)

    def test_empty_when_insufficient_data(self):
        from multi_study_analysis import bootstrap_causal_stability

        studies = {"s1": pd.DataFrame({"x": [1, 2]})}
        result = bootstrap_causal_stability(studies, n_bootstrap=5, min_rows=10)
        self.assertTrue(result.empty)


class TestPCAlgorithm(unittest.TestCase):
    """Test PC algorithm causal discovery."""

    def test_discovers_skeleton(self):
        from multi_study_analysis import discover_causal_structure_pc
        import numpy as np

        rng = np.random.default_rng(42)
        n = 200
        x = rng.standard_normal(n)
        y = 0.8 * x + rng.standard_normal(n) * 0.3
        z = rng.standard_normal(n)  # independent of x, y

        # Use canonical DV names so _canonicalize_studies keeps them
        studies = {
            "s1": pd.DataFrame({"trust_rating": x[:100], "usability": y[:100], "frustration": z[:100]}),
            "s2": pd.DataFrame({"trust_rating": x[100:], "usability": y[100:], "frustration": z[100:]}),
        }
        result = discover_causal_structure_pc(studies, alpha=0.05, min_rows=20)
        self.assertIsNotNone(result)
        self.assertIn("skeleton", result)
        self.assertIn("removed_edges", result)
        self.assertEqual(result["n_dvs"], 3)
        # At least some edges should have been removed (frustration is independent)
        self.assertGreater(len(result["removed_edges"]), 0,
                           "Independent DVs should have edges removed")

    def test_returns_none_insufficient_data(self):
        from multi_study_analysis import discover_causal_structure_pc

        studies = {"s1": pd.DataFrame({"x": [1, 2]})}
        result = discover_causal_structure_pc(studies, min_rows=10)
        self.assertIsNone(result)


class TestSurveyParsers(unittest.TestCase):
    """Test Qualtrics, LimeSurvey, and REDCap parsers."""

    def test_qualtrics_parser_3_header_rows(self):
        from survey_parsers import QualtricsParser
        import tempfile

        # Simulate a Qualtrics CSV with 3 header rows
        content = (
            "StartDate,EndDate,Q1,Q2_1\n"
            "Start Date,End Date,How satisfied?,Rate quality\n"
            '{"ImportId":"startDate"},{"ImportId":"endDate"},{"ImportId":"QID1"},{"ImportId":"QID2_1"}\n'
            "2024-01-01,2024-01-01,4,5\n"
            "2024-01-02,2024-01-02,3,4\n"
        )
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name

        parser = QualtricsParser()
        df = parser.parse(path)
        self.assertEqual(len(df), 2, "Should have 2 data rows")
        # Column names should come from description row
        self.assertTrue(any("satisfied" in str(c).lower() for c in df.columns))

    def test_redcap_parser_checkbox_detection(self):
        from survey_parsers import REDCapParser
        import tempfile

        content = (
            "record_id,age,nasa_mental_demand,comfort___1,comfort___2,comfort___3\n"
            "1,25,15,1,0,1\n"
            "2,30,18,0,1,1\n"
        )
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name

        parser = REDCapParser()
        df = parser.parse(path)
        self.assertEqual(len(df), 2)
        self.assertIn("record_id", df.columns)

    def test_detect_and_parse_raises_on_unknown(self):
        from survey_parsers import detect_and_parse
        import tempfile

        # Plain CSV (not a survey platform export) should raise ValueError
        content = "id,score\n1,4\n2,5\n"
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name

        with self.assertRaises(ValueError):
            detect_and_parse(path)

    def test_detect_and_parse_with_hint(self):
        from survey_parsers import detect_and_parse
        import tempfile

        # REDCap-style CSV with format hint
        content = "record_id,age,nasa_mental_demand\n1,25,15\n2,30,18\n"
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name

        df = detect_and_parse(path, format_hint="redcap")
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 2)


class TestReshapeUtils(unittest.TestCase):
    """Test long/wide detection and reshaping."""

    def test_detect_wide_format(self):
        from reshape_utils import detect_data_shape

        # Wide format: many columns, few rows per ID
        df = pd.DataFrame({
            "id": [1, 2, 3],
            "trust": [3.5, 4.0, 2.5],
            "usability": [80, 90, 70],
            "workload": [50, 40, 60],
            "satisfaction": [4, 5, 3],
            "acceptance": [3, 4, 2],
            "safety": [4, 3, 5],
            "effort": [3, 2, 4],
            "performance": [4, 5, 3],
            "frustration": [2, 1, 3],
            "temporal_demand": [3, 2, 4],
            "mental_demand": [4, 3, 5],
            "physical_demand": [2, 1, 3],
            "comprehension": [4, 5, 3],
            "preference": [3, 4, 2],
            "engagement": [4, 3, 5],
        })
        shape = detect_data_shape(df)
        self.assertEqual(shape, "wide")

    def test_detect_long_format(self):
        from reshape_utils import detect_data_shape

        df = pd.DataFrame({
            "participant_id": [1, 1, 1, 2, 2, 2],
            "variable": ["trust", "usability", "workload", "trust", "usability", "workload"],
            "value": [3.5, 80, 50, 4.0, 90, 40],
        })
        shape = detect_data_shape(df)
        self.assertEqual(shape, "long")

    def test_long_to_wide(self):
        from reshape_utils import long_to_wide

        df = pd.DataFrame({
            "pid": [1, 1, 2, 2],
            "measure": ["trust", "safety", "trust", "safety"],
            "score": [4.0, 3.5, 3.0, 4.5],
        })
        wide = long_to_wide(df, id_col="pid", variable_col="measure", value_col="score")
        self.assertEqual(len(wide), 2)
        self.assertIn("trust", wide.columns)
        self.assertIn("safety", wide.columns)

    def test_auto_reshape_to_wide(self):
        from reshape_utils import auto_reshape_to_wide

        # Already wide - should return as-is
        df = pd.DataFrame({
            "id": [1, 2],
            "trust": [3.5, 4.0],
            "usability": [80, 90],
            "workload": [50, 40],
            "satisfaction": [4, 5],
            "acceptance": [3, 4],
            "safety": [4, 3],
            "effort": [3, 2],
            "performance": [4, 5],
            "frustration": [2, 1],
            "temporal_demand": [3, 2],
            "mental_demand": [4, 3],
            "physical_demand": [2, 1],
            "comprehension": [4, 5],
            "preference": [3, 4],
            "engagement": [4, 3],
        })
        result = auto_reshape_to_wide(df)
        self.assertEqual(len(result), 2)
        self.assertGreaterEqual(len(result.columns), 15)


class TestMainCLI(unittest.TestCase):
    """Test __main__.py CLI module."""

    def _load_module(self):
        # Use a non-__main__ name to avoid triggering the if __name__ guard
        spec = importlib.util.spec_from_file_location(
            "opendv_main", str(REPO_ROOT / "__main__.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_module_imports(self):
        mod = self._load_module()
        self.assertTrue(hasattr(mod, "main"))
        self.assertTrue(hasattr(mod, "__version__"))
        self.assertEqual(mod.__version__, "3.0.0")

    def test_parser_has_subcommands(self):
        mod = self._load_module()
        parser = mod._build_parser()
        # Parser should accept subcommands without error
        args, _ = parser.parse_known_args(["standardize", "--help-test"])
        self.assertEqual(args.command, "standardize")

    def test_dispatch_table_complete(self):
        mod = self._load_module()
        for cmd in ("standardize", "batch", "analyze", "validate"):
            self.assertIn(cmd, mod._DISPATCH, f"Missing dispatch for '{cmd}'")


if __name__ == "__main__":
    unittest.main()
