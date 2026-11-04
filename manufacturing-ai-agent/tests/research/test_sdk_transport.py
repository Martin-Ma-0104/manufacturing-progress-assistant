"""Offline HTTP transport mocks exercise actual SDK serialization, never the API."""

import asyncio
import json
from unittest.mock import patch
import httpx
import pytest
from openai import AsyncOpenAI
from research.harry_milestone.agent import LivePermit, ResearchAgent
from research.harry_milestone.contracts import Query, TOOL_A
from research.harry_milestone.fixtures import build
from research.harry_milestone.tools import DataSource, ResearchTools


def response(output):
    return dict(
        id="resp_offline",
        object="response",
        created_at=0,
        model="gpt-6-sol",
        status="completed",
        output=output,
        usage=dict(input_tokens=100, output_tokens=20, total_tokens=120),
    )


def run_offline(tmp_path, monkeypatch, handler):
    path = tmp_path / "sample.db"
    build(path)
    before = path.read_bytes()
    monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
    permit = LivePermit(2, allow_external=True)

    async def execute():
        client = AsyncOpenAI(
            api_key="offline-placeholder",
            base_url="https://api.openai.com/v1",
            max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        with patch("openai.AsyncOpenAI", return_value=client):
            return await ResearchAgent(
                ResearchTools(DataSource(path, "synthetic")),
                Query(start_date="2026-01-01", end_date="2026-01-30"),
            ).run(
                "Compare input mother rolls for 2026-01-05 through 2026-01-07.",
                permit=permit,
            )

    result = asyncio.run(execute())
    assert path.read_bytes() == before
    return result, permit


def test_actual_agents_sdk_responses_roundtrip_uses_only_offline_transport(
    tmp_path, monkeypatch
):
    requests = []

    def handler(request):
        assert request.url.path == "/v1/responses" and request.method == "POST"
        body = json.loads(request.content)
        requests.append(body)
        assert body["model"] == "gpt-6-sol" and body["store"] is False
        assert (
            body["reasoning"]["effort"] == "none" and body["service_tier"] == "default"
        )
        assert "expected_answer" not in request.content.decode()
        if len(requests) == 1:
            assert {tool["name"] for tool in body["tools"]} == {
                TOOL_A,
                "rank_abnormality_duration",
            }
            output = [
                dict(
                    type="function_call",
                    id="fc_offline",
                    call_id="call_offline",
                    name=TOOL_A,
                    arguments=json.dumps(
                        dict(
                            start_date="2026-01-05",
                            end_date="2026-01-07",
                            machine_id=None,
                            shift="All",
                        )
                    ),
                    status="completed",
                )
            ]
        else:
            assert len(requests) == 2 and body["tools"] == []
            output = [
                dict(
                    type="message",
                    id="msg_offline",
                    role="assistant",
                    status="completed",
                    content=[
                        dict(
                            type="output_text",
                            text=json.dumps(
                                dict(fact_ids=["totals", "gaps", "coverage"])
                            ),
                            annotations=[],
                        )
                    ],
                )
            ]
        return httpx.Response(200, json=response(output))

    result, permit = run_offline(tmp_path, monkeypatch, handler)
    assert result["status"] == "answered", result
    assert result["result"]["actual_inputs"] == 56 and len(requests) == 2
    assert permit.requests == 2 and permit.spent_usd == pytest.approx(0.0008)
    # These are fabricated transport usage fields; no live-model result is produced.
    assert all(s["usage"]["input_tokens"] == 100 for s in result["stages"])


def test_http_failure_has_no_automatic_retry_and_is_retained(tmp_path, monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            503,
            json={
                "error": {
                    "message": "offline simulated failure",
                    "type": "server_error",
                }
            },
        )

    result, permit = run_offline(tmp_path, monkeypatch, handler)
    assert result["status"] == "failed" and result["failed_stage"] == "selection"
    assert len(requests) == permit.requests == 1 and permit.spent_usd > 0
    assert "offline-placeholder" not in json.dumps(result)
