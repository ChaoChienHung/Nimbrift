"""Compatibility entry point. Use `nimbrift download` for new scripts."""

from nimbrift.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["download", *__import__("sys").argv[1:]]))
