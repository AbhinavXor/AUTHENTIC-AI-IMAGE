from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from threading import RLock
from time import monotonic
from typing import Iterable, Literal

from ai.provider_adapter import ProviderError


CircuitState = Literal[
    "closed",
    "open",
    "half_open",
]


@dataclass(slots=True)
class _ProviderState:
    circuit_state: CircuitState = "closed"
    consecutive_failures: int = 0
    cooldown_until: float = 0.0
    probe_in_flight: bool = False
    last_error_code: str | None = None
    last_status_code: int | None = None
    last_success_at: str | None = None
    last_failure_at: str | None = None


class ProviderHealthManager:
    """
    Tracks provider availability without exposing credentials,
    prompts, responses, or sensitive provider error bodies.
    """

    def __init__(
        self,
        provider_names: Iterable[str],
        *,
        failure_threshold: int = 2,
        base_cooldown_seconds: int = 15,
        maximum_cooldown_seconds: int = 300,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError(
                "failure_threshold must be at least 1."
            )

        if base_cooldown_seconds < 1:
            raise ValueError(
                "base_cooldown_seconds must be positive."
            )

        if maximum_cooldown_seconds < base_cooldown_seconds:
            raise ValueError(
                "maximum cooldown cannot be smaller "
                "than base cooldown."
            )

        self._failure_threshold = failure_threshold
        self._base_cooldown_seconds = (
            base_cooldown_seconds
        )
        self._maximum_cooldown_seconds = (
            maximum_cooldown_seconds
        )

        self._states = {
            name: _ProviderState()
            for name in provider_names
        }

        self._lock = RLock()

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    def _get_state(
        self,
        provider: str,
    ) -> _ProviderState:
        return self._states.setdefault(
            provider,
            _ProviderState(),
        )

    def _calculated_cooldown(
        self,
        failure_count: int,
    ) -> int:
        exponent = max(
            0,
            failure_count - self._failure_threshold,
        )

        cooldown = (
            self._base_cooldown_seconds
            * (2 ** exponent)
        )

        return min(
            cooldown,
            self._maximum_cooldown_seconds,
        )

    def acquire_attempt(
        self,
        provider: str,
    ) -> bool:
        """
        Return whether one request may use this provider.

        When an open circuit's cooldown expires, only one
        half-open probe is permitted at a time.
        """

        with self._lock:
            state = self._get_state(provider)
            now = monotonic()

            if state.circuit_state == "closed":
                return True

            if (
                state.circuit_state == "open"
                and now < state.cooldown_until
            ):
                return False

            if state.circuit_state == "open":
                state.circuit_state = "half_open"
                state.probe_in_flight = True
                return True

            if (
                state.circuit_state == "half_open"
                and not state.probe_in_flight
            ):
                state.probe_in_flight = True
                return True

            return False

    def record_success(
        self,
        provider: str,
    ) -> None:
        with self._lock:
            state = self._get_state(provider)

            state.circuit_state = "closed"
            state.consecutive_failures = 0
            state.cooldown_until = 0.0
            state.probe_in_flight = False
            state.last_error_code = None
            state.last_status_code = None
            state.last_success_at = self._utc_now()

    def record_failure(
        self,
        provider: str,
        error: ProviderError,
    ) -> None:
        with self._lock:
            state = self._get_state(provider)

            state.probe_in_flight = False
            state.last_error_code = error.code
            state.last_status_code = error.status_code
            state.last_failure_at = self._utc_now()

            # A malformed request usually relates to one prompt,
            # model parameter, or adapter implementation. It must
            # not mark the entire provider as unhealthy.
            if error.code == "request":
                state.circuit_state = "closed"
                return

            state.consecutive_failures += 1

            immediate_open = error.code in {
                "rate_limit",
                "authentication",
                "configuration",
            }

            infrastructure_failure = error.code in {
                "timeout",
                "connection",
                "response",
                "unknown",
            }

            should_open = (
                immediate_open
                or (
                    infrastructure_failure
                    and state.consecutive_failures
                    >= self._failure_threshold
                )
                or state.circuit_state == "half_open"
            )

            if not should_open:
                state.circuit_state = "closed"
                return

            cooldown = self._calculated_cooldown(
                state.consecutive_failures
            )

            if error.code == "rate_limit":
                cooldown = max(
                    60,
                    cooldown,
                )

            if error.code in {
                "authentication",
                "configuration",
            }:
                cooldown = max(
                    300,
                    cooldown,
                )

            cooldown = min(
                cooldown,
                self._maximum_cooldown_seconds,
            )

            state.circuit_state = "open"
            state.cooldown_until = (
                monotonic() + cooldown
            )

    def snapshot(
        self,
    ) -> list[dict[str, object]]:
        with self._lock:
            now = monotonic()
            result: list[dict[str, object]] = []

            for provider, state in sorted(
                self._states.items()
            ):
                remaining = max(
                    0,
                    ceil(
                        state.cooldown_until - now
                    ),
                )

                available = (
                    state.circuit_state == "closed"
                    or (
                        state.circuit_state == "open"
                        and remaining == 0
                    )
                )

                if (
                    state.circuit_state == "half_open"
                    and state.probe_in_flight
                ):
                    available = False

                result.append(
                    {
                        "provider": provider,
                        "circuit_state": (
                            state.circuit_state
                        ),
                        "available": available,
                        "consecutive_failures": (
                            state.consecutive_failures
                        ),
                        "cooldown_remaining_seconds": (
                            remaining
                        ),
                        "last_error_code": (
                            state.last_error_code
                        ),
                        "last_status_code": (
                            state.last_status_code
                        ),
                        "last_success_at": (
                            state.last_success_at
                        ),
                        "last_failure_at": (
                            state.last_failure_at
                        ),
                    }
                )

            return result
