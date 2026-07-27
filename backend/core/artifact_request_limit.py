from __future__ import annotations

import json
from typing import Final

from starlette.types import (
    Message,
    Receive,
    Scope,
    Send,
)


_ARTIFACT_GENERATE_PATH: Final = (
    "/api/v1/artifacts/generate"
)


class _RequestTooLarge(Exception):
    pass


class ArtifactRequestSizeLimitMiddleware:
    """Reject oversized artifact-generation request bodies."""

    def __init__(
        self,
        app,
        *,
        maximum_request_bytes: int,
    ) -> None:
        if maximum_request_bytes < 1:
            raise ValueError(
                "Maximum request size must be positive."
            )

        self.app = app
        self.maximum_request_bytes = (
            maximum_request_bytes
        )

    @staticmethod
    def _content_length(
        scope: Scope,
    ) -> int | None:
        for name, value in scope.get(
            "headers",
            (),
        ):
            if name.lower() != b"content-length":
                continue

            try:
                parsed = int(
                    value.decode(
                        "ascii"
                    )
                )
            except (
                UnicodeDecodeError,
                ValueError,
            ):
                return None

            return max(
                parsed,
                0,
            )

        return None

    async def _send_too_large(
        self,
        send: Send,
    ) -> None:
        body = json.dumps(
            {
                "detail": (
                    "Artifact request exceeds "
                    "the configured size limit."
                )
            },
            separators=(",", ":"),
        ).encode("utf-8")

        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (
                        b"content-type",
                        b"application/json",
                    ),
                    (
                        b"content-length",
                        str(
                            len(body)
                        ).encode("ascii"),
                    ),
                    (
                        b"cache-control",
                        b"no-store",
                    ),
                    (
                        b"x-content-type-options",
                        b"nosniff",
                    ),
                ],
            }
        )

        await send(
            {
                "type": "http.response.body",
                "body": body,
                "more_body": False,
            }
        )

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if (
            scope.get("type") != "http"
            or scope.get("method") != "POST"
            or scope.get("path")
            != _ARTIFACT_GENERATE_PATH
        ):
            await self.app(
                scope,
                receive,
                send,
            )
            return

        content_length = (
            self._content_length(
                scope
            )
        )

        if (
            content_length is not None
            and content_length
            > self.maximum_request_bytes
        ):
            await self._send_too_large(
                send
            )
            return

        consumed_bytes = 0

        async def limited_receive() -> Message:
            nonlocal consumed_bytes

            message = await receive()

            if (
                message.get("type")
                == "http.request"
            ):
                body = message.get(
                    "body",
                    b"",
                )

                consumed_bytes += len(body)

                if (
                    consumed_bytes
                    > self.maximum_request_bytes
                ):
                    raise _RequestTooLarge

            return message

        try:
            await self.app(
                scope,
                limited_receive,
                send,
            )

        except _RequestTooLarge:
            await self._send_too_large(
                send
            )