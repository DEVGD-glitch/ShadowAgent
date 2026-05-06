"""EventBus — Central event dispatch for GenericAgent.

Provides a publish/subscribe mechanism for loose coupling between modules.
Replaces scattered callbacks and enables cross-module communication without
circular imports.
"""
from __future__ import annotations

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("ga.agentmain.event_bus")


class EventType(Enum):
    """Well-known event types in the GenericAgent system."""
    LLM_CALL_START = auto()
    LLM_CALL_END = auto()
    LLM_CALL_ERROR = auto()
    TOOL_EXECUTED = auto()
    TOOL_ERROR = auto()
    ERROR_OCCURRED = auto()
    THEME_CHANGED = auto()
    SESSION_SAVED = auto()
    SESSION_LOADED = auto()
    AGENT_STARTED = auto()
    AGENT_STOPPED = auto()
    SHUTDOWN_REQUESTED = auto()
    CONFIG_CHANGED = auto()
    MEMORY_UPDATED = auto()


@dataclass
class Event:
    """A single event dispatched through the EventBus."""
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""


class EventBus:
    """Central publish/subscribe event bus.
    
    Thread-safe. Subscribers are called synchronously in the publisher's
    thread — avoid long-running handlers.
    
    Usage::
        bus = EventBus()
        bus.subscribe(EventType.THEME_CHANGED, my_handler)
        bus.publish(Event(EventType.THEME_CHANGED, {"theme": "light"}))
    """
    
    def __init__(self) -> None:
        self._subscribers: Dict[EventType, List[Callable[[Event], None]]] = defaultdict(list)
        self._lock = threading.Lock()
    
    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Subscribe a handler to an event type."""
        with self._lock:
            self._subscribers[event_type].append(handler)
    
    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Remove a handler subscription."""
        with self._lock:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass
    
    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        with self._lock:
            handlers = list(self._subscribers.get(event.type, []))
        
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    "EventBus handler error for %s: %s",
                    event.type.name, e, exc_info=True,
                )


# Global singleton
_global_bus: Optional[EventBus] = None

# String-based event support (for cross-module events like circuit_breaker)
_string_subscribers: Dict[str, List[Callable]] = defaultdict(list)
_string_lock = threading.Lock()


def emit(event_name: str, data: Dict[str, Any]) -> None:
    """Emit a string-based event to all subscribers.

    This is a convenience function for modules that don't want to
    depend on the EventType enum (e.g. circuit_breaker → event_bus).

    Args:
        event_name: Dot-separated event name (e.g. "circuit_breaker.state_change").
        data: Event data dictionary.
    """
    with _string_lock:
        for callback in _string_subscribers.get(event_name, []):
            try:
                callback(data)
            except Exception as e:
                logger.warning(f"Event subscriber error for {event_name}: {e}")


def subscribe(event_name: str, handler: Callable) -> None:
    """Subscribe a handler to a string-based event.

    Args:
        event_name: Dot-separated event name.
        handler: Callable that receives a data dict.
    """
    with _string_lock:
        _string_subscribers.setdefault(event_name, []).append(handler)


def unsubscribe(event_name: str, handler: Callable) -> None:
    """Remove a handler subscription for a string-based event."""
    with _string_lock:
        if event_name in _string_subscribers:
            _string_subscribers[event_name] = [
                cb for cb in _string_subscribers[event_name] if cb != handler
            ]


def get_event_bus() -> EventBus:
    """Return the global EventBus singleton."""
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus


__all__ = [
    "EventType",
    "Event",
    "EventBus",
    "get_event_bus",
    "emit",
    "subscribe",
    "unsubscribe",
]
