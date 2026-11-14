"""Render Nimbrift's Qt brand mark into a macOS .icns file."""

import subprocess
import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication

from nimbrift.gui import app_icon


def main() -> int:
    if sys.platform != "darwin":
        raise SystemExit("App icon generation requires macOS iconutil")
    app = QGuiApplication.instance() or QGuiApplication([])
    iconset = Path("build/Nimbrift.iconset")
    iconset.mkdir(parents=True, exist_ok=True)
    for base in (16, 32, 128, 256, 512):
        for scale, suffix in ((1, ""), (2, "@2x")):
            size = base * scale
            image = app_icon(size).pixmap(size, size).toImage()
            if not image.save(str(iconset / f"icon_{base}x{base}{suffix}.png")):
                raise RuntimeError(f"Could not render {size}px icon")
    output = Path("build/Nimbrift.icns")
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(output)], check=True)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
