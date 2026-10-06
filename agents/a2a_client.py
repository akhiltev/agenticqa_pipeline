"""Small helper for the Orchestrator to send a JSON payload to another A2A
agent and get back a JSON dict response (round-tripping through
JsonHandlerAgentExecutor on the server side).
"""
from __future__ import annotations

import json

import httpx

from a2a.client.client import ClientConfig
from a2a.client.client_factory import create_client
from a2a.helpers.proto_helpers import get_message_text, new_text_message
from a2a.types.a2a_pb2 import Role, SendMessageRequest, Task

# Generous timeout: the Generator agent makes a real LLM call under the hood,
# which can take well beyond the A2A SDK's default HTTP client timeout.
_AGENT_CALL_TIMEOUT_SECONDS = 180.0


async def call_agent(url: str, payload: dict) -> dict:
    httpx_client = httpx.AsyncClient(timeout=_AGENT_CALL_TIMEOUT_SECONDS)
    client = await create_client(url, client_config=ClientConfig(httpx_client=httpx_client))
    try:
        msg = new_text_message(json.dumps(payload), role=Role.ROLE_USER)
        req = SendMessageRequest(message=msg)
        last_text = "{}"
        async for resp in client.send_message(req):
            if resp.HasField("task"):
                task: Task = resp.task
                if task.status.HasField("message"):
                    last_text = get_message_text(task.status.message) or last_text
            elif resp.HasField("message"):
                last_text = get_message_text(resp.message) or last_text
        try:
            return json.loads(last_text)
        except json.JSONDecodeError:
            return {"raw": last_text}
    finally:
        await client.close()

