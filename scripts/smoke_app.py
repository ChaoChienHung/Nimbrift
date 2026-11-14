"""Verify the packaged GUI stays alive long enough to initialize."""

import os
import subprocess
import time
from pathlib import Path


def main() -> int:
    executable = Path("dist/Nimbrift.app/Contents/MacOS/Nimbrift")
    if not executable.is_file():
        raise SystemExit(f"Missing bundled executable: {executable}")
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    process = subprocess.Popen([str(executable)], env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        time.sleep(3)
        if process.poll() is not None:
            error = process.stderr.read().decode(errors="replace")[:1000]
            raise RuntimeError(f"Bundled app exited early ({process.returncode}): {error}")
        print("Bundled app initialized successfully")
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
