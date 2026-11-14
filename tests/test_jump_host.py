import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from nimbrift.model import Connection
from nimbrift.sftp import SFTPTransport, build_proxy_command


class JumpHostTests(unittest.TestCase):
    def test_build_proxy_command_single_hop(self):
        cmd = build_proxy_command("xlogin.comp.nus.edu.sg", 22, "stu")
        self.assertEqual(cmd, "ssh -W [xlogin.comp.nus.edu.sg]:22 stu")

    def test_build_proxy_command_multi_hop(self):
        cmd = build_proxy_command(
            "xlogin.comp.nus.edu.sg",
            22,
            "chaoch@stujump.comp.nus.edu.sg,chaoch@stu.comp.nus.edu.sg",
        )
        self.assertEqual(
            cmd,
            "ssh -J chaoch@stujump.comp.nus.edu.sg -W [xlogin.comp.nus.edu.sg]:22 chaoch@stu.comp.nus.edu.sg",
        )

    def test_build_proxy_command_three_hops(self):
        cmd = build_proxy_command("target.host", 2222, "hop1, hop2, hop3")
        self.assertEqual(cmd, "ssh -J hop1,hop2 -W [target.host]:2222 hop3")

    def test_build_proxy_command_empty_raises(self):
        with self.assertRaises(ValueError):
            build_proxy_command("target.host", 22, "   ,  ")

    def test_resolve_connection_from_ssh_config_proxyjump(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as f:
            f.write(
                "Host xlogin\n"
                "    HostName xlogin.comp.nus.edu.sg\n"
                "    Port 2222\n"
                "    User chaoch\n"
                "    ProxyJump stujump,stu\n"
            )
            config_path = Path(f.name)

        try:
            mock_paramiko = MagicMock()
            import paramiko
            mock_paramiko.SSHConfig = paramiko.SSHConfig
            mock_paramiko.ProxyCommand = MagicMock(side_effect=lambda c: f"PROXY:{c}")

            conn = Connection("xlogin", "chaoch")
            transport = SFTPTransport(conn)
            target_host, target_port, key_file, sock = transport._resolve_connection(
                mock_paramiko, config_path=config_path
            )

            self.assertEqual(target_host, "xlogin.comp.nus.edu.sg")
            self.assertEqual(target_port, 2222)
            self.assertEqual(
                sock,
                "PROXY:ssh -J stujump -W [xlogin.comp.nus.edu.sg]:2222 stu",
            )
        finally:
            config_path.unlink(missing_ok=True)

    def test_resolve_connection_from_ssh_config_proxycommand(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as f:
            f.write(
                "Host soc-backup\n"
                "    HostName xlogin.comp.nus.edu.sg\n"
                "    User chaoch\n"
                "    ProxyCommand ssh -J stujump stu nc %h %p\n"
            )
            config_path = Path(f.name)

        try:
            mock_paramiko = MagicMock()
            import paramiko
            mock_paramiko.SSHConfig = paramiko.SSHConfig
            mock_paramiko.ProxyCommand = MagicMock(side_effect=lambda c: f"PROXY:{c}")

            conn = Connection("soc-backup", "chaoch")
            transport = SFTPTransport(conn)
            target_host, target_port, key_file, sock = transport._resolve_connection(
                mock_paramiko, config_path=config_path
            )

            self.assertEqual(target_host, "xlogin.comp.nus.edu.sg")
            self.assertEqual(
                sock,
                "PROXY:ssh -J stujump stu nc xlogin.comp.nus.edu.sg 22",
            )
        finally:
            config_path.unlink(missing_ok=True)

    def test_explicit_jump_host_overrides_ssh_config(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as f:
            f.write(
                "Host target\n"
                "    HostName target.internal\n"
                "    ProxyJump config_jump\n"
            )
            config_path = Path(f.name)

        try:
            mock_paramiko = MagicMock()
            import paramiko
            mock_paramiko.SSHConfig = paramiko.SSHConfig
            mock_paramiko.ProxyCommand = MagicMock(side_effect=lambda c: f"PROXY:{c}")

            conn = Connection("target", "chaoch", jump_host="manual_jump")
            transport = SFTPTransport(conn)
            target_host, target_port, key_file, sock = transport._resolve_connection(
                mock_paramiko, config_path=config_path
            )

            self.assertEqual(target_host, "target.internal")
            self.assertEqual(sock, "PROXY:ssh -W [target.internal]:22 manual_jump")
        finally:
            config_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
