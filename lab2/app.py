from datetime import datetime
from decimal import Decimal
from flask import Flask, request, jsonify
from uuid import UUID

# Импорты домена и инфраструктуры
from domain.common.exceptions import (
    DomainInvariantViolation, EntityNotFound, TransitionNotAllowed, GatewayUnresolved, InvalidValueObject
)
from domain.common.values import Money
from domain.parking.values import Tariff, VehicleId, LicensePlate, SpotId, SessionId
from domain.parking.service import ParkingProcess
from infra.parking_memory import (
    InMemoryParkingSessionRepository, InMemoryParkingSpotRepository, SystemClock, FakePaymentGateway
)

app = Flask(__name__)

# Инициализация зависимостей (как в main.py)
spots_repo = InMemoryParkingSpotRepository()
sessions_repo = InMemoryParkingSessionRepository()
payment_gateway = FakePaymentGateway()
system_clock = SystemClock()
tariff = Tariff(hourly_rate=Money(Decimal("100")), minimum_hours=1)

process = ParkingProcess(
    spots=spots_repo, sessions=sessions_repo, 
    payment_gateway=payment_gateway, clock=system_clock, tariff=tariff
)

# --- Общий обработчик исключений (Задача 4.1, п. 5) ---
@app.errorhandler(TransitionNotAllowed)
def handle_transition_not_allowed(e):
    return jsonify({"error": "TransitionNotAllowed", "message": str(e)}), 409

@app.errorhandler(DomainInvariantViolation)
@app.errorhandler(InvalidValueObject)
def handle_unprocessable(e):
    return jsonify({"error": "UnprocessableEntity", "message": str(e)}), 422

@app.errorhandler(EntityNotFound)
def handle_not_found(e):
    return jsonify({"error": "NotFound", "message": str(e)}), 404

@app.errorhandler(GatewayUnresolved)
def handle_internal_error(e):
    return jsonify({"error": "InternalServerError", "message": str(e)}), 500

# --- Бизнес-маршруты (Задача 4.1, п. 2) ---

@app.route("/parking/start", methods=["POST"])
def start_parking():
    data = request.json
    # Валидация входных данных
    plate = LicensePlate(data.get("license_plate", ""))
    vehicle_id = VehicleId(UUID(data.get("vehicle_id")))
    
    if process.check_blocklist(plate):
        return jsonify({"message": "Въезд запрещен: блок-лист"}), 403
        
    if not process.check_free_spots():
        return jsonify({"message": "Въезд запрещен: нет мест"}), 403
        
    spot = process.assign_spot(data.get("spot_number", "A-01"))
    session = process.start_session(spot, vehicle_id, plate)
    
    return jsonify({"session_id": str(session.session_id.value), "state": session.state}), 201

@app.route("/parking/<session_id>/pay", methods=["POST"])
def pay_parking(session_id):
    data = request.json
    amount = float(data.get("amount", 0))
    
    process.accept_payment(SessionId(UUID(session_id)), amount)
    return jsonify({"status": "ok", "message": "Оплата принята"}), 200

@app.route("/parking/<session_id>/exit", methods=["POST"])
def exit_parking(session_id):
    exit_time = system_clock.now() # Или можно передать из запроса
    process.process_exit(SessionId(UUID(session_id)), exit_time)
    return jsonify({"status": "ok", "message": "Сессия закрыта, место свободно"}), 200

# --- Получение состояния (Задача 4.1, п. 3) ---

@app.route("/parking/<session_id>", methods=["GET"])
def get_session_state(session_id):
    session = sessions_repo.get(SessionId(UUID(session_id)))
    return jsonify({
        "session_id": str(session.session_id.value),
        "state": session.state,
        "allowed_events": session.get_allowed_events(),
        "events": [{"type": e.__class__.__name__, "time": e.occurred_at.isoformat()} for e in session.events]
    }), 200

# --- Служебный маршрут для перевода часов (Задача 4.1, п. 6) ---

@app.route("/internal/tick", methods=["POST"])
def internal_tick():
    data = request.json or {}
    now_str = data.get("now")
    
    if now_str:
        try:
            now = datetime.fromisoformat(now_str)
        except ValueError:
            return jsonify({"error": "ValidationError", "message": "Неверный формат даты"}), 422
    else:
        now = system_clock.now()
        
    # Проходим по всем сессиям и вызываем таймеры ТОЛЬКО для активных
    for session in sessions_repo._storage.values():
        if session.state not in ("ClosedState"): # <--- ДОБАВИЛИ ЭТУ ПРОВЕРКУ
            session.on_timer_7_days(now)
            sessions_repo.save(session)
        
    return jsonify({"status": "ok", "message": f"Время переведено на {now.isoformat()}"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)