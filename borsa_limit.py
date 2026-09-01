"""Process-wide cap on concurrent borsapy calls.

borsapy talks to TradingView over websockets, and those connections start
failing once too many run at once: measured 12/12 symbols OK at <=6 concurrent
calls, but only 7/12 at 10-15 ("Connection is already closed",
"'NoneType' object has no attribute 'sock'"). Pool sizes alone can't enforce
this because several pools (ticker, movers, detail) plus several gunicorn
threads can be active at the same time, so the ceiling has to be global.
"""
import threading

MAX_CONCURRENT = 5
_sem = threading.Semaphore(MAX_CONCURRENT)


def guarded(fn, *args, **kwargs):
    """Run fn under the global concurrency cap."""
    with _sem:
        return fn(*args, **kwargs)
