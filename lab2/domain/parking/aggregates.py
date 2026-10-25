from datetime import datetime
from enum import Enum
from uuid import uuid4


from domain.common.values import Money
from domain.parking.values import (
     ParkingPolicy, SessionId, SpotId, Tariff,
    TimeInterval,
)

from domain.common.exceptions import DomainInvariantViolation
from domain.common.events import PaymentReceived, OverstayNotified
from domain.common.clock import Clock
from domain.parking.states import (
    SessionState, NotPaidState, PaidState, NotifiedState, ClosedState
)
from domain.common.exceptions import TransitionNotAllowed

class SpotStatus(Enum):
    FREE = "свободно"
    OCCUPIED = "занято"


class SessionStatus(Enum):
    ACTIVE = "активна"
    CLOSED = "закрыта"


class ParkingSpot:
    def __init__(self, spot_id: SpotId, number: str,
                 active_session_id: SessionId | None = None) -> None:
        if not number.strip():
            raise DomainInvariantViolation("Номер места не может быть пустым")
        self._spot_id = spot_id
        self._number = number
        self._active_session_id = active_session_id

    @property
    def spot_id(self) -> SpotId: return self._spot_id
    @property
    def number(self) -> str: return self._number
    @property
    def active_session_id(self) -> SessionId | None:
        return self._active_session_id

    @property
    def status(self) -> SpotStatus:
        return (SpotStatus.OCCUPIED if self._active_session_id is not None
                else SpotStatus.FREE)

    def is_free(self) -> bool:
        return self._active_session_id is None

    @classmethod
    def create(cls, number: str) -> "ParkingSpot":
        return cls(SpotId(uuid4()), number)

    @classmethod
    def restore(cls, spot_id: SpotId, number: str,
                active_session_id: SessionId | None) -> "ParkingSpot":
        return cls(spot_id, number, active_session_id)

    def occupy(self, session_id: SessionId) -> None:
        if self._active_session_id is not None:
            raise DomainInvariantViolation(f"Место {self._number} уже занято")
        self._active_session_id = session_id

    def release(self) -> None:
        if self._active_session_id is None:
            raise DomainInvariantViolation(f"Место {self._number} не занято")
        self._active_session_id = None


class ParkingSession:
    def __init__(self, session_id, spot_id, vehicle_id, license_plate, interval, clock: Clock, cost=None, overstay_fine=None):
        self._session_id = session_id
        self._spot_id = spot_id
        self._vehicle_id = vehicle_id
        self._license_plate = license_plate
        self._interval = interval
        self._cost = cost
        self._overstay_fine = overstay_fine
        self._clock = clock
        
        # --- ГЛАВНОЕ ИЗМЕНЕНИЕ: Вместо Enum статуса кладем объект Состояния ---
        self._state: SessionState = NotPaidState() 
        self._events = [] # Журнал доменных событий
        self._last_payment_time: datetime | None = None

    # Свойства (геттеры) остаются прежними, плюс новые:
    @property
    def session_id(self): return self._session_id
    @property
    def spot_id(self): return self._spot_id
    @property
    def vehicle_id(self): return self._vehicle_id
    @property
    def license_plate(self): return self._license_plate
    @property
    def interval(self): return self._interval
    @property
    def cost(self): return self._cost
    @property
    def overstay_fine(self): return self._overstay_fine
    @property
    def events(self): return self._events.copy()

    @property
    def state(self) -> str:
        """Возвращает название текущего состояния (для вывода)."""
        return self._state.name

    def get_allowed_events(self) -> list[str]:
        """Возвращает список допустимых событий в текущем состоянии."""
        return self._state.get_allowed_events()

    # --- НОВЫЕ МЕТОДЫ СОБЫТИЙ (делегируют работу состоянию) ---

    def pay(self, amount: float) -> None:
        self._state = self._state.pay(amount)
        self._last_payment_time = self._clock.now()
        self._events.append(PaymentReceived(self._last_payment_time, str(self.session_id), amount))

    def pay_at_exit(self, amount: float) -> None:
        self._state = self._state.pay_at_exit(amount)

    def pay_extra(self, amount: float) -> None:
        if self._last_payment_time:
            diff = (self._clock.now() - self._last_payment_time).total_seconds()
            if diff <= 900: # 15 минут = 900 секунд
                raise DomainInvariantViolation("Доплата не требуется, прошло менее 15 минут")
        self._state = self._state.pay_extra(amount)
        self._last_payment_time = self._clock.now()

    def exit_vehicle(self) -> None:
        self._state = self._state.exit()

    def on_timer_7_days(self, now: datetime) -> None:
        new_state = self._state.timer_7_days(now)
        # Если состояние изменилось на Уведомлён, пишем событие
        if isinstance(new_state, NotifiedState) and not isinstance(self._state, NotifiedState):
            self._events.append(OverstayNotified(now, str(self.session_id)))
        self._state = new_state

    # --- СТАРЫЙ МЕТОД CLOSE (адаптированный под новые состояния) ---
    def close(self, exit_time: datetime, tariff: Tariff, policy: ParkingPolicy | None = None):
        if isinstance(self._state, ClosedState):
            from domain.common.exceptions import TransitionNotAllowed
            raise TransitionNotAllowed("ClosedState", "exit")
        
        self._interval = TimeInterval(self._interval.entry_time, exit_time)
        hours = self._interval.billed_hours()
        self._cost = tariff.cost_for(hours)

        if policy is not None and policy.is_overstay(hours):
            self._overstay_fine = policy.overstay_fine
        else:
            from domain.common.values import Money
            self._overstay_fine = Money.zero(self._cost.currency)
            
        self._state = ClosedState() # Переводим в конечное состояние
        return self._cost

    @classmethod
    def create(cls, spot_id, vehicle_id, license_plate, entry_time, clock: Clock):
        # Нам нужно передать clock внутрь при создании
        return cls(
            session_id=SessionId(uuid4()),
            spot_id=spot_id,
            vehicle_id=vehicle_id,
            license_plate=license_plate,
            interval=TimeInterval(entry_time=entry_time),
            clock=clock
        )