"""
Entrypoint. Run with:  python main.py

On first run, this installs its own dependencies from requirements.txt
(so a fresh `pip install` step isn't a separate manual thing you have to
remember) and then restarts itself once they're available.
"""
from __future__ import annotations

import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))


def _ensure_dependencies() -> None:
    """Install requirements.txt automatically if anything is missing, then
    re-exec this same script so the newly installed packages are importable."""
    missing = False
    for module_name in ("neonize", "dotenv"):
        try:
            __import__(module_name)
        except ImportError:
            missing = True
            break

    if not missing:
        return

    print("First run detected — installing required Python packages...")
    requirements_path = os.path.join(_HERE, "requirements.txt")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_path])
    except subprocess.CalledProcessError as exc:
        print(f"Failed to install dependencies automatically: {exc}")
        print(f"Try running manually: pip install -r {requirements_path}")
        sys.exit(1)

    print("Dependencies installed. Restarting...")
    os.execv(sys.executable, [sys.executable] + sys.argv)


_ensure_dependencies()

# Everything below this line depends on packages that _ensure_dependencies()
# just guaranteed are installed, so these imports are safe here.
import logging  # noqa: E402
import signal  # noqa: E402

from app.config import Config  # noqa: E402
from app.health_server import start_health_server  # noqa: E402
from app.status_bot import StatusBot  # noqa: E402


def main() -> None:
    Config.validate()

    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("main")

    start_health_server(Config.PORT)
    logger.info("Health check server listening on port %s", Config.PORT)

    bot = StatusBot(Config)

    def _handle_signal(signum, _frame) -> None:
        logger.info("Received signal %s, shutting down", signum)
        bot.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    bot.run()


if __name__ == "__main__":
    main()
