from typing import Optional
from uuid import UUID

from domain.common.exceptions import EntityNotFound
from domain.parking.aggregates import ParkingSession, ParkingSpot
from domain.parking.values import SessionId, SpotId, VehicleId
from datetime import datetime
from domain.common.clock import Clock
from domain.parking.repositories import PaymentGateway

class InMemoryParkingSpotRepository:
    def __init__(self) -> None:
        self._storage: dict[UUID, ParkingSpot] = {}

    def get(self, spot_id: SpotId) -> ParkingSpot:
        try:
            return self._storage[spot_id.value]
        except KeyError:
            raise EntityNotFound(f"ParkingSpot {spot_id.value} не найден")

    def save(self, spot: ParkingSpot) -> None:
        self._storage[spot.spot_id.value] = spot


class InMemoryParkingSessionRepository:
    def __init__(self) -> None:
        self._storage: dict[UUID, ParkingSession] = {}

    def get(self, session_id: SessionId) -> ParkingSession:
        try:
            return self._storage[session_id.value]
        except KeyError:
            raise EntityNotFound(
                f"ParkingSession {session_id.value} не найден"
            )

    def save(self, session: ParkingSession) -> None:
        self._storage[session.session_id.value] = session

    def find_active_by_vehicle(
        self, vehicle_id: VehicleId
    ) -> Optional[ParkingSession]:
        for s in self._storage.values():
            if s.vehicle_id == vehicle_id and s.is_active():
                return s
        return None

class SystemClock(Clock):
    """Реальные часы системы."""
    def now(self) -> datetime:
        return datetime.now()

class FakePaymentGateway(PaymentGateway):
    """Заглушка платежной системы (всегда возвращает успех)."""
    def __init__(self):
        self.payments = []
        
    def process_payment(self, session_id: str, amount: float) -> bool:
        self.payments.append((session_id, amount))
        return True