import asyncio
from contextlib import closing
import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from research.harry_milestone.agent import ResearchAgent, LivePermit, ScriptedDemoRunner
from research.harry_milestone.contracts import Query, Clarification, TOOL_A, TOOL_B
from research.harry_milestone.fixtures import build
from research.harry_milestone.tools import ResearchTools, DataSource
from research.harry_milestone.evaluation import (
    matches,
    score_trial,
    freeze,
    verify_freeze,
    tool_checks,
    dashboard_comparison,
    comparison_queries,
)


@pytest.fixture()
def service(tmp_path):
    p = tmp_path / "sample_a.db"
    build(p)
    build(tmp_path / "sample_b.db", "B")
    result = ResearchTools(DataSource(p, "synthetic"))
    before = p.read_bytes()
    yield result
    assert p.read_bytes() == before


def approved(**changes):
    return Query(**(dict(start_date="2026-01-01", end_date="2026-01-30") | changes))


def arguments(**changes):
    return (
        dict(
            start_date="2026-01-05", end_date="2026-01-07", machine_id=None, shift="All"
        )
        | changes
    )


class FakeRunner:
    def __init__(self, tool=TOOL_A, args=None, ids=None, clarification=None):
        self.tool, self.args, self.ids, self.clarification = (
            tool,
            args or arguments(),
            ids,
            clarification,
        )
        self.calls = 0
        self.inputs = []

    async def __call__(self, agent, **kwargs):
        from agents.tool_context import ToolContext

        self.calls += 1
        self.inputs.append(kwargs["input"])
        assert kwargs["max_turns"] == 1 and kwargs["run_config"].tracing_disabled
        assert (
            agent.model_settings.store is False
            and agent.model_settings.parallel_tool_calls is False
        )
        if self.calls == 1:
            assert len(agent.tools) == 2 and agent.model_settings.tool_choice == "auto"
            assert agent.tool_use_behavior == "stop_on_first_tool"
            if self.clarification:
                return SimpleNamespace(final_output=self.clarification)
            tool = next(t for t in agent.tools if t.name == self.tool)
            context = ToolContext(
                context=None,
                tool_name=tool.name,
                tool_call_id="offline",
                tool_arguments=json.dumps(self.args),
                run_config=kwargs["run_config"],
            )
            return SimpleNamespace(
                final_output=await tool.on_invoke_tool(context, json.dumps(self.args))
            )
        assert not agent.tools
        ids = (
            self.ids
            if self.ids is not None
            else ["totals", "gaps", "coverage"]
            if self.tool == TOOL_A
            else ["ranking", "coverage", "unranked"]
        )
        return SimpleNamespace(final_output=dict(fact_ids=ids))


@pytest.mark.parametrize("tool", [TOOL_A, TOOL_B])
def test_actual_sdk_argument_binding_and_evidence_only_output(
    service, tool, monkeypatch
):
    monkeypatch.setenv("OPENAI_API_KEY", "DUMMY-DO-NOT-READ")
    fake = FakeRunner(tool)
    agent = ResearchAgent(service, approved())
    with patch("openai.AsyncOpenAI") as api:
        result = asyncio.run(
            agent.run(
                "A development question with explicit input units and dates.",
                mock_runner=fake,
            )
        )
        api.assert_not_called()
    assert (
        result["status"] == "answered" and result["mode"] == "mock" and fake.calls == 2
    )
    assert result["trace"][0]["arguments"] == arguments()
    assert result["result"]["tool"] == tool
    package = " ".join(fake.inputs)
    assert (
        "expected_answer" not in package
        and "Q01" not in package
        and "SYN-A" not in package
        and "DUMMY-DO-NOT-READ" not in package
    )
    assert result["warnings"] == result["result"]["warnings"]


def test_clarification_executes_no_business_tool(service):
    fake = FakeRunner(
        clarification=Clarification(reason="ambiguous", target="date_range")
    )
    result = asyncio.run(
        ResearchAgent(service, approved()).run(
            "Compare production recently.", mock_runner=fake
        )
    )
    assert (
        result["status"] == "clarification"
        and result["trace"] == []
        and fake.calls == 1
        and "start and end dates" in result["question"]
    )


@pytest.mark.parametrize(
    "ids", [["invented"], ["totals"], ["totals", "totals", "gaps", "coverage"]]
)
def test_unsupported_or_incomplete_explanation_is_a_failure(service, ids):
    result = asyncio.run(
        ResearchAgent(service, approved()).run(
            "Development comparison.", mock_runner=FakeRunner(ids=ids)
        )
    )
    assert result["status"] == "failed" and "explanation" not in result


@pytest.mark.parametrize(
    "changes",
    [{"start_date": "2025-12-31"}, {"machine_id": "FX999"}, {"shift": "Night"}],
)
def test_scope_expansion_or_unknown_machine_fails(service, changes):
    outer = approved(shift="Day")
    fake = FakeRunner(args=arguments(**({"shift": "Day"} | changes)))
    result = asyncio.run(
        ResearchAgent(service, outer).run("Development comparison.", mock_runner=fake)
    )
    assert result["status"] == "failed" and fake.calls == 1


def test_live_calls_need_separate_permission_even_with_a_key(service, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "DUMMY")
    with patch("openai.AsyncOpenAI") as client:
        with pytest.raises(PermissionError):
            asyncio.run(ResearchAgent(service, approved()).run("Do a paid request."))
        client.assert_not_called()


def test_real_aggregates_need_distinct_live_permission(tmp_path):
    path = tmp_path / "real-like.db"
    with closing(sqlite3.connect(path)):
        pass
    service = ResearchTools(DataSource(path, "real"))
    with patch("openai.AsyncOpenAI") as client:
        with pytest.raises(PermissionError):
            asyncio.run(
                ResearchAgent(service, approved()).run(
                    "Question", permit=LivePermit(2, allow_external=True)
                )
            )
        client.assert_not_called()


def test_budget_reservation_and_unknown_usage():
    permit = LivePermit(0.1, allow_external=True, max_requests=1)
    agent = SimpleNamespace(
        tools=[], instructions="Question router", output_type=Clarification
    )
    reserved = permit.reserve(agent, "test")
    permit.settle(reserved, None)
    assert permit.spent_usd == reserved and permit.reserved_usd == 0
    with pytest.raises(PermissionError):
        permit.reserve(agent, "test")
    with pytest.raises(PermissionError):
        LivePermit(0.000001, allow_external=True).reserve(agent, "test")
    with pytest.raises(ValueError):
        LivePermit(2, allow_external=True).reserve(agent, "x" * 17000)


def test_frozen_oracles_and_changed_ranking(service):
    result = tool_checks(service.source.path.parent)
    assert result["passed"] == result["trial_count"] == 22
    assert result["tool_selection_accuracy"] is None
    a = service.rank_abnormality_duration(Query(**arguments()))
    b = ResearchTools(
        DataSource(service.source.path.with_name("sample_b.db"), "synthetic")
    ).rank_abnormality_duration(Query(**arguments()))
    assert not matches(a, {"rankings": b["rankings"]})


def test_numeric_type_unknown_vs_zero_and_scoring_failures():
    assert (
        not matches(None, 0) and not matches(True, 1) and not matches(float("nan"), 0)
    )
    case = dict(
        expected_tool=TOOL_A,
        expected_arguments=arguments(),
        expected_answer=dict(actual_inputs=56),
    )
    wrong = dict(
        status="failed",
        trace=[dict(tool=TOOL_A, arguments=arguments())],
        result=dict(actual_inputs=56),
    )
    score = score_trial(case, wrong)
    assert (
        score["tool_selection"]
        and score["arguments"]
        and not score["numerical"]
        and not score["end_to_end"]
    )
    clarify = dict(expected_tool=None, expected_answer=dict(reason="ambiguous"))
    assert not score_trial(clarify, dict(status="answered", trace=[]))["clarification"]


def test_fixture_hash_manifest_detects_data_or_source_changes(service, tmp_path):
    path = tmp_path / "manifest.json"
    freeze(service.source.path.parent, path)
    assert verify_freeze(service.source.path.parent, path)["model"] == "gpt-6-sol"
    value = json.loads(path.read_text())
    value["files"]["tools.py"] = "changed"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        verify_freeze(service.source.path.parent, path)


def test_dashboard_same_scope_agreement_is_not_human_timing(service):
    result = dashboard_comparison(service.source, comparison_queries(service.source))
    assert result["agreements"] == result["scope_count"] == 54
    assert result["human_dashboard_task_time"] == "not measured"


def test_scripted_development_demo_is_explicitly_mocked(service):
    result = asyncio.run(
        ResearchAgent(service, approved()).run(
            "Show FX1 mother-roll input for 2026-01-05 through 2026-01-06.",
            mock_runner=ScriptedDemoRunner(),
        )
    )
    assert (
        result["status"] == "answered"
        and result["mode"] == "mock"
        and result["result"]["actual_inputs"] == 29
    )


def test_delivered_tool_definitions_match_actual_sdk_schemas(service):
    from research.harry_milestone.evaluation import HERE

    delivered = json.loads((HERE / "tool_definitions.json").read_text())
    actual = [
        dict(
            name=t.name,
            description=t.description,
            parameters=t.params_json_schema,
            strict=t.strict_json_schema,
        )
        for t in ResearchAgent(service, approved()).sdk_tools([])
    ]
    assert delivered == actual
