from abc import ABC
from datetime import datetime
from domain.common.exceptions import TransitionNotAllowed


class SessionState(ABC):
    """Базовый класс состояния. Все методы по умолчанию кидают ошибку."""
    name: str = "Неизвестное состояние"
    
    def __str__(self) -> str:
        return self.name

    def start_session(self) -> "SessionState":
        raise TransitionNotAllowed(self.name, "start_session")
        
    def pay(self, amount: float) -> "SessionState":
        raise TransitionNotAllowed(self.name, "pay")
        
    def pay_extra(self, amount: float) -> "SessionState":
        raise TransitionNotAllowed(self.name, "pay_extra")
        
    def pay_at_exit(self, amount: float) -> "SessionState":
        raise TransitionNotAllowed(self.name, "pay_at_exit")
        
    def exit(self) -> "SessionState":
        raise TransitionNotAllowed(self.name, "exit")
        
    def timer_7_days(self, now: datetime) -> "SessionState":
        raise TransitionNotAllowed(self.name, "timer_7_days")

    def get_allowed_events(self) -> list[str]:
        return []


class NotPaidState(SessionState):
    """Состояние: Не оплачена."""
    name = "Не оплачена"
    
    def pay(self, amount: float) -> SessionState:
        return PaidState()
        
    def pay_at_exit(self, amount: float) -> SessionState:
        return ClosedState()
        
    def timer_7_days(self, now: datetime) -> SessionState:
        return NotifiedState()

    def get_allowed_events(self) -> list[str]:
        return ["pay", "pay_at_exit", "timer_7_days"]


class PaidState(SessionState):
    """Состояние: Оплачена (есть 15 минут на выезд)."""
    name = "Оплачена"
    
    def pay_extra(self, amount: float) -> SessionState:
        return PaidState()
        
    def exit(self) -> SessionState:
        return ClosedState()
        
    def timer_7_days(self, now: datetime) -> SessionState:
        return NotifiedState()

    def get_allowed_events(self) -> list[str]:
        return ["pay_extra", "exit", "timer_7_days"]


class NotifiedState(SessionState):
    """Состояние: Уведомлён (прошло 7 суток)."""
    name = "Уведомлён"
    
    def pay(self, amount: float) -> SessionState:
        return PaidState()
        
    def exit(self) -> SessionState:
        return ClosedState()
        
    def pay_at_exit(self, amount: float) -> SessionState:
        return ClosedState()

    def get_allowed_events(self) -> list[str]:
        return ["pay", "exit", "pay_at_exit"]


class ClosedState(SessionState):
    """Состояние: Закрыта"""
    name = "Закрыта"
    
    def get_allowed_events(self) -> list[str]:
        return []