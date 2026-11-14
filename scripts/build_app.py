"""Run tests, then build a double-clickable Nimbrift.app on macOS."""

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Test and build the Nimbrift macOS app")
    parser.add_argument("--skip-tests", action="store_true", help="Use only when a prior CI job has passed")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    if sys.platform != "darwin":
        parser.error("The macOS .app must be built on macOS")
    if not args.skip_tests:
        subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=root, check=True)
    for module in ("PySide6", "PyInstaller", "paramiko"):
        if importlib.util.find_spec(module) is None:
            parser.error(f"Missing {module}; run: python -m pip install -e '.[build]'")
    subprocess.run([sys.executable, "scripts/make_icon.py"], cwd=root, check=True)
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
            "--name", "Nimbrift", "--icon", str(root / "build/Nimbrift.icns"),
            "--osx-bundle-identifier", "io.github.chaochienhung.nimbrift",
            "--specpath", "build", "--workpath", "build/pyinstaller", "--distpath", "dist",
            "gui_main.py",
        ],
        cwd=root,
        check=True,
    )
    bundle = root / "dist/Nimbrift.app"
    if not (bundle / "Contents/MacOS/Nimbrift").is_file():
        raise RuntimeError("PyInstaller completed without a usable app bundle")
    print(f"Built {bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
