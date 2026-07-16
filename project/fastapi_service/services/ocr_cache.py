import os, json

CACHE_PATH = os.getenv("OCR_CACHE_PATH", "ocr_cache.json")

def _load() -> dict:
    if not os.path.exists(CACHE_PATH):
        return {}
    with open(CACHE_PATH) as f:
        return json.load(f)

def _save(cache: dict) -> None:
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f)

def get_cached_ocr_result(content_hash: str) -> str | None:
    return _load().get(content_hash)

def store_ocr_result(content_hash: str, text: str) -> None:
    cache = _load()
    cache[content_hash] = text
    _save(cache)