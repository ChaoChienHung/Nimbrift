"""Compatibility entry point. Use `nimbrift upload` for new scripts."""

from nimbrift.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["upload", *__import__("sys").argv[1:]]))
