"""Synchronous bridge for Strands agents used by the API and CLI.

Strands' convenience ``Agent(...)`` and ``Graph(...)`` calls create a short-
lived executor and ask ``asyncio.run`` to shut it down. On Python 3.14 that
shutdown can wait forever after a synchronous tool has completed. Tebaki's
FastAPI handlers are synchronous today, so keep one small bridge here: run the
coroutine on a private loop and close the loop without waiting for the SDK's
default executor. The agent implementation and all Strands event handling
remain unchanged.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


def run_sync[T](factory: Callable[[], Awaitable[T]]) -> T:
    """Run a Strands coroutine from sync code without executor shutdown hangs."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(factory())
    finally:
        asyncio.set_event_loop(None)
        loop.close()
