"""SFTP transport adapter. Remote paths always use POSIX separators."""

import os
import posixpath
import stat
from collections.abc import Callable
from pathlib import Path
from threading import Event
from uuid import uuid4

from .model import Connection, Direction, Progress, Transfer, TransferCancelled, TransferError


def build_proxy_command(target_host: str, target_port: int, jump_spec: str) -> str:
    """Build an OpenSSH ProxyCommand string for single- or multi-hop jump hosts."""
    hops = [h.strip() for h in jump_spec.split(",") if h.strip()]
    if not hops:
        raise ValueError("Jump host specification cannot be empty")
    target = f"[{target_host}]:{target_port}"
    if len(hops) == 1:
        return f"ssh -W {target} {hops[0]}"
    prior = ",".join(hops[:-1])
    return f"ssh -J {prior} -W {target} {hops[-1]}"


class SFTPTransport:
    def __init__(self, connection: Connection):
        self.connection = connection
        self.client = None
        self.sftp = None
        self.sock = None

    def _resolve_connection(self, paramiko_module, config_path: Path | None = None):
        cfg_file = config_path if config_path is not None else Path("~/.ssh/config").expanduser()
        host_cfg = {}
        if cfg_file.is_file():
            try:
                ssh_config = paramiko_module.SSHConfig()
                with open(cfg_file) as f:
                    ssh_config.parse(f)
                host_cfg = ssh_config.lookup(self.connection.host)
            except Exception:
                host_cfg = {}

        target_host = host_cfg.get("hostname") or self.connection.host
        target_port = self.connection.port
        if target_port == 22 and "port" in host_cfg:
            try:
                target_port = int(host_cfg["port"])
            except ValueError:
                pass

        if self.connection.key_file:
            key_filename = str(self.connection.key_file.expanduser())
        elif "identityfile" in host_cfg:
            identities = host_cfg["identityfile"]
            if isinstance(identities, list):
                key_filename = [str(Path(p).expanduser()) for p in identities]
            else:
                key_filename = str(Path(identities).expanduser())
        else:
            key_filename = None

        sock = None
        jump_spec = self.connection.jump_host or host_cfg.get("proxyjump")
        if jump_spec:
            cmd = build_proxy_command(target_host, target_port, jump_spec)
            sock = paramiko_module.ProxyCommand(cmd)
        elif "proxycommand" in host_cfg:
            sock = paramiko_module.ProxyCommand(host_cfg["proxycommand"])

        return target_host, target_port, key_filename, sock

    def __enter__(self) -> "SFTPTransport":
        try:
            import paramiko
        except ImportError as exc:
            raise TransferError("Install Nimbrift first: pip install -e .") from exc
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        if self.connection.known_hosts:
            client.load_host_keys(str(self.connection.known_hosts.expanduser()))
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        target_host, target_port, key_filename, sock = self._resolve_connection(paramiko)
        self.sock = sock
        try:
            client.connect(
                hostname=target_host,
                port=target_port,
                username=self.connection.username,
                password=self.connection.password,
                key_filename=key_filename,
                sock=sock,
                allow_agent=True,
                look_for_keys=True,
                timeout=15,
                auth_timeout=15,
                banner_timeout=15,
            )
            self.sftp = client.open_sftp()
            self.client = client
        except Exception:
            if self.sock:
                self.sock.close()
                self.sock = None
            client.close()
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.sftp:
            self.sftp.close()
        if self.client:
            self.client.close()
        if self.sock:
            self.sock.close()
            self.sock = None

    def execute(self, request: Transfer, progress: Callable[[Progress], None], cancel: Event) -> None:
        if request.direction == Direction.UPLOAD:
            self._upload(Path(request.source).expanduser(), request.destination, request.overwrite, progress, cancel)
        elif request.direction == Direction.DOWNLOAD:
            self._download(request.source, Path(request.destination).expanduser(), request.overwrite, progress, cancel)
        else:
            raise TransferError(f"Unsupported direction: {request.direction}")

    @staticmethod
    def _check(cancel: Event) -> None:
        if cancel.is_set():
            raise TransferCancelled("Transfer cancelled")

    def _remote_stat(self, path: str):
        try:
            return self.sftp.lstat(path)
        except FileNotFoundError:
            return None

    def _remote_mkdirs(self, path: str) -> None:
        path = posixpath.normpath(path)
        if path in ("", ".", "/"):
            return
        info = self._remote_stat(path)
        if info is not None:
            if not stat.S_ISDIR(info.st_mode):
                raise TransferError(f"Remote path is not a directory: {path}")
            return
        self._remote_mkdirs(posixpath.dirname(path))
        self.sftp.mkdir(path)

    def _upload(self, source: Path, target: str, overwrite: bool, progress, cancel: Event) -> None:
        self._check(cancel)
        if source.is_symlink() or not source.exists():
            raise TransferError(f"Source is missing or is a symbolic link: {source}")
        target = posixpath.normpath(target)
        if source.is_dir():
            self._remote_mkdirs(target)
            for child in sorted(source.iterdir()):
                self._upload(child, posixpath.join(target, child.name), overwrite, progress, cancel)
            return
        if not source.is_file():
            raise TransferError(f"Source is not a regular file: {source}")
        info = self._remote_stat(target)
        if info is not None and stat.S_ISDIR(info.st_mode):
            target = posixpath.join(target, source.name)
            info = self._remote_stat(target)
        if info is not None and (not overwrite or not stat.S_ISREG(info.st_mode)):
            raise TransferError(f"Remote file exists (use --overwrite): {target}")
        self._remote_mkdirs(posixpath.dirname(target))
        temporary = f"{target}.nimbrift-{uuid4().hex}.part"
        try:
            def callback(sent: int, total: int) -> None:
                self._check(cancel)
                progress(Progress(str(source), sent, total))

            self.sftp.put(str(source), temporary, callback=callback, confirm=True)
            self._check(cancel)
            if overwrite and info is not None:
                try:
                    self.sftp.posix_rename(temporary, target)
                except OSError:
                    # Some SFTP servers lack the OpenSSH posix-rename extension.
                    backup = f"{target}.nimbrift-{uuid4().hex}.backup"
                    self.sftp.rename(target, backup)
                    try:
                        self.sftp.rename(temporary, target)
                    except Exception:
                        self.sftp.rename(backup, target)
                        raise
                    self.sftp.remove(backup)
            else:
                if self._remote_stat(target) is not None:
                    raise TransferError(f"Remote file appeared during transfer: {target}")
                self.sftp.rename(temporary, target)
        finally:
            try:
                self.sftp.remove(temporary)
            except FileNotFoundError:
                pass

    def _download(self, source: str, target: Path, overwrite: bool, progress, cancel: Event) -> None:
        self._check(cancel)
        source = posixpath.normpath(source)
        info = self._remote_stat(source)
        if info is None or stat.S_ISLNK(info.st_mode):
            raise TransferError(f"Remote source is missing or is a symbolic link: {source}")
        if stat.S_ISDIR(info.st_mode):
            if target.is_symlink() or (target.exists() and not target.is_dir()):
                raise TransferError(f"Local destination is not a directory: {target}")
            target.mkdir(parents=True, exist_ok=True)
            for entry in sorted(self.sftp.listdir_attr(source), key=lambda item: item.filename):
                name = entry.filename
                if name in (".", "..") or "/" in name or "\\" in name:
                    raise TransferError(f"Unsafe remote filename: {name}")
                self._download(posixpath.join(source, name), target / name, overwrite, progress, cancel)
            return
        if not stat.S_ISREG(info.st_mode):
            raise TransferError(f"Remote source is not a regular file: {source}")
        if target.is_symlink():
            raise TransferError(f"Local destination is a symbolic link: {target}")
        if target.is_dir():
            target = target / posixpath.basename(source)
        if target.is_symlink() or (target.exists() and not overwrite):
            raise TransferError(f"Local file exists (use --overwrite): {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.nimbrift-{uuid4().hex}.part")
        try:
            def callback(sent: int, total: int) -> None:
                self._check(cancel)
                progress(Progress(source, sent, total))

            self.sftp.get(source, str(temporary), callback=callback)
            self._check(cancel)
            if target.exists() and not overwrite:
                raise TransferError(f"Local file appeared during transfer: {target}")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
