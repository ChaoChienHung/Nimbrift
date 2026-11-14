import posixpath
import tempfile
import unittest
from pathlib import Path
from threading import Event
from types import SimpleNamespace

from nimbrift.model import Connection, Direction, Transfer, TransferCancelled, TransferError
from nimbrift.service import TransferService
from nimbrift.sftp import SFTPTransport


class LocalSFTP:
    """Filesystem-backed stand-in that exercises the transport without a server."""

    def __init__(self, root: Path):
        self.root = root

    def path(self, remote: str) -> Path:
        normalized = posixpath.normpath(remote).lstrip("/")
        return self.root / normalized

    def lstat(self, remote: str):
        return self.path(remote).lstat()

    def mkdir(self, remote: str):
        self.path(remote).mkdir()

    def listdir_attr(self, remote: str):
        return [SimpleNamespace(filename=p.name) for p in self.path(remote).iterdir()]

    def put(self, local: str, remote: str, callback, confirm=True):
        data = Path(local).read_bytes()
        self.path(remote).write_bytes(data)
        callback(len(data), len(data))

    def get(self, remote: str, local: str, callback):
        data = self.path(remote).read_bytes()
        Path(local).write_bytes(data)
        callback(len(data), len(data))

    def rename(self, old: str, new: str):
        self.path(old).rename(self.path(new))

    def posix_rename(self, old: str, new: str):
        self.path(old).replace(self.path(new))

    def remove(self, remote: str):
        self.path(remote).unlink()


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / "remote"
        self.remote.mkdir()
        self.transport = SFTPTransport(Connection("example.test", "alice"))
        self.transport.sftp = LocalSFTP(self.remote)
        self.events = []

    def test_recursive_upload_and_download(self):
        source = self.root / "source"
        (source / "nested").mkdir(parents=True)
        (source / "nested" / "file.txt").write_text("hello")
        self.transport.execute(Transfer(Direction.UPLOAD, str(source), "/data"), self.events.append, Event())
        self.assertEqual((self.remote / "data/nested/file.txt").read_text(), "hello")
        destination = self.root / "download"
        self.transport.execute(Transfer(Direction.DOWNLOAD, "/data", str(destination)), self.events.append, Event())
        self.assertEqual((destination / "nested/file.txt").read_text(), "hello")
        self.assertEqual(len(self.events), 2)

    def test_overwrite_is_explicit_and_leaves_no_partial_file(self):
        source = self.root / "new.txt"
        source.write_text("new")
        (self.remote / "existing.txt").write_text("old")
        request = Transfer(Direction.UPLOAD, str(source), "/existing.txt")
        with self.assertRaises(TransferError):
            self.transport.execute(request, self.events.append, Event())
        self.assertEqual((self.remote / "existing.txt").read_text(), "old")
        self.transport.execute(Transfer(Direction.UPLOAD, str(source), "/existing.txt", True), self.events.append, Event())
        self.assertEqual((self.remote / "existing.txt").read_text(), "new")
        self.assertEqual(list(self.remote.glob("*.part")), [])

    def test_cancel_removes_temporary_download(self):
        (self.remote / "file.txt").write_text("content")
        cancellation = Event()

        def stop(_):
            cancellation.set()

        destination = self.root / "file.txt"
        with self.assertRaises(TransferCancelled):
            self.transport.execute(Transfer(Direction.DOWNLOAD, "/file.txt", str(destination)), stop, cancellation)
        self.assertFalse(destination.exists())
        self.assertEqual(list(self.root.glob("*.part")), [])

    def test_overwrite_without_posix_rename_extension(self):
        source = self.root / "new.txt"
        source.write_text("new")
        (self.remote / "existing.txt").write_text("old")

        def unsupported(*_):
            raise OSError("unsupported")

        self.transport.sftp.posix_rename = unsupported
        self.transport.execute(Transfer(Direction.UPLOAD, str(source), "/existing.txt", True), self.events.append, Event())
        self.assertEqual((self.remote / "existing.txt").read_text(), "new")
        self.assertEqual(list(self.remote.glob("*.backup")), [])

    def test_symlink_source_is_rejected(self):
        source = self.root / "real.txt"
        source.write_text("data")
        link = self.root / "link.txt"
        link.symlink_to(source)
        with self.assertRaises(TransferError):
            self.transport.execute(Transfer(Direction.UPLOAD, str(link), "/link.txt"), self.events.append, Event())

    def test_service_uses_injected_transport(self):
        calls = []

        class FakeTransport:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                calls.append("closed")

            def execute(self, request, progress, cancel):
                calls.append(request.direction)

        service = TransferService(lambda _: FakeTransport())
        service.run(Connection("example.test", "alice"), Transfer(Direction.UPLOAD, "a", "b"))
        self.assertEqual(calls, [Direction.UPLOAD, "closed"])


if __name__ == "__main__":
    unittest.main()
