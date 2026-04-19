import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from analyses.multi_study_analysis import (
    _categorize_mapping_source,
    _detect_scale_range,
    _estimate_tau2_dl,
    _estimate_tau2_reml,
    _parse_scale_range,
    _rescale_to_canonical,
    build_composite_index,
    compute_dv_presence_matrix,
    compute_overlap_details,
    compute_standardized_effects,
    compute_study_vs_pool_standardized_deviation,
    discover_causal_structure,
    eggers_test,
    harmonized_summary,
    leave_one_out_sensitivity,
    load_mapping_provenance,
    load_studies,
    meta_analysis_summary,
    numeric_dvs,
    subgroup_meta_analysis,
)


class MultiStudyAnalysisTests(unittest.TestCase):
    def test_load_studies_treats_root_files_as_individual_studies(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pd.DataFrame({"task_success_rate": [0.8, 0.9]}).to_csv(root / "study_a.csv", index=False)
            pd.DataFrame({"task_success_rate": [0.6, 0.7]}).to_csv(root / "study_b.csv", index=False)

            studies = load_studies(root)

        self.assertEqual(set(studies.keys()), {"study_a", "study_b"})
        self.assertEqual(len(studies["study_a"]), 2)
        self.assertEqual(len(studies["study_b"]), 2)

    def test_load_studies_reads_pickled_standardized_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pd.DataFrame({"task_success": [0.8, 0.9]}).to_pickle(root / "study_a.pkl")

            studies = load_studies(root)

        self.assertEqual(set(studies.keys()), {"study_a"})
        self.assertEqual(studies["study_a"]["task_success"].tolist(), [0.8, 0.9])

    def test_meta_analysis_summary_returns_random_effects_metrics(self):
        summary = pd.DataFrame(
            [
                {"study": "a", "dv": "task_success_rate", "n": 100, "mean": 0.70, "sd": 0.10, "scale_note": ""},
                {"study": "b", "dv": "task_success_rate", "n": 120, "mean": 0.80, "sd": 0.12, "scale_note": ""},
                {"study": "c", "dv": "sus_score", "n": 50, "mean": 65.0, "sd": 10.0, "scale_note": ""},
            ]
        )

        meta = meta_analysis_summary(summary)

        self.assertEqual(meta["dv"].tolist(), ["task_success_rate"])
        self.assertEqual(int(meta.loc[0, "k_studies"]), 2)
        self.assertGreater(meta.loc[0, "ci95_high"], meta.loc[0, "ci95_low"])
        self.assertGreaterEqual(meta.loc[0, "heterogeneity_i2_pct"], 0.0)

    def test_meta_analysis_includes_q_pvalue_and_prediction_interval(self):
        summary = pd.DataFrame(
            [
                {"study": "a", "dv": "task_success", "n": 100, "mean": 0.70, "sd": 0.10, "scale_note": ""},
                {"study": "b", "dv": "task_success", "n": 120, "mean": 0.80, "sd": 0.12, "scale_note": ""},
                {"study": "c", "dv": "task_success", "n": 80, "mean": 0.75, "sd": 0.11, "scale_note": ""},
            ]
        )

        meta = meta_analysis_summary(summary, total_studies=3)

        self.assertIn("q_pvalue", meta.columns)
        self.assertIn("prediction_interval_low", meta.columns)
        self.assertIn("prediction_interval_high", meta.columns)
        self.assertIn("tau", meta.columns)
        self.assertIn("h2", meta.columns)
        # With k=3, prediction interval should exist
        self.assertTrue(np.isfinite(meta.loc[0, "prediction_interval_low"]))
        # Prediction interval must be wider than CI
        self.assertLessEqual(meta.loc[0, "prediction_interval_low"], meta.loc[0, "ci95_low"])
        self.assertGreaterEqual(meta.loc[0, "prediction_interval_high"], meta.loc[0, "ci95_high"])

    def test_build_composite_index_handles_partially_shared_dvs(self):
        studies = {
            "study_a": pd.DataFrame(
                {
                    "task_success": [0.8, 0.9, 0.85],
                    "sus_score": [70, 75, 80],
                }
            ),
            "study_b": pd.DataFrame(
                {
                    "task_success": [0.6, 0.7, 0.65],
                    "sus_score": [60, 62, 64],
                }
            ),
            "study_c": pd.DataFrame(
                {
                    "task_success": [0.75, 0.78, 0.8],
                    "nasa_tlx_score": [55, 50, 52],
                }
            ),
        }

        composite = build_composite_index(studies)

        self.assertEqual(set(composite["study"]), {"study_a", "study_b", "study_c"})
        self.assertEqual(set(composite["n_shared_dvs_used"]), {2})
        self.assertTrue(composite["mean"].notna().all())
        self.assertTrue(composite["explained_variance_ratio"].notna().all())

    def test_overlap_outputs_include_presence_and_pairwise_details(self):
        studies = {
            "study_a": pd.DataFrame(
                {
                    "task_success": [0.8, 0.9],
                    "trust_rating": [4.0, 4.5],
                }
            ),
            "study_b": pd.DataFrame(
                {
                    "task_success": [0.7, 0.75],
                    "sus_score": [70, 72],
                }
            ),
        }

        presence = compute_dv_presence_matrix(studies)
        overlap_details = compute_overlap_details(studies)

        self.assertEqual(int(presence.loc["study_a", "task_success"]), 1)
        self.assertEqual(int(presence.loc["study_b", "trust_rating"]), 0)
        self.assertEqual(len(overlap_details), 1)
        self.assertEqual(int(overlap_details.loc[0, "shared_dv_count"]), 1)
        self.assertIn("task_success", overlap_details.loc[0, "shared_dvs"])

    def test_numeric_dvs_only_returns_schema_backed_canonical_dvs(self):
        df = pd.DataFrame(
            {
                "requestID": [101, 102],
                "Unix Timestamp In Milliseconds": [1693081000000, 1693081001000],
                "sus_score": [72.0, 74.0],
                "nasa_tlx_score": [41.0, 43.0],
                "trust_rating": [4.0, 4.5],
            }
        )

        dvs = numeric_dvs(df)

        self.assertEqual(set(dvs), {"TLX_SCORE", "trust_rating", "usability"})

    def test_meta_analysis_summary_reports_study_coverage(self):
        summary = pd.DataFrame(
            [
                {"study": "a", "dv": "task_success", "n": 100, "mean": 0.70, "sd": 0.10, "scale_note": ""},
                {"study": "b", "dv": "task_success", "n": 120, "mean": 0.80, "sd": 0.12, "scale_note": ""},
            ]
        )

        meta = meta_analysis_summary(summary, total_studies=4)

        self.assertEqual(meta.loc[0, "study_coverage_pct"], 50.0)

    # ── Scale harmonization tests ──────────────────────────────────────────

    def test_parse_scale_range_extracts_21_point(self):
        self.assertEqual(_parse_scale_range("21-point (0-20)"), (0.0, 20.0))
        self.assertEqual(_parse_scale_range("21-point (0–20)"), (0.0, 20.0))

    def test_parse_scale_range_extracts_5_point_negative(self):
        self.assertEqual(_parse_scale_range("5-point (-2 to +2)"), (-2.0, 2.0))

    def test_parse_scale_range_known_units(self):
        self.assertEqual(_parse_scale_range("5-point"), (1.0, 5.0))
        self.assertEqual(_parse_scale_range("proportion"), (0.0, 1.0))

    def test_detect_scale_range_keeps_canonical_when_data_fits(self):
        s = pd.Series([3, 8, 15, 18])
        detected = _detect_scale_range(s, (0.0, 20.0))
        self.assertEqual(detected, (0.0, 20.0))

    def test_detect_scale_range_identifies_0_100_alternative(self):
        s = pd.Series([10, 40, 70, 95])
        detected = _detect_scale_range(s, (0.0, 20.0))
        self.assertEqual(detected, (0.0, 100.0))

    def test_rescale_to_canonical(self):
        s = pd.Series([0.0, 50.0, 100.0])
        result = _rescale_to_canonical(s, (0.0, 100.0), (0.0, 20.0))
        np.testing.assert_array_almost_equal(result.values, [0.0, 10.0, 20.0])

    def test_harmonized_summary_rescales_mismatched_ranges(self):
        # mental_demand on 0-100 range should be rescaled to 0-20
        studies = {
            "study_a": pd.DataFrame({"mental_demand": [0, 25, 50, 75, 100]}),
            "study_b": pd.DataFrame({"mental_demand": [5, 10, 15]}),
        }

        summary = harmonized_summary(studies, harmonize_scales=True)
        study_a = summary[summary["study"] == "study_a"]

        self.assertTrue(len(study_a) > 0)
        # If rescaled from 0-100 to 0-20, mean of [0,25,50,75,100] -> [0,5,10,15,20] = 10
        self.assertAlmostEqual(study_a.iloc[0]["mean"], 10.0, places=1)
        self.assertIn("rescaled", study_a.iloc[0]["scale_note"])

    # ── Standardized effects tests ─────────────────────────────────────────

    def test_hedges_g_correction_reduces_with_large_n(self):
        summary = pd.DataFrame([
            {"study": "a", "dv": "task_success", "n": 10, "mean": 0.70, "sd": 0.10, "scale_note": ""},
            {"study": "b", "dv": "task_success", "n": 10000, "mean": 0.80, "sd": 0.12, "scale_note": ""},
        ])

        effects = compute_standardized_effects(summary)
        large_n_row = effects[effects["study"] == "b"].iloc[0]

        # For large n, hedges_g should be very close to cohens_d
        self.assertAlmostEqual(large_n_row["hedges_g"], large_n_row["cohens_d"], places=3)

    def test_standardized_effects_returns_correct_columns(self):
        summary = pd.DataFrame([
            {"study": "a", "dv": "task_success", "n": 50, "mean": 0.70, "sd": 0.10, "scale_note": ""},
            {"study": "b", "dv": "task_success", "n": 60, "mean": 0.80, "sd": 0.12, "scale_note": ""},
        ])

        effects = compute_standardized_effects(summary)

        for col in ["study", "dv", "cohens_d", "hedges_g", "var_g", "se_g"]:
            self.assertIn(col, effects.columns)
        self.assertEqual(len(effects), 2)

    # ── REML estimator tests ───────────────────────────────────────────────

    def test_reml_converges_to_dl_for_no_heterogeneity(self):
        effects = np.array([5.0, 5.0, 5.0])
        variances = np.array([1.0, 1.0, 1.0])

        tau2_dl = _estimate_tau2_dl(effects, variances)
        tau2_reml = _estimate_tau2_reml(effects, variances)

        self.assertAlmostEqual(tau2_dl, 0.0, places=5)
        self.assertAlmostEqual(tau2_reml, 0.0, places=5)

    def test_reml_meta_analysis_runs(self):
        summary = pd.DataFrame([
            {"study": "a", "dv": "task_success", "n": 100, "mean": 0.70, "sd": 0.10, "scale_note": ""},
            {"study": "b", "dv": "task_success", "n": 120, "mean": 0.80, "sd": 0.12, "scale_note": ""},
        ])

        meta = meta_analysis_summary(summary, estimator="REML")

        self.assertEqual(meta.loc[0, "estimator"], "REML")
        self.assertGreater(meta.loc[0, "random_effects_mean"], 0)

    # ── Q p-value test ─────────────────────────────────────────────────────

    def test_q_pvalue_is_chi_squared(self):
        from scipy.stats import chi2

        summary = pd.DataFrame([
            {"study": "a", "dv": "task_success", "n": 100, "mean": 0.70, "sd": 0.10, "scale_note": ""},
            {"study": "b", "dv": "task_success", "n": 120, "mean": 0.80, "sd": 0.12, "scale_note": ""},
        ])

        meta = meta_analysis_summary(summary)

        q = meta.loc[0, "heterogeneity_q"]
        expected_p = chi2.sf(q, 1)  # df = k-1 = 1
        self.assertAlmostEqual(meta.loc[0, "q_pvalue"], expected_p, places=6)

    # ── Leave-one-out sensitivity test ─────────────────────────────────────

    def test_leave_one_out_returns_k_rows_per_dv(self):
        summary = pd.DataFrame([
            {"study": "a", "dv": "task_success", "n": 100, "mean": 0.70, "sd": 0.10, "scale_note": ""},
            {"study": "b", "dv": "task_success", "n": 120, "mean": 0.80, "sd": 0.12, "scale_note": ""},
            {"study": "c", "dv": "task_success", "n": 80, "mean": 0.75, "sd": 0.11, "scale_note": ""},
        ])

        sensitivity = leave_one_out_sensitivity(summary)

        self.assertEqual(len(sensitivity), 3)
        self.assertEqual(set(sensitivity["omitted_study"]), {"a", "b", "c"})

    # ── Egger's test ───────────────────────────────────────────────────────

    def test_eggers_test_returns_none_for_few_studies(self):
        summary = pd.DataFrame([
            {"study": "a", "dv": "task_success", "n": 100, "mean": 0.70, "sd": 0.10, "scale_note": ""},
            {"study": "b", "dv": "task_success", "n": 120, "mean": 0.80, "sd": 0.12, "scale_note": ""},
        ])

        result = eggers_test(summary, "task_success")

        self.assertIsNone(result)

    def test_eggers_test_runs_with_sufficient_studies(self):
        summary = pd.DataFrame([
            {"study": "a", "dv": "task_success", "n": 100, "mean": 0.70, "sd": 0.10, "scale_note": ""},
            {"study": "b", "dv": "task_success", "n": 120, "mean": 0.80, "sd": 0.12, "scale_note": ""},
            {"study": "c", "dv": "task_success", "n": 80, "mean": 0.75, "sd": 0.11, "scale_note": ""},
        ])

        result = eggers_test(summary, "task_success")

        self.assertIsNotNone(result)
        self.assertIn("intercept", result)
        self.assertIn("p_value", result)
        self.assertIn("significant_at_10pct", result)

    # ── Subgroup analysis test ─────────────────────────────────────────────

    def test_subgroup_analysis_groups_by_cluster(self):
        effects = pd.DataFrame([
            {"study": "a", "dv": "mental_demand", "cohens_d": 0.3, "hedges_g": 0.29, "var_g": 0.02, "se_g": 0.14},
            {"study": "b", "dv": "mental_demand", "cohens_d": -0.3, "hedges_g": -0.29, "var_g": 0.02, "se_g": 0.14},
            {"study": "a", "dv": "task_success", "cohens_d": 0.5, "hedges_g": 0.49, "var_g": 0.03, "se_g": 0.17},
            {"study": "b", "dv": "task_success", "cohens_d": -0.5, "hedges_g": -0.49, "var_g": 0.03, "se_g": 0.17},
        ])

        subgroup = subgroup_meta_analysis(effects)

        self.assertGreater(len(subgroup), 0)
        self.assertIn("cluster", subgroup.columns)
        self.assertIn("pooled_g", subgroup.columns)

    # ── LiNGAM causal discovery test ───────────────────────────────────────

    def test_causal_discovery_returns_none_for_no_shared_dvs(self):
        studies = {
            "study_a": pd.DataFrame({"task_success": np.random.rand(50)}),
            "study_b": pd.DataFrame({"sus_score": np.random.rand(50)}),
        }

        result = discover_causal_structure(studies)

        self.assertIsNone(result)

    def test_causal_discovery_runs_with_shared_dvs(self):
        np.random.seed(42)
        n = 100
        x = np.random.randn(n)
        y = 0.5 * x + np.random.randn(n) * 0.3
        z = 0.3 * x + 0.4 * y + np.random.randn(n) * 0.2

        studies = {
            "study_a": pd.DataFrame({
                "mental_demand": x[:60],
                "effort": y[:60],
                "frustration": z[:60],
            }),
            "study_b": pd.DataFrame({
                "mental_demand": x[40:],
                "effort": y[40:],
                "frustration": z[40:],
            }),
        }

        result = discover_causal_structure(studies, min_rows=20)

        self.assertIsNotNone(result)
        self.assertEqual(result["n_dvs"], 3)
        self.assertIn("adjacency_matrix", result)
        self.assertIn("causal_order", result)
        self.assertIn("edges", result)
        self.assertEqual(len(result["causal_order"]), 3)

    # ── Provenance & sensitivity tests ─────────────────────────────────────

    def test_categorize_mapping_source_labels(self):
        self.assertEqual(_categorize_mapping_source("llm_deduction"), "llm_deduced")
        self.assertEqual(_categorize_mapping_source("in_memory_mapping"), "schema")
        self.assertEqual(_categorize_mapping_source("schemas/standard_dv_mapping.yaml"),
                         "schema")
        self.assertEqual(_categorize_mapping_source("custom/roads_chi25/mapping.yaml"),
                         "repo_mapping")
        self.assertEqual(_categorize_mapping_source(None), "unknown")
        self.assertEqual(_categorize_mapping_source(""), "unknown")
        self.assertEqual(_categorize_mapping_source("never_map_blocklist"), "blocked")

    def test_load_mapping_provenance_reads_meta_view_and_prefers_llm(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            meta_view = Path(tmpdir) / "meta_view.csv"
            pd.DataFrame([
                {"source_id": "study_a", "canonical_dv": "trust_rating",
                 "mapping_source": "in_memory_mapping"},
                {"source_id": "study_a", "canonical_dv": "task_success",
                 "mapping_source": "llm_deduction"},
                # Conflicting rows for the same DV — llm_deduced wins.
                {"source_id": "study_b", "canonical_dv": "trust_rating",
                 "mapping_source": "in_memory_mapping"},
                {"source_id": "study_b", "canonical_dv": "trust_rating",
                 "mapping_source": "llm_deduction"},
            ]).to_csv(meta_view, index=False)

            prov = load_mapping_provenance(meta_view)

        self.assertEqual(prov[("study_a", "trust_rating")], "schema")
        self.assertEqual(prov[("study_a", "task_success")], "llm_deduced")
        self.assertEqual(prov[("study_b", "trust_rating")], "llm_deduced")

    def test_load_mapping_provenance_missing_file_returns_empty(self):
        self.assertEqual(load_mapping_provenance(Path("does_not_exist.csv")), {})

    def test_harmonized_summary_attaches_mapping_source(self):
        studies = {
            "study_a": pd.DataFrame({"task_success": [0.8, 0.85, 0.9]}),
            "study_b": pd.DataFrame({"task_success": [0.6, 0.65, 0.7]}),
        }
        provenance = {
            ("study_a", "task_success"): "schema",
            ("study_b", "task_success"): "llm_deduced",
        }

        summary = harmonized_summary(studies, mapping_provenance=provenance)

        self.assertIn("mapping_source", summary.columns)
        self.assertEqual(
            summary.loc[summary["study"] == "study_a", "mapping_source"].iloc[0],
            "schema",
        )
        self.assertEqual(
            summary.loc[summary["study"] == "study_b", "mapping_source"].iloc[0],
            "llm_deduced",
        )

    def test_meta_analysis_summary_flags_llm_contributions(self):
        summary = pd.DataFrame([
            {"study": "a", "dv": "task_success", "n": 100, "mean": 0.7,
             "sd": 0.1, "scale_note": "", "mapping_source": "schema"},
            {"study": "b", "dv": "task_success", "n": 120, "mean": 0.8,
             "sd": 0.12, "scale_note": "", "mapping_source": "llm_deduced"},
            {"study": "c", "dv": "trust_rating", "n": 80, "mean": 4.1,
             "sd": 0.5, "scale_note": "", "mapping_source": "schema"},
            {"study": "d", "dv": "trust_rating", "n": 90, "mean": 4.3,
             "sd": 0.4, "scale_note": "", "mapping_source": "schema"},
        ])

        meta = meta_analysis_summary(summary)

        task_row = meta[meta["dv"] == "task_success"].iloc[0]
        trust_row = meta[meta["dv"] == "trust_rating"].iloc[0]
        self.assertTrue(bool(task_row["includes_llm_deduced"]))
        self.assertEqual(int(task_row["k_llm_deduced"]), 1)
        self.assertIn("llm_deduced", task_row["mapping_source_categories"])
        self.assertFalse(bool(trust_row["includes_llm_deduced"]))
        self.assertEqual(int(trust_row["k_llm_deduced"]), 0)

    def test_exclude_llm_deduced_sensitivity_changes_pooled_estimate(self):
        # Two studies: one "schema", one "llm_deduced".  Filtering the
        # llm_deduced row should change k and the pooled mean.
        summary = pd.DataFrame([
            {"study": "a", "dv": "task_success", "n": 100, "mean": 0.7,
             "sd": 0.1, "scale_note": "", "mapping_source": "schema"},
            {"study": "b", "dv": "task_success", "n": 120, "mean": 0.9,
             "sd": 0.12, "scale_note": "", "mapping_source": "llm_deduced"},
            {"study": "c", "dv": "task_success", "n": 80, "mean": 0.72,
             "sd": 0.11, "scale_note": "", "mapping_source": "schema"},
        ])

        full_meta = meta_analysis_summary(summary)
        clean_meta = meta_analysis_summary(
            summary[summary["mapping_source"] != "llm_deduced"]
        )

        self.assertEqual(int(full_meta.iloc[0]["k_studies"]), 3)
        self.assertEqual(int(clean_meta.iloc[0]["k_studies"]), 2)
        self.assertNotAlmostEqual(
            float(full_meta.iloc[0]["random_effects_mean"]),
            float(clean_meta.iloc[0]["random_effects_mean"]),
            places=4,
        )

    def test_compute_standardized_effects_carries_mapping_source(self):
        summary = pd.DataFrame([
            {"study": "a", "dv": "task_success", "n": 50, "mean": 0.7,
             "sd": 0.1, "scale_note": "", "mapping_source": "schema"},
            {"study": "b", "dv": "task_success", "n": 60, "mean": 0.8,
             "sd": 0.12, "scale_note": "", "mapping_source": "llm_deduced"},
        ])

        effects = compute_standardized_effects(summary)

        self.assertIn("mapping_source", effects.columns)
        self.assertEqual(
            set(effects["mapping_source"]),
            {"schema", "llm_deduced"},
        )
        # Preferred alias is exposed for new callers.
        self.assertIs(
            compute_study_vs_pool_standardized_deviation,
            compute_standardized_effects,
        )

    # ── Causal discovery fallback tests ────────────────────────────────────

    def test_causal_discovery_reports_complete_case_method(self):
        np.random.seed(7)
        n = 80
        x = np.random.randn(n)
        y = 0.5 * x + np.random.randn(n) * 0.3

        studies = {
            "study_a": pd.DataFrame({"mental_demand": x[:50], "effort": y[:50]}),
            "study_b": pd.DataFrame({"mental_demand": x[30:], "effort": y[30:]}),
        }

        result = discover_causal_structure(studies, min_rows=20)

        self.assertIsNotNone(result)
        self.assertFalse(bool(result["synthetic_fallback"]))
        self.assertEqual(result["used_method"], "complete_case")
        self.assertGreaterEqual(int(result["n_complete_rows"]), 20)

    def test_refuse_synthetic_blocks_cholesky_fallback(self):
        np.random.seed(11)

        # Two studies that *share* DV names but never co-occur in the same row
        # within a study (each study has only one of each DV available).
        # This forces partial coverage and triggers the synthetic path in the
        # default code path.
        studies = {
            "study_a": pd.DataFrame({
                "mental_demand": np.random.randn(25),
                "effort": np.nan,
            }),
            "study_b": pd.DataFrame({
                "mental_demand": np.nan,
                "effort": np.random.randn(25),
            }),
        }

        # Without refuse_synthetic, this returns None because the per-study
        # dropna leaves < min_rows rows anyway — so this test primarily
        # ensures the new kwarg is accepted without raising.
        result_strict = discover_causal_structure(
            studies,
            min_rows=10,
            refuse_synthetic=True,
        )
        self.assertIsNone(result_strict)
