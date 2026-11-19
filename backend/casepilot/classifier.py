"""Offline deterministic planner. Untrusted text never changes permissions or tool URLs."""

import json
import re

from pydantic import ValidationError

from .contracts import Proposal


class PlanningError(ValueError):
    pass


def classify(text: str) -> Proposal:
    lower = text.lower()
    if re.search(
        r"ignore.{0,30}(instructions|rules)|system\s*:|bypass|grant.{0,15}admin|https?://|execute\s+(shell|command)|reveal.{0,20}(secret|token)",
        lower,
    ):
        raise PlanningError("Unsafe instruction: policy or execution override rejected")
    try:
        if text.lstrip().startswith("{"):
            return Proposal.model_validate(json.loads(text))
        number = re.search(r"#?(\d+)", text)
        ticket = int(number.group(1)) if number else None
        if "deactivat" in lower:
            match = re.search(r"account\s+([\w.@-]+)", text, re.IGNORECASE)
            return Proposal(
                operation="deactivate_account",
                account=match.group(1)
                if match and match.group(1).lower() not in {"deactivation", "request", "deactivate"}
                else None,
            )
        if "escalat" in lower:
            match = re.search(r"to\s+(?:the\s+)?(.+?)(?:\s+team)?[.!]?$", text, re.IGNORECASE)
            return Proposal(
                operation="escalate_ticket",
                ticket_id=ticket,
                team=match.group(1) if match else None,
            )
        if "access" in lower:
            match = re.search(r"access\s+to\s+(?:the\s+)?(.+?)[.!]?$", text, re.IGNORECASE)
            return Proposal(operation="request_access", resource=match.group(1) if match else None)
        if "update" in lower or "close ticket" in lower:
            status = (
                "closed"
                if "clos" in lower
                else "in_progress"
                if "in progress" in lower
                else "open"
                if "open" in lower
                else None
            )
            return Proposal(operation="update_ticket", ticket_id=ticket, status=status)
        if any(x in lower for x in ["status", "retrieve", "get ticket", "check ticket"]):
            return Proposal(operation="get_ticket", ticket_id=ticket)
        if any(x in lower for x in ["create", "support ticket", "cannot", "broken"]):
            return Proposal(operation="create_ticket", title=text[:500])
    except (ValidationError, json.JSONDecodeError) as exc:
        raise PlanningError("Invalid or incomplete tool parameters") from exc
    raise PlanningError(
        "Unrecognized or ambiguous request; specify a ticket operation or access resource"
    )
