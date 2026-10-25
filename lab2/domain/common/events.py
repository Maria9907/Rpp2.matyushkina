from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class DomainEvent:
    occurred_at: datetime

@dataclass(frozen=True)
class PaymentReceived(DomainEvent):
    """Событие: оплата получена."""
    session_id: str
    amount: float

@dataclass(frozen=True)
class OverstayNotified(DomainEvent):
    """Событие: оператор уведомлен о длительной стоянке (7 суток)."""
    session_id: str