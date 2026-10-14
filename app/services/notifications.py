from typing import Protocol


class NotificationSink(Protocol):
    """Contrato futuro; adaptadores externos não estão implementados nesta etapa."""
    def emit(self, event: dict) -> None: ...


class LocalNotificationSink:
    def emit(self, event: dict) -> None:
        # O alerta já está persistido junto à mensagem na mesma transação SQLite.
        pass
