from collections import defaultdict
from collections.abc import Callable

Handler = Callable[[str, dict[str, object]], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event: str, handler: Handler) -> None:
        self._handlers[event].append(handler)

    def publish(self, event: str, payload: dict[str, object]) -> None:
        for handler in self._handlers[event]:
            handler(event, payload)


event_bus = EventBus()
