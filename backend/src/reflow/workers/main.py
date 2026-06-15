"""Background workers entrypoint.

Run via:
    python -m reflow.workers.main outbox

Each worker is a long-lived process. The CLI dispatches based on the first
positional argument.
"""

from __future__ import annotations

import asyncio
import signal
import sys

import click

from reflow.core.config import get_settings
from reflow.core.database import dispose_engine, init_engine
from reflow.core.events.outbox import run_relay_forever
from reflow.core.observability.logging import configure_logging, get_logger
from reflow.core.redis import close_redis_clients

_logger = get_logger(__name__)


async def _shutdown_signal(loop: asyncio.AbstractEventLoop) -> None:
    """Cooperative cancellation on SIGINT/SIGTERM."""
    for task in asyncio.all_tasks(loop):
        if task is not asyncio.current_task():
            task.cancel()


def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(
                sig, lambda: asyncio.create_task(_shutdown_signal(loop))
            )
        except (NotImplementedError, RuntimeError):
            # Windows: signal handlers via loop.add_signal_handler aren't supported.
            # SIGINT still triggers KeyboardInterrupt which we catch elsewhere.
            pass


async def _run_outbox() -> None:
    settings = get_settings()
    configure_logging(settings.observability)
    init_engine(settings.database)
    try:
        await run_relay_forever()
    finally:
        await close_redis_clients()
        await dispose_engine()


@click.group()
def cli() -> None:
    """Reflow background workers."""


@cli.command("outbox")
def outbox_command() -> None:
    """Run the transactional-outbox relay forever."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _install_signal_handlers(loop)
    try:
        loop.run_until_complete(_run_outbox())
    except (KeyboardInterrupt, asyncio.CancelledError):
        _logger.info("workers.outbox.exit")
    finally:
        loop.close()


if __name__ == "__main__":  # pragma: no cover
    cli(prog_name="reflow.workers")
    sys.exit(0)
