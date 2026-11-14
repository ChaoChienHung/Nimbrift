import contextlib
import io
import unittest
from unittest.mock import patch

from nimbrift.cli import main
from nimbrift.model import Direction


class CliTests(unittest.TestCase):
    def test_upload_request_reaches_shared_service(self):
        with patch("nimbrift.cli.TransferService") as service, contextlib.redirect_stdout(io.StringIO()) as output:
            code = main(["upload", "local.txt", "/remote.txt", "--host", "example.test", "--user", "alice"])
        self.assertEqual(code, 0)
        connection, request, *_ = service.return_value.run.call_args.args
        self.assertEqual((connection.host, connection.username), ("example.test", "alice"))
        self.assertIsNone(connection.jump_host)
        self.assertEqual((request.direction, request.source, request.destination), (Direction.UPLOAD, "local.txt", "/remote.txt"))
        self.assertIn("Transfer complete", output.getvalue())

    def test_jump_host_flag(self):
        with patch("nimbrift.cli.TransferService") as service, contextlib.redirect_stdout(io.StringIO()):
            code = main([
                "upload", "local.txt", "/remote.txt",
                "--host", "example.test",
                "--user", "alice",
                "-J", "chaoch@stujump.comp.nus.edu.sg,chaoch@stu.comp.nus.edu.sg",
            ])
        self.assertEqual(code, 0)
        connection, *_ = service.return_value.run.call_args.args
        self.assertEqual(connection.jump_host, "chaoch@stujump.comp.nus.edu.sg,chaoch@stu.comp.nus.edu.sg")

    def test_invalid_port_fails_before_network_call(self):
        with patch("nimbrift.cli.TransferService") as service, contextlib.redirect_stderr(io.StringIO()) as errors:
            code = main(["download", "/remote.txt", "local.txt", "--host", "example.test", "--user", "alice", "--port", "70000"])
        self.assertEqual(code, 1)
        service.assert_not_called()
        self.assertIn("Port must be between", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
