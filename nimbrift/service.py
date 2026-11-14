"""Application boundary: both frontends submit the same transfer request."""

from collections.abc import Callable
from threading import Event
from typing import Protocol

from .model import Connection, Progress, Transfer
from .sftp import SFTPTransport


class Transport(Protocol):
    def __enter__(self) -> "Transport": ...
    def __exit__(self, exc_type: object, exc: object, tb: object) -> None: ...
    def execute(
        self, request: Transfer, progress: Callable[[Progress], None], cancel: Event
    ) -> None: ...


class TransferService:
    """Transport factory is injectable for tests and future backends."""

    def __init__(self, factory: Callable[[Connection], Transport] = SFTPTransport):
        self._factory = factory

    def run(
        self,
        connection: Connection,
        request: Transfer,
        progress: Callable[[Progress], None] = lambda _: None,
        cancel: Event | None = None,
    ) -> None:
        cancellation = cancel if cancel is not None else Event()
        with self._factory(connection) as transport:
            transport.execute(request, progress, cancellation)
