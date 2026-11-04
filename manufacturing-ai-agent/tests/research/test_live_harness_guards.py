import asyncio
import os
import subprocess
import sys
from unittest.mock import patch
from research.harry_milestone.fixtures import build
from research.harry_milestone.evaluation import freeze, live_evaluation
from research.harry_milestone.agent import LivePermit, ResearchAgent


def test_mocked_harness_retains_all_failed_attempts_and_correct_denominators(tmp_path):
    build(tmp_path / "sample_a.db")
    build(tmp_path / "sample_b.db", "B")
    manifest = tmp_path / "manifest.json"
    freeze(tmp_path, manifest)

    async def failed(*args, **kwargs):
        return dict(
            status="failed", error_type="SyntheticFailure", trace=[], seconds=0.001
        )

    with (
        patch.object(ResearchAgent, "run", side_effect=failed),
        patch("openai.AsyncOpenAI") as client,
    ):
        report = asyncio.run(
            live_evaluation(
                tmp_path,
                manifest,
                LivePermit(2, allow_external=True),
                tmp_path / "mocked-harness-output",
            )
        )
        client.assert_not_called()
    assert (
        report["attempted_trials"] == 78
        and report["metrics"]["end_to_end"]["correct"] == 0
    )
    assert report["metrics"]["tool_selection"]["applicable"] == 66
    assert report["metrics"]["clarification"]["applicable"] == 12
    assert report["metrics"]["numerical_given_correct_arguments"]["applicable"] == 0
    assert report["missing_attempts"] == 0 and report["manual_review"] == "not reviewed"
    assert (
        len((tmp_path / "mocked-harness-output/trials.jsonl").read_text().splitlines())
        == 78
    )


def test_live_cli_requires_both_approval_flags_before_any_request_or_output(tmp_path):
    destination = tmp_path / "not-created"
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "research.harry_milestone.evaluation",
            "--mode",
            "live",
            "--data-dir",
            str(tmp_path),
            "--output",
            str(destination),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2 and "--allow-paid" in result.stderr
    assert not destination.exists()


def test_dashboard_baseline_in_a_new_process_never_reaches_dotenv_file_loader(tmp_path):
    build(tmp_path / "sample_a.db")
    code = """
import sys
from unittest.mock import patch
from pathlib import Path
from research.harry_milestone.tools import DataSource
from research.harry_milestone.evaluation import dashboard_comparison, comparison_queries
source = DataSource(Path(sys.argv[1]), "synthetic")
with patch("dotenv.main.DotEnv.dict", side_effect=AssertionError("Private dotenv loader reached")):
    report = dashboard_comparison(source, comparison_queries(source))
assert report["agreements"] == report["scope_count"] == 54
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, str(tmp_path / "sample_a.db")],
        env={k: v for k, v in os.environ.items() if k != "PYTHON_DOTENV_DISABLED"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
