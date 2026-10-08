import concurrent.futures
import json
import re
import time
from pathlib import Path

import requests

SOURCE_URL = "https://cdn.jsdelivr.net/gh/proxyscrape/free-proxy-list@main/proxies/all/data.txt"
TEST_URL = "https://www.gstatic.com/generate_204"
TIMEOUT = 8
MAX_WORKERS = 200
FAST_LATENCY_MS = 1500

OUTPUT_FILE = Path("valid.txt")
FAST_FILE = Path("fast.txt")
STATS_FILE = Path("stats.json")

PROXY_PATTERN = re.compile(r"^(https?|socks5)://([^:\s]+):(\d+)$", re.I)


def download_proxies() -> list[str]:
    response = requests.get(SOURCE_URL, timeout=30)
    response.raise_for_status()

    proxies: set[str] = set()
    for line in response.text.splitlines():
        proxy = line.strip()
        if PROXY_PATTERN.fullmatch(proxy):
            proxies.add(proxy)
    return sorted(proxies)


def test_proxy(proxy: str):
    started = time.perf_counter()
    try:
        response = requests.get(
            TEST_URL,
            proxies={"http": proxy, "https": proxy},
            timeout=TIMEOUT,
            allow_redirects=False,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        if response.status_code == 204:
            return proxy, round(latency_ms, 1)
    except requests.RequestException:
        pass
    except Exception:
        pass
    return None


def main() -> None:
    proxies = download_proxies()
    print(f"Source proxies: {len(proxies)}")

    valid: list[tuple[str, float]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(test_proxy, proxy) for proxy in proxies]
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            result = future.result()
            if result:
                valid.append(result)
                print(f"[OK] {result[1]:7.1f} ms  {result[0]}")
            if index % 500 == 0:
                print(f"Progress: {index}/{len(proxies)} valid={len(valid)}")

    valid.sort(key=lambda item: item[1])
    fast = [item for item in valid if item[1] < FAST_LATENCY_MS]

    OUTPUT_FILE.write_text(
        "".join(f"{proxy}\n" for proxy, _ in valid),
        encoding="utf-8",
    )
    FAST_FILE.write_text(
        "".join(f"{proxy}\n" for proxy, _ in fast)
        encoding="utf-8",
    )

    stats = {
        "source": SOURCE_URL,
        "test_url": TEST_URL,
        "tested": len(proxies),
        "valid": len(valid),
        "fast_lt_1500ms": len(fast),
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    STATS_FILE.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(stats, indent=2))

    if not valid:
        raise SystemExit("No valid proxies found")


if __name__ == "__main__":
    main()
