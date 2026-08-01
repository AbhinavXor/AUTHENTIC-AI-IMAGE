from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from uuid import uuid4

from starlette.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
)

logger = logging.getLogger("authentic.request")

request_id_context: ContextVar[str | None] = (
    ContextVar(
        "request_id",
        default=None,
    )
)


def current_request_id() -> str | None:
    return request_id_context.get()


class RequestContextMiddleware:
    """Adds correlation IDs and structured request completion logs."""

    def __init__(
        self,
        app: ASGIApp,
    ) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(
                scope,
                receive,
                send,
            )
            return

        headers = {
            key.decode("latin-1").lower():
                value.decode("latin-1")
            for key, value in scope.get(
                "headers",
                [],
            )
        }
        requested_id = headers.get(
            "x-request-id",
            "",
        ).strip()
        request_id = (
            requested_id[:128]
            if requested_id
            else uuid4().hex
        )
        context_token = request_id_context.set(
            request_id
        )
        started = time.perf_counter()
        status_code = 500

        async def send_with_context(
            message: Message,
        ) -> None:
            nonlocal status_code

            if message["type"] == "http.response.start":
                status_code = int(
                    message["status"]
                )
                response_headers = list(
                    message.get("headers", [])
                )
                response_headers.append(
                    (
                        b"x-request-id",
                        request_id.encode("ascii"),
                    )
                )
                message["headers"] = response_headers

            await send(message)

        try:
            await self.app(
                scope,
                receive,
                send_with_context,
            )
        finally:
            duration_ms = round(
                (
                    time.perf_counter()
                    - started
                )
                * 1_000,
                2,
            )
            logger.info(
                "request_complete request_id=%s method=%s path=%s status=%s duration_ms=%s",
                request_id,
                scope.get("method", ""),
                scope.get("path", ""),
                status_code,
                duration_ms,
            )
            request_id_context.reset(
                context_token
            )
