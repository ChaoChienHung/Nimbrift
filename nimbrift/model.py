"""Public data types shared by the CLI, GUI, and transport adapters."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Direction(str, Enum):
    UPLOAD = "upload"
    DOWNLOAD = "download"


@dataclass(frozen=True)
class Connection:
    host: str
    username: str
    port: int = 22
    key_file: Path | None = None
    password: str | None = None
    known_hosts: Path | None = None
    jump_host: str | None = None

    def __post_init__(self) -> None:
        if not self.host.strip() or not self.username.strip():
            raise ValueError("Host and username are required")
        if not 1 <= self.port <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        if self.jump_host is not None and not self.jump_host.strip():
            object.__setattr__(self, "jump_host", None)


@dataclass(frozen=True)
class Transfer:
    direction: Direction
    source: str
    destination: str
    overwrite: bool = False

    def __post_init__(self) -> None:
        if not self.source.strip() or not self.destination.strip():
            raise ValueError("Source and destination are required")


@dataclass(frozen=True)
class Progress:
    path: str
    transferred: int
    total: int


class TransferCancelled(Exception):
    """The caller cancelled a transfer between or during files."""


class TransferError(Exception):
    """A transfer failed with a user-facing message."""
