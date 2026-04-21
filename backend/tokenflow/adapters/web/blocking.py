from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import ParamSpec, TypeVar

import anyio

T = TypeVar("T")
P = ParamSpec("P")


async def run_blocking(func: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
    """Run sync I/O or CPU-bound work outside the FastAPI event loop."""
    return await anyio.to_thread.run_sync(partial(func, *args, **kwargs))
