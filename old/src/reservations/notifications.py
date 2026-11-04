"""Notification Integration (C03 G2): doručení e-mailu a záznam výsledku SENT / FAILED (REQ-09).

Skutečná Notification Service neexistuje (stejně jako v C02), proto ji zastupuje
EmailServiceStub. Jiná implementace stačí předat NotificationIntegration.
"""
from dataclasses import dataclass
from typing import List, Protocol


class NotificationUnavailable(Exception):
    pass


class EmailTransport(Protocol):
    """Rozhraní externí Notification Service: odešle e-mail, nebo vyhodí výjimku."""

    def send(self, to: str, subject: str, body: str) -> None: ...


class EmailServiceStub:
    """Náhradní Notification Service pro walking skeleton a testy; `available` simuluje výpadek."""

    def __init__(self, available: bool = True):
        self.available = available

    def send(self, to: str, subject: str, body: str) -> None:
        if not self.available:
            raise NotificationUnavailable("Notification Service is unavailable")


@dataclass
class NotificationRecord:
    to: str
    subject: str
    status: str  # SENT / FAILED


class NotificationIntegration:
    """Implementace kontraktu service.Notifier. Žádná chyba služby nedoběhne k volajícímu."""

    def __init__(self, transport: EmailTransport):
        self.transport = transport
        self.log: List[NotificationRecord] = []

    def send(self, to: str, subject: str, body: str) -> None:
        status = "SENT"
        try:
            self.transport.send(to, subject, body)
        except Exception:  # NotificationUnavailable, timeout, chyba sítě...
            status = "FAILED"
        self.log.append(NotificationRecord(to, subject, status))
