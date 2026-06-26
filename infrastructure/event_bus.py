"""Lightweight synchronous event bus for internal application events."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

from infrastructure.logging_config import get_logger


EventHandler = Callable[["InternalEvent"], None]


@dataclass(frozen=True)
class InternalEvent:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._logger = get_logger(__name__)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        if handler not in self._handlers[event_name]:
            self._handlers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        if handler in self._handlers[event_name]:
            self._handlers[event_name].remove(handler)

    def publish(self, event_name: str, **payload: Any) -> None:
        event = InternalEvent(event_name, dict(payload))
        for handler in tuple(self._handlers.get(event_name, ())):
            try:
                handler(event)
            except Exception:
                self._logger.exception("Event handler failed for %s", event_name)

