"""200 end-to-end graph cases with a real synthetic REST handler and injected faults."""

import json
from pathlib import Path

import httpx
import pytest
from casepilot.service import create_service
from casepilot.tools import RestTools
from casepilot.workflow import build_graph
from fastapi.testclient import TestClient
from langgraph.types import Command

CASES = json.loads(Path("fixtures/service_cases.json").read_text())


def execute_case(case, tmp_path):
    service = TestClient(create_service(f"sqlite:///{tmp_path}/service.db", "service"))
    requests = []
    fault = case.get("fault")
    recovery = False

    def transport(req):
        requests.append(req)
        if fault in {"tool_timeout", "retry_recovery"} and not recovery:
            raise httpx.ReadTimeout("Synthetic timeout")
        if fault == "tool_exception":
            return httpx.Response(503, json={"detail": "Synthetic unavailable"})
        if fault == "invalid_tool_result":
            return httpx.Response(200, json={"status": "fake success"})
        response = service.post(req.url.path, content=req.content, headers=dict(req.headers))
        return httpx.Response(response.status_code, json=response.json())

    tools = RestTools("http://service", "service", transport=httpx.MockTransport(transport))
    events = []
    graph, connection = build_graph(
        str(tmp_path / "checkpoints.db"), tools, lambda *args: events.append(args)
    )
    config = {"configurable": {"thread_id": case["id"]}}
    try:
        graph.invoke(
            {
                "id": case["id"],
                "text": case["text"],
                "role": case.get("role", "requester"),
                "owner": "synthetic",
            },
            config,
        )
        snapshot = graph.get_state(config)
        if snapshot.tasks and any(t.interrupts for t in snapshot.tasks):
            assert len(requests) == 0, "Protected action ran before approval"
            if "decision" in case:
                graph.invoke(Command(resume={"approve": case["decision"]}), config)
        snapshot = graph.get_state(config)
        state = snapshot.values
        if fault == "retry_recovery":
            assert state["status"] == "failed"
            recovery = True
            graph.update_state(config, {"status": "ready"}, as_node="approval")
            graph.invoke(None, config)
            state = graph.get_state(config).values
        actual = (
            "awaiting_approval"
            if any(t.interrupts for t in graph.get_state(config).tasks)
            else state["status"]
        )
        assert actual == case["expected"], f"{case['id']}: {actual} != {case['expected']}"
        if case.get("operation"):
            assert state["proposal"]["operation"] == case["operation"]
        for key, expected in case.get("parameters", {}).items():
            assert state["proposal"][key] == expected
        if actual in {"denied", "rejected", "needs_information", "awaiting_approval"}:
            assert not requests
        if actual == "completed":
            assert state["result"]["record_id"] > 0
        if fault == "duplicate_request":
            from casepilot.contracts import Proposal

            duplicate = tools.execute(Proposal.model_validate(state["proposal"]), case["id"])
            assert duplicate == state["result"]
        if fault == "tool_timeout":
            assert len(requests) == 2, "Retry must be bounded"
    finally:
        connection.close()
        tools.client.close()
        service.close()


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['id']}-{c['category']}")
def test_synthetic_case(case, tmp_path):
    execute_case(case, tmp_path)
