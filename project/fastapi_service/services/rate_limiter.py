
import time
import threading

_buckets: dict[str, dict] = {}
_lock = threading.Lock()


DEFAULT_CAPACITY = 20      # max tokens held at once
DEFAULT_REFILL_RATE = 5    # tokens added per second


def _get_bucket(bucket: str) -> dict:
    if bucket not in _buckets:
        _buckets[bucket] = {
            "tokens": DEFAULT_CAPACITY,
            "last_refill": time.monotonic(),
        }
    return _buckets[bucket]



def acquire_token(bucket: str, capacity: int = DEFAULT_CAPACITY,
                   refill_rate: float = DEFAULT_REFILL_RATE) -> None:
    """Blocks (briefly) until a token is available for the given bucket."""
    while True:
        with _lock:
            state = _get_bucket(bucket)
            now = time.monotonic()
            elapsed = now - state["last_refill"]
            state["tokens"] = min(capacity, state["tokens"] + elapsed * refill_rate)
            state["last_refill"] = now

            if state["tokens"] >= 1:
                state["tokens"] -= 1
                return

        time.sleep(0.1)
