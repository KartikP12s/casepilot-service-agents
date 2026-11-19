import logging
import sqlite3
from pathlib import Path
from typing import TypedDict

import httpx
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import ValidationError

from .classifier import PlanningError, classify
from .contracts import PROTECTED, Proposal

logger = logging.getLogger(__name__)


class State(TypedDict, total=False):
    id: str
    text: str
    role: str
    owner: str
    status: str
    proposal: dict
    result: dict
    error: str
    approved: bool


def build_graph(checkpoint_path: str, tools, audit):
    Path(checkpoint_path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(checkpoint_path, check_same_thread=False)
    saver = SqliteSaver(connection)

    def plan(state: State):
        try:
            proposal = classify(state["text"])
            audit(state["id"], "agent", "classified", {"operation": proposal.operation})
            return {"proposal": proposal.model_dump(), "status": "planned"}
        except PlanningError as exc:
            audit(state["id"], "agent", "input_rejected", {})
            return {"status": "needs_information", "error": str(exc)}

    def permission(state: State):
        if state["role"] == "viewer" and state["proposal"]["operation"] not in {
            "get_ticket",
            "check_status",
        }:
            audit(state["id"], "agent", "permission_denied", {})
            return {"status": "denied", "error": "Your role cannot perform this operation"}
        audit(state["id"], "agent", "permission_checked", {})
        return {"status": "authorized"}

    def approval(state: State):
        if state["proposal"]["operation"] in PROTECTED:
            decision = interrupt(
                {"proposal": state["proposal"], "risk": "high", "request_id": state["id"]}
            )
            if not decision["approve"]:
                return {"status": "rejected", "approved": False}
        return {"approved": True, "status": "ready"}

    def execute(state: State):
        audit(state["id"], "agent", "tool_started", {"operation": state["proposal"]["operation"]})
        try:
            result = tools.execute(Proposal.model_validate(state["proposal"]), state["id"])
            audit(state["id"], "agent", "tool_completed", result)
            return {"result": result, "status": "completed", "error": ""}
        except (httpx.HTTPError, ValidationError, ValueError, RuntimeError) as exc:
            logger.warning(
                "tool_failed", extra={"request_id": state["id"], "error_type": type(exc).__name__}
            )
            audit(state["id"], "agent", "tool_failed", {"type": type(exc).__name__})
            return {
                "status": "failed",
                "error": "Tool failed; inspect the audit trail and retry safely",
            }

    graph = StateGraph(State)
    for name, fn in [
        ("plan", plan),
        ("permission", permission),
        ("approval", approval),
        ("execute", execute),
    ]:
        graph.add_node(name, fn)
    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", lambda s: "permission" if s["status"] == "planned" else END)
    graph.add_conditional_edges(
        "permission", lambda s: "approval" if s["status"] == "authorized" else END
    )
    graph.add_conditional_edges("approval", lambda s: "execute" if s.get("approved") else END)
    graph.add_edge("execute", END)
    return graph.compile(checkpointer=saver), connection
