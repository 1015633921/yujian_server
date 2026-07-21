from __future__ import annotations

import argparse
import logging
import time

from .observability import configure_logging, log_event
from .runtime_tasks import CommerceMaintenanceTaskRunner, commerce_maintenance_enabled


LOGGER = logging.getLogger("yujian.commerce.worker")


def run(once: bool = False) -> int:
    configure_logging()
    if not commerce_maintenance_enabled():
        log_event(LOGGER, "commerce.worker.disabled", result="disabled")
        return 0
    runner = CommerceMaintenanceTaskRunner()
    log_event(LOGGER, "commerce.worker.started", result="started", mode="once" if once else "loop")
    while True:
        result = runner.run_once()
        if once:
            return 0 if result.get("status") in {"completed", "skipped_locked"} else 1
        time.sleep(runner.interval_seconds())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run independent commerce maintenance")
    parser.add_argument("--once", action="store_true", help="run one scheduled attempt and exit")
    args = parser.parse_args()
    raise SystemExit(run(args.once))


if __name__ == "__main__":
    main()
