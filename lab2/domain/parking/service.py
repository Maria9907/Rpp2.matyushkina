from datetime import datetime
from domain.common.exceptions import DomainInvariantViolation, GatewayUnresolved
from domain.common.clock import Clock
from domain.parking.repositories import (
    ParkingSpotRepository, 
    ParkingSessionRepository, 
    PaymentGateway
)
from domain.parking.aggregates import ParkingSpot, ParkingSession
from domain.parking.values import VehicleId, LicensePlate, SpotId, SessionId, Tariff

class ParkingProcess:
    """
    Прикладной сервис, реализующий BPMN-процесс парковки.
    Каждая задача схемы соответствует отдельному методу.
    """
    def __init__(self, spots: ParkingSpotRepository, sessions: ParkingSessionRepository, 
                 payment_gateway: PaymentGateway, clock: Clock, tariff: Tariff):
        self._spots = spots
        self._sessions = sessions
        self._payment_gateway = payment_gateway
        self._clock = clock
        self._tariff = tariff

    # --- 1. Задача: Проверить блок-лист ---
    def check_blocklist(self, license_plate: LicensePlate) -> bool:
        """Возвращает True, если автомобиль заблокирован."""
        # Для заглушки: блокируем все номера, начинающиеся на "X"
        return str(license_plate).startswith("X")

    # --- 2. Задача: Проверить свободные места ---
    def check_free_spots(self) -> bool:
        """Возвращает True, если есть свободные места."""
        # В реальной БД это был бы запрос count(is_free)
        return True # Предположим, что места всегда есть для теста

    # --- 3. Задача: Назначить парковочное место ---
    def assign_spot(self, number: str) -> ParkingSpot:
        spot = ParkingSpot.create(number)
        self._spots.save(spot)
        return spot

    # --- 4. Задача: Создать активную сессию (Начать парковку) ---
    def start_session(self, spot: ParkingSpot, vehicle_id: VehicleId, license_plate: LicensePlate) -> ParkingSession:
        # Задача "Открыть шлагбаум" пропущена, т.к. это внешнее устройство
        session = ParkingSession.create(
            spot_id=spot.spot_id,
            vehicle_id=vehicle_id,
            license_plate=license_plate,
            entry_time=self._clock.now(),
            clock=self._clock
        )
        spot.occupy(session.session_id) # Задача "Занять место"
        
        self._spots.save(spot)
        self._sessions.save(session)
        return session

    # --- 5. Задача: Принять оплату (Водитель оплачивает через приложение) ---
    def accept_payment(self, session_id: SessionId, amount: float) -> None:
        session = self._sessions.get(session_id)
        success = self._payment_gateway.process_payment(str(session_id.value), amount)
        if not success:
            raise DomainInvariantViolation("Платеж отклонен платежной системой")
        
        session.pay(amount)
        self._sessions.save(session)

    # --- 6. Задача: Принять оплату в терминале у выезда ---
    def accept_payment_at_exit(self, session_id: SessionId, amount: float) -> None:
        session = self._sessions.get(session_id)
        success = self._payment_gateway.process_payment(str(session_id.value), amount)
        if not success:
            raise DomainInvariantViolation("Платеж отклонен платежной системой")
        
        session.pay_at_exit(amount)
        self._sessions.save(session)

    # --- 7. Задача: Закрыть сессию и освободить место (Выезд) ---
    def process_exit(self, session_id: SessionId, exit_time: datetime) -> None:
        session = self._sessions.get(session_id)
        
        # Проверка шлюза "Оплата действительна?"
        # ИСПРАВЛЕНО: используем русские названия состояний
        if session.state in ("Не оплачена", "Уведомлён"):
             raise GatewayUnresolved("Требуется оплата на выезде")
             
        # Закрываем сессию (считаем стоимость и переводим в ClosedState)
        session.close(exit_time, self._tariff) 
        
        spot = self._spots.get(session.spot_id)
        spot.release() # Задача "Освободить место"
        
        self._sessions.save(session)
        self._spots.save(spot)

    # --- 8. Задача: Событие таймера (Прошло 7 суток) ---
    def on_timer_7_days(self, session_id: SessionId) -> None:
        session = self._sessions.get(session_id)
        session.on_timer_7_days(self._clock.now()) # Задача "Уведомить оператора"
        self._sessions.save(session)