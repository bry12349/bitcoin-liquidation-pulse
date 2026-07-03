from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
LOG_PATH = ROOT / "data" / "server.log"


def main() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("ab", buffering=0) as log:
        subprocess.Popen(
            [str(ROOT / ".venv" / "bin" / "python"), str(ROOT / "app.py"), "--no-open", "--port", "8765"],
            cwd=ROOT,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    print("Bitcoin Liquidation Pulse started in background: http://127.0.0.1:8765")


if __name__ == "__main__":
    sys.exit(main())
