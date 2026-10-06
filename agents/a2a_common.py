"""Shared helpers for building A2A agent servers (Starlette apps) and
constructing Agent Cards, reused by planner/generator/reviewer agents.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue_v2 import EventQueue
from a2a.server.request_handlers.default_request_handler_v2 import (
    DefaultRequestHandlerV2,
)
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.types.a2a_pb2 import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    Role,
    TaskState,
)
from a2a.helpers.proto_helpers import (
    get_message_text,
    new_task_from_user_message,
    new_text_part,
)
from a2a.utils.constants import TransportProtocol
from starlette.applications import Starlette

logger = logging.getLogger(__name__)


def build_agent_card(
    name: str,
    description: str,
    url: str,
    skill_id: str,
    skill_description: str,
    tags: list[str],
) -> AgentCard:
    """Builds a minimal, valid AgentCard for one of our demo agents."""
    return AgentCard(
        name=name,
        description=description,
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["text/plain"],
        default_output_modes=["application/json"],
        supported_interfaces=[
            AgentInterface(
                url=url,
                protocol_binding=TransportProtocol.JSONRPC,
                protocol_version="1.0",
            )
        ],
        skills=[
            AgentSkill(
                id=skill_id,
                name=skill_id,
                description=skill_description,
                tags=tags,
            )
        ],
    )


class JsonHandlerAgentExecutor(AgentExecutor):
    """Generic AgentExecutor that JSON-decodes the incoming user message
    text, calls a synchronous handler(dict) -> dict, and returns the result
    as a JSON text message on the task (used by all three demo agents to
    avoid re-implementing A2A task plumbing three times).
    """

    def __init__(self, handler: Callable[[dict], dict]) -> None:
        self._handler = handler

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        from a2a.server.tasks.task_updater import TaskUpdater

        message = context.message
        task = context.current_task
        if task is None:
            task = new_task_from_user_message(message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work()

        raw_text = get_message_text(message) if message else "{}"
        try:
            payload = json.loads(raw_text) if raw_text else {}
        except json.JSONDecodeError:
            payload = {"text": raw_text}

        try:
            result = self._handler(payload)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Agent handler failed")
            await updater.failed(
                message=updater.new_agent_message([new_text_part(str(exc))])
            )
            return

        response_text = json.dumps(result)
        await updater.complete(
            message=updater.new_agent_message([new_text_part(response_text)])
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("Cancellation is not supported by this demo agent.")


def build_agent_app(agent_card: AgentCard, handler: Callable[[dict], dict]) -> Starlette:
    """Builds a minimal Starlette app serving one A2A agent (agent-card +
    JSON-RPC message/send endpoint) backed by `handler`.
    """
    executor = JsonHandlerAgentExecutor(handler)
    request_handler = DefaultRequestHandlerV2(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )
    routes = create_agent_card_routes(agent_card) + create_jsonrpc_routes(
        request_handler, rpc_url="/"
    )
    return Starlette(routes=routes)
