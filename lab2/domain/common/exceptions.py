class DomainError(Exception):
    """Базовое доменное исключение."""


class DomainInvariantViolation(DomainError):
    """Нарушение инварианта агрегата."""


class InvalidValueObject(DomainError):
    """Некорректное значение объекта-значения."""


class EntityNotFound(DomainError):
    """Сущность не найдена в репозитории."""

class TransitionNotAllowed(Exception):
    """Выбрасывается, когда событие недопустимо в текущем состоянии."""
    def __init__(self, state: str, event: str):
        self.state = state
        self.event = event
        super().__init__(f"Переход запрещен: событие '{event}' в состоянии '{state}'")

class GatewayUnresolved(Exception):
    """Выбрасывается, если ни одно условие шлюза не выполнено."""
    pass