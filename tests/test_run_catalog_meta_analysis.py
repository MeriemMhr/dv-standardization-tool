import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from scripts.run_catalog_meta_analysis import (
    build_sources_from_catalog,
    run_catalog_meta_analysis,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CATALOG_PATH = REPO_ROOT / "data" / "raw" / "study_catalog_example.csv"


class CatalogMetaAnalysisTests(unittest.TestCase):
    def test_example_catalog_includes_new_supported_sources(self):
        catalog = pd.read_csv(EXAMPLE_CATALOG_PATH)

        self.assertIn(
            "https://github.com/interactionlab/Touch-Interaction-with-Road-Bumps/tree/master/data",
            catalog["dataset_url"].tolist(),
        )
        self.assertIn(
            "https://data.4tu.nl/articles/_/20224281",
            catalog["dataset_url"].tolist(),
        )
        self.assertIn(
            "https://dl.acm.org/doi/suppl/10.1145/3772318.3790738/suppl_file/"
            "3772318.3790738-supplemental-material-1.zip",
            catalog["dataset_url"].tolist(),
        )

    def test_build_sources_from_catalog_deduplicates_locations(self):
        catalog = pd.DataFrame(
            [
                {"dataset_url": "https://github.com/example/study-a", "note": "row1"},
                {"dataset_url": "https://github.com/example/study-a", "note": "row2"},
                {"dataset_url": "https://osf.io/cwd6h/overview", "note": "row3"},
            ]
        )

        sources, source_summary = build_sources_from_catalog(catalog, url_column="dataset_url")

        self.assertEqual(len(sources), 2)
        self.assertEqual(source_summary["catalog_row_count"].tolist(), [2, 1])
        self.assertEqual(sources[0]["source_type"], "github_repo")
        self.assertEqual(sources[1]["source_type"], "osf_project")

    def test_build_sources_from_catalog_infers_web_dataset_sources(self):
        catalog = pd.DataFrame(
            [
                {"dataset_url": "https://data.4tu.nl/articles/_/20224281"},
                {"dataset_url": "https://ieee-dataport.org/open-access/usyd-campus-dataset"},
            ]
        )

        sources, _ = build_sources_from_catalog(catalog, url_column="dataset_url")

        self.assertEqual([source["source_type"] for source in sources], ["web_dataset", "web_dataset"])

    def test_run_catalog_meta_analysis_runs_mapping_and_overlap_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            study_a_dir = tmp / "study_a"
            study_b_dir = tmp / "study_b"
            study_a_dir.mkdir()
            study_b_dir.mkdir()

            pd.DataFrame(
                {
                    "success_rate": [0.80, 0.85, 0.90],
                    "trust_rating": [4.0, 4.2, 4.5],
                }
            ).to_csv(study_a_dir / "results.csv", index=False)
            pd.DataFrame(
                {
                    "task_success_ratio": [0.60, 0.65, 0.70],
                    "trust_rating": [3.8, 4.0, 4.1],
                }
            ).to_csv(study_b_dir / "results.csv", index=False)

            catalog_path = tmp / "catalog.csv"
            pd.DataFrame(
                [
                    {
                        "dataset_url": str(study_a_dir),
                        "source_type": "local_path",
                        "study_name": "study_a",
                        "tag": "automated-driving",
                    },
                    {
                        "dataset_url": str(study_a_dir),
                        "source_type": "local_path",
                        "study_name": "study_a",
                        "tag": "trust",
                    },
                    {
                        "dataset_url": str(study_b_dir),
                        "source_type": "local_path",
                        "study_name": "study_b",
                        "tag": "automated-driving",
                    },
                ]
            ).to_csv(catalog_path, index=False)

            output_dir = tmp / "output"
            with mock.patch("scripts.run_catalog_meta_analysis.save_plots"):
                with mock.patch("scripts.run_catalog_meta_analysis.save_composite_plot"):
                    summary = run_catalog_meta_analysis(
                        catalog_path=catalog_path,
                        url_column="dataset_url",
                        output_dir=output_dir,
                        source_id_column="study_name",
                        source_type_column="source_type",
                        context_columns=["tag"],
                        llm_deduction_enabled=False,
                    )

            self.assertEqual(summary["n_unique_sources"], 2)
            self.assertEqual(summary["n_loaded_studies"], 2)

            manifest_path = output_dir / "generated_sources_manifest.yaml"
            source_summary_path = output_dir / "catalog_source_summary.csv"
            analysis_summary_path = output_dir / "analysis" / "analysis_summary.json"
            overlap_details_path = output_dir / "analysis" / "dv_overlap_details.csv"
            presence_path = output_dir / "analysis" / "dv_presence_matrix.csv"
            meta_path = output_dir / "analysis" / "meta_analysis_summary.csv"

            self.assertTrue(manifest_path.exists())
            self.assertTrue(source_summary_path.exists())
            self.assertTrue(analysis_summary_path.exists())
            self.assertTrue(overlap_details_path.exists())
            self.assertTrue(presence_path.exists())
            self.assertTrue(meta_path.exists())

            standardized_a = output_dir / "standardized" / "study_a" / "results_csv-standardized.csv"
            standardized_b = output_dir / "standardized" / "study_b" / "results_csv-standardized.csv"
            self.assertTrue(standardized_a.exists())
            self.assertTrue(standardized_b.exists())

            standardized_a_df = pd.read_csv(standardized_a)
            standardized_b_df = pd.read_csv(standardized_b)
            self.assertIn("task_success", standardized_a_df.columns)
            self.assertIn("trust_rating", standardized_a_df.columns)
            self.assertIn("task_success", standardized_b_df.columns)
            self.assertIn("trust_rating", standardized_b_df.columns)

            source_summary_df = pd.read_csv(source_summary_path)
            self.assertEqual(
                int(source_summary_df.loc[source_summary_df["source_id"] == "study_a", "catalog_row_count"].iloc[0]),
                2,
            )

            overlap_details = pd.read_csv(overlap_details_path)
            self.assertEqual(len(overlap_details), 1)
            self.assertEqual(int(overlap_details.loc[0, "shared_dv_count"]), 2)
            self.assertAlmostEqual(float(overlap_details.loc[0, "jaccard_overlap"]), 1.0)
            self.assertIn("task_success", overlap_details.loc[0, "shared_dvs"])
            self.assertIn("trust_rating", overlap_details.loc[0, "shared_dvs"])

            presence = pd.read_csv(presence_path, index_col=0)
            self.assertEqual(int(presence.loc["study_a", "task_success"]), 1)
            self.assertEqual(int(presence.loc["study_b", "trust_rating"]), 1)

            meta = pd.read_csv(meta_path)
            self.assertEqual(set(meta["dv"]), {"task_success", "trust_rating"})
            self.assertTrue((meta["study_coverage_pct"] == 100.0).all())

            analysis_summary = json.loads(analysis_summary_path.read_text(encoding="utf-8"))
            self.assertEqual(analysis_summary["n_unique_sources"], 2)
            self.assertEqual(analysis_summary["overlap_pair_count"], 1)

    def test_run_catalog_meta_analysis_records_unavailable_source_statuses(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            catalog_path = tmp / "catalog.csv"
            pd.DataFrame(
                [
                    {"dataset_url": "https://data.4tu.nl/articles/_/20224281"},
                ]
            ).to_csv(catalog_path, index=False)

            output_dir = tmp / "output"
            mocked_batch_summary = {
                "results": [
                    {
                        "source_id": "data_4tu_nl_20224281",
                        "status": "not_available",
                        "message": "No downloadable dataset files were detected.",
                        "discovered_files": 0,
                        "processed_files": 0,
                        "failed_files": 0,
                        "unknown_columns": 0,
                        "total_columns": 0,
                        "mapped_columns": 0,
                        "mapped_ratio": 0.0,
                        "output_dir": str(output_dir / "standardized" / "data_4tu_nl_20224281"),
                    }
                ]
            }

            with mock.patch("scripts.run_catalog_meta_analysis.run_batch", return_value=mocked_batch_summary):
                with mock.patch(
                    "scripts.run_catalog_meta_analysis.load_studies",
                    side_effect=FileNotFoundError("No CSV/XLSX/PKL files found in standardized output"),
                ):
                    summary = run_catalog_meta_analysis(
                        catalog_path=catalog_path,
                        url_column="dataset_url",
                        output_dir=output_dir,
                        llm_deduction_enabled=False,
                    )

            source_summary = pd.read_csv(output_dir / "catalog_source_summary.csv")
            self.assertEqual(source_summary.loc[0, "batch_status"], "not_available")
            self.assertIn("No downloadable dataset files were detected", source_summary.loc[0, "batch_message"])
            self.assertEqual(summary["n_loaded_studies"], 0)
            self.assertIn("analysis_skipped_reason", summary)


if __name__ == "__main__":
    unittest.main()
