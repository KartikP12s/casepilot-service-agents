import httpx

from .contracts import Proposal, ToolResult


class RestTools:
    def __init__(self, base_url: str, token: str, timeout: float = 5, transport=None):
        self.client = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)
        self.token = token

    def execute(self, proposal: Proposal, key: str) -> dict:
        # Fixed endpoint only. One bounded retry; the remote transaction deduplicates writes.
        for attempt in range(2):
            try:
                response = self.client.post(
                    "/tools/execute",
                    json=proposal.model_dump(),
                    headers={"Authorization": f"Bearer {self.token}", "Idempotency-Key": key},
                )
                response.raise_for_status()
                return ToolResult.model_validate(response.json()).model_dump()
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt:
                    raise
        raise RuntimeError("unreachable")
