"""Process-wide cap on concurrent borsapy calls.

borsapy talks to TradingView over websockets, and those connections start
failing once too many run at once: measured 12/12 symbols OK at <=6 concurrent
calls, but only 7/12 at 10-15 ("Connection is already closed",
"'NoneType' object has no attribute 'sock'"). Pool sizes alone can't enforce
this because several pools (ticker, movers, detail) plus several gunicorn
threads can be active at the same time, so the ceiling has to be global.

A plain Semaphore was not enough. Those websocket calls have no timeout of
their own, so a wedged one held its slot forever; once MAX_CONCURRENT of them
piled up, every later request blocked indefinitely and the whole app looked
dead while /health still answered. Hence two guards here:

  * waiters give up after WAIT_TIMEOUT instead of blocking forever, so a busy
    moment degrades to an error message rather than a hang;
  * a slot held longer than MAX_HOLD is presumed lost and reclaimed. The stuck
    thread cannot be killed from Python, but it stops counting against the cap.
"""
import threading
import time

MAX_CONCURRENT = 5
MAX_HOLD = 60.0        # a call still running after this is treated as wedged
WAIT_TIMEOUT = 25.0    # how long a caller waits for a free slot
# The home page queues ~47 calls at once (15 ticker symbols + 30 movers + the
# index), which at five slots takes ~25s to drain and starved every other page
# meanwhile. Bulk work is capped below the total so a page a visitor is actually
# waiting on always has room.
BULK_CONCURRENT = 3


class _Limiter:
    def __init__(self, limit, max_hold, wait):
        self._limit = limit
        self._max_hold = max_hold
        self._wait = wait
        self._cv = threading.Condition()
        self._active = {}          # token -> acquisition time

    def _prune(self, now):
        for token, started in list(self._active.items()):
            if now - started >= self._max_hold:
                del self._active[token]

    def acquire(self, limit=None):
        ceiling = self._limit if limit is None else min(limit, self._limit)
        deadline = time.monotonic() + self._wait
        with self._cv:
            while True:
                now = time.monotonic()
                self._prune(now)
                if len(self._active) < ceiling:
                    token = object()
                    self._active[token] = now
                    return token
                left = deadline - now
                if left <= 0:
                    raise TimeoutError("borsapy is busy; no free slot")
                self._cv.wait(min(left, 1.0))

    def release(self, token):
        with self._cv:
            self._active.pop(token, None)   # may already have been pruned
            self._cv.notify()

    @property
    def in_flight(self):
        with self._cv:
            self._prune(time.monotonic())
            return len(self._active)


_limiter = _Limiter(MAX_CONCURRENT, MAX_HOLD, WAIT_TIMEOUT)


def guarded(fn, *args, **kwargs):
    """Run fn under the global concurrency cap."""
    token = _limiter.acquire()
    try:
        return fn(*args, **kwargs)
    finally:
        _limiter.release(token)


def guarded_bulk(fn, *args, **kwargs):
    """Same cap, but for background/list fetches that must not crowd out the
    page a visitor is waiting on."""
    token = _limiter.acquire(limit=BULK_CONCURRENT)
    try:
        return fn(*args, **kwargs)
    finally:
        _limiter.release(token)


def in_flight():
    """Slots currently held — useful when diagnosing a stall."""
    return _limiter.in_flight
