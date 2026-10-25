from datetime import datetime
from typing import Protocol

class Clock(Protocol):
    """Протокол для получения текущего времени (нужен для тестов)."""
    def now(self) -> datetime: ...