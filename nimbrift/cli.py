"""Command line frontend for Nimbrift."""

import argparse
import getpass
import sys
from pathlib import Path
from threading import Event

from .model import Connection, Direction, Progress, Transfer, TransferCancelled, TransferError
from .service import TransferService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nimbrift", description="Secure SSH file transfers")
    sub = parser.add_subparsers(dest="command", required=True)
    for direction in (Direction.UPLOAD, Direction.DOWNLOAD):
        command = sub.add_parser(direction.value, help=f"{direction.value.title()} a file or directory")
        command.add_argument("source", help="Source file or directory")
        command.add_argument("destination", help="Destination file or directory")
        command.add_argument("--host", required=True, help="SSH host name or IP address")
        command.add_argument("--user", required=True, help="SSH username")
        command.add_argument("--port", type=int, default=22)
        command.add_argument("--key-file", type=Path, help="Private key path")
        command.add_argument("-J", "--jump-host", dest="jump_host", help="Jump host(s) e.g. jump1 or user@jump1,user@jump2")
        command.add_argument("--known-hosts", type=Path, help="Additional known_hosts file")
        command.add_argument("--ask-password", action="store_true", help="Prompt for SSH password")
        command.add_argument("--overwrite", action="store_true", help="Replace existing files")
    sub.add_parser("gui", help="Open the desktop interface")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "gui":
        from .gui import main as launch_gui

        return launch_gui()
    try:
        password = getpass.getpass("SSH password: ") if args.ask_password else None
        connection = Connection(
            host=args.host,
            username=args.user,
            port=args.port,
            key_file=args.key_file,
            known_hosts=args.known_hosts,
            password=password,
            jump_host=args.jump_host,
        )
        request = Transfer(Direction(args.command), args.source, args.destination, args.overwrite)
        last_path = ""

        def show_progress(item: Progress) -> None:
            nonlocal last_path
            if item.path != last_path:
                if last_path:
                    print(file=sys.stderr)
                last_path = item.path
            percent = 100 if item.total == 0 else item.transferred * 100 // item.total
            print(f"\r{item.path}: {percent:3d}% ({item.transferred}/{item.total} bytes)", end="", file=sys.stderr, flush=True)

        TransferService().run(connection, request, show_progress, Event())
        if last_path:
            print(file=sys.stderr)
        print("Transfer complete")
        return 0
    except (TransferCancelled, KeyboardInterrupt):
        print("Transfer cancelled", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Transfer failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
