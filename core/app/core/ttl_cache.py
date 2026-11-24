# app/core/ttl_cache.py

import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Hashable
from typing import Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """Remembers answers for a short while, within one worker. Callers that miss at once wait for the first one's answer
    rather than each asking the database, which is what keeps a busy thread cheap as its answer expires."""

    def __init__(self, seconds: float, max_entries: int) -> None:
        self.seconds = seconds
        self.max_entries = max_entries
        self._entries: OrderedDict[Hashable, tuple[float, T]] = OrderedDict()
        self._loading: dict[Hashable, asyncio.Future[T]] = {}

    async def get(self, key: Hashable, load: Callable[[], Awaitable[T]]) -> T:
        if self.seconds <= 0:
            return await load()

        while True:
            entry = self._entries.get(key)
            if entry is not None and entry[0] > time.monotonic():
                self._entries.move_to_end(key)
                return entry[1]
            waiting = self._loading.get(key)
            if waiting is None:
                break
            # One whose request was cancelled leaves the next of these to load it; one that failed fails them all, since
            # taking turns would only queue them up behind whatever is wrong
            await asyncio.wait([waiting])
            if not waiting.cancelled():
                return waiting.result()

        future: asyncio.Future[T] = asyncio.get_running_loop().create_future()
        self._loading[key] = future
        try:
            value = await load()
        except Exception as error:
            future.set_exception(error)
            future.exception()  # nobody may be waiting for it
            raise
        except BaseException:
            future.cancel()
            raise
        else:
            # Unless it was cleared meanwhile: this was read before whatever changed
            if self._loading.get(key) is future:
                self._entries[key] = (time.monotonic() + self.seconds, value)
                self._entries.move_to_end(key)
                while len(self._entries) > self.max_entries:
                    self._entries.popitem(last=False)
            future.set_result(value)
            return value
        finally:
            if self._loading.get(key) is future:
                del self._loading[key]

    def clear(self) -> None:
        self._entries.clear()
        self._loading.clear()
