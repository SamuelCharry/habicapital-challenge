from collections.abc import Callable
from dataclasses import dataclass
import logging
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DomainEvent:
    pass


@dataclass(frozen=True)
class TransferCompleted(DomainEvent):
    operation_id: UUID
    shared_expense_id: UUID | None


class EventDispatcher:
    def __init__(self):
        self.handlers: dict[type[DomainEvent], list[Callable]] = {}

    def subscribe(self, event_type: type[DomainEvent], handler: Callable) -> None:
        self.handlers.setdefault(event_type, []).append(handler)

    def publish(self, event: DomainEvent) -> None:
        for handler in self.handlers.get(type(event), ()):
            try:
                handler(event)
            except Exception:
                logger.exception('Handler failed for %s', event)
