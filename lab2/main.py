from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from domain.common.values import Money
from domain.library.aggregates import Book, Reader
from domain.library.service import LibraryService
from domain.library.values import FullName, ISBN, TicketNumber
from domain.parking.values import (
    LicensePlate, ParkingPolicy, Tariff, VehicleId,
)
from infra.library_memory import (
    InMemoryBookRepository, InMemoryLoanRepository,
    InMemoryReaderRepository,
)
from infra.parking_memory import (
    InMemoryParkingSessionRepository, InMemoryParkingSpotRepository,
)
from domain.parking.aggregates import ParkingSpot
from domain.parking.service import ParkingProcess
from domain.parking.values import Tariff, VehicleId, LicensePlate, SpotId, SessionId
from infra.parking_memory import (
    InMemoryParkingSessionRepository, 
    InMemoryParkingSpotRepository,
    SystemClock,
    FakePaymentGateway
)


def demo_library() -> None:
    print("БИБЛИОТЕКА")

    books = InMemoryBookRepository()
    readers = InMemoryReaderRepository()
    loans = InMemoryLoanRepository()
    service = LibraryService(
        books=books, readers=readers, loans=loans,
        fine_per_day=Money(Decimal("100")),
    )

    book = Book.create("Мастер и Маргарита", "М.А. Булгаков",
                       ISBN("978-5-04-116543-3"))
    book.add_copy()
    book.add_copy()
    book.add_copy()
    books.save(book)
    print(f"Книга: {book.title} (всего {book.total_count()} экз.)")

    reader = Reader.create(
        FullName("Иван", "Иванов", "Иванович"),
        TicketNumber("ЧБ-0001"),
    )
    readers.save(reader)
    print(f"Читатель: {reader.full_name} (билет {reader.ticket_number})")

    copy_id = book.copies()[0].id
    loan = service.issue_book(book.book_id, copy_id, reader.reader_id,
                              date.today(), loan_days=14)
    print(f"Выдано. Доступно: {book.available_count()}")

    return_date = date.today() + timedelta(days=19)
    fine = service.return_book(loan.loan_id, return_date)
    print(f"Возврат. Штраф: {fine}")
    print(f"Доступно после возврата: {book.available_count()}")

    try:
        service.return_book(loan.loan_id, return_date)
    except Exception as e:
        print(f"Инвариант сработал: {e}")

    for _ in range(3):
        free = [c for c in book.copies() if not c.on_loan]
        if not free:
            print(f"Инвариант сработал: нет свободных экземпляров")
            break
        try:
            service.issue_book(book.book_id, free[0].id,
                               reader.reader_id, date.today())
            print(f"Выдано ещё, осталось: {book.available_count()}")
        except Exception as e:
            print(f"Инвариант сработал: {e}")
            break

def demo_parking() -> None:
    print()
    print("=" * 55)
    print("ПАРКОВКА (ЛАБОРАТОРНАЯ 3)")
    print("=" * 55)

    spots = InMemoryParkingSpotRepository()
    sessions = InMemoryParkingSessionRepository()
    clock = SystemClock()
    payment_gateway = FakePaymentGateway()
    tariff = Tariff(hourly_rate=Money(Decimal("100")), minimum_hours=1)
    
    # Создаем прикладной сервис
    process = ParkingProcess(
        spots=spots, sessions=sessions, 
        payment_gateway=payment_gateway, clock=clock, tariff=tariff
    )

    # 1. Проверка блок-листа и мест
    vehicle_id = VehicleId(uuid4())
    plate_ok = LicensePlate("А123ВС77")
    
    if process.check_blocklist(plate_ok):
        print("Въезд запрещен: автомобиль в блок-листе")
        return
        
    if not process.check_free_spots():
        print("Въезд запрещен: нет свободных мест")
        return

    # 2. Назначаем место и стартуем сессию
    spot = process.assign_spot("A-01")
    session = process.start_session(spot, vehicle_id, plate_ok)
    print(f"Сессия начата. Текущее состояние: {session.state}")
    

    # 3. Попытка выехать без оплаты (Шлюз не пройден)
    try:
        process.process_exit(session.session_id, clock.now())
    except Exception as e:
        print(f"Шлюз не пройден: {e}")

    # 4. Водитель оплачивает
    process.accept_payment(session.session_id, 300.0)
    print(f"Оплата принята. Состояние: {session.state}")

    # 5. Попытка доплаты (прошло меньше 15 минут, должна быть ошибка инварианта)
    try:
        session.pay_extra(100.0)
    except Exception as e:
        print(f"Инвариант сработал: {e}")

    # 6. Выезд
    exit_time = clock.now() + timedelta(hours=2, minutes=30)
    process.process_exit(session.session_id, exit_time)
    print(f"Сессия закрыта. Состояние: {session.state}")
    print(f"Статус места: {spot.status.value}")
    
    # 7. Демонстрация таймера 7 суток на новой сессии
    session2 = process.start_session(process.assign_spot("B-02"), VehicleId(uuid4()), LicensePlate("В456ЕК99"))
    print(f"Новая сессия. Состояние: {session2.state}")
    
    # Имитируем, что прошло 8 дней (7 суток + 1 день)
    # Мы берем время въезда и прибавляем к нему 8 дней
    time_after_8_days = session2.interval.entry_time + timedelta(days=8)
    
    # Передаем это время в метод таймера
    session2.on_timer_7_days(time_after_8_days) 
    
    print(f"Сработал таймер 7 суток. Состояние: {session2.state}")
    print(f"Журнал событий сессии: {session2.events}")

if __name__ == "__main__":
    demo_library() # Оставляем для проверки, что ничего не сломалось
    demo_parking()