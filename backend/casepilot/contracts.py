from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Operation = Literal[
    "create_ticket",
    "get_ticket",
    "update_ticket",
    "escalate_ticket",
    "request_access",
    "check_status",
    "deactivate_account",
]
PROTECTED = {"update_ticket", "escalate_ticket", "request_access", "deactivate_account"}


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Operation
    title: str | None = Field(default=None, min_length=3, max_length=500)
    ticket_id: int | None = Field(default=None, ge=1)
    resource: str | None = Field(default=None, min_length=3, max_length=120)
    team: str | None = Field(default=None, min_length=2, max_length=80)
    status: Literal["open", "in_progress", "closed"] | None = None
    account: str | None = Field(default=None, min_length=3, max_length=120)

    @model_validator(mode="after")
    def required_fields(self):
        required = {
            "create_ticket": ["title"],
            "get_ticket": ["ticket_id"],
            "check_status": ["ticket_id"],
            "update_ticket": ["ticket_id", "status"],
            "escalate_ticket": ["ticket_id", "team"],
            "request_access": ["resource"],
            "deactivate_account": ["account"],
        }
        missing = [key for key in required[self.operation] if getattr(self, key) is None]
        if missing:
            raise ValueError("Missing parameters: " + ", ".join(missing))
        return self


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: int
    operation: Operation
    status: str
    summary: str


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=3, max_length=2000)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve: bool
    reason: str = Field(min_length=3, max_length=500)
