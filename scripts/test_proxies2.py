import argparse
import concurrent.futures
import json
import re
import time
from pathlib import Path

import requests

SOURCE_URLS = (
    "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/elite.txt"
)
TEST_URL = "https://www.gstatic.com/generate_204"
TIMEOUT = 8
MAX_WORKERS = 200
FAST_LATENCY_MS = 1500

OUTPUT_FILE = Path("valid-2.txt")
FAST_FILE = Path("fast-2.txt")
STATS_FILE = Path("stats-2.json")

PROXY_PATTERN = re.compile(r"^(https?|socks5)://([^:\s]+):(\d+)$", re.I)
BARE_PROXY_PATTERN = re.compile(r"^[^:/\s]+:\d+$")


def create_direct_session() -> requests.Session:
    """Ignore machine-level HTTP(S)_PROXY / ALL_PROXY environment variables."""
    session = requests.Session()
    session.trust_env = False
    session.proxies.clear()
    return session


def parse_source_proxies(content: str) -> set[str]:
    """Parse protocol-qualified entries and probe HProxy's bare IP:port entries."""
    proxies: set[str] = set()
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if PROXY_PATTERN.fullmatch(line):
            proxies.add(line)
        elif BARE_PROXY_PATTERN.fullmatch(line):
            # HProxy's elite.txt does not include protocols. Probe supported
            # schemes; SOCKS4 remains excluded.
            proxies.update(f"{scheme}://{line}" for scheme in ("http", "https", "socks5"))
    return proxies


def download_proxies() -> tuple[list[str], str]:
    """Download and merge all configured source lists, using the configured proxy if available."""
    errors: list[str] = []
    merged_proxies: set[str] = set()
    successful_sources: list[str] = []

    for source_url in SOURCE_URLS:
        try:
            # Keep trust_env enabled for source downloads so Requests can use
            # configured HTTP(S)_PROXY / ALL_PROXY or the OS proxy settings.
            with requests.Session() as session:
                response = session.get(source_url, timeout=30)
                response.raise_for_status()
                content = response.text

            source_proxies = parse_source_proxies(content)
            if source_proxies:
                merged_proxies.update(source_proxies)
                successful_sources.append(source_url)
                print(f"Proxy source loaded: {source_url}")
                print(f"Source proxies: {len(source_proxies)}")
            else:
                message = "download succeeded but contained no supported proxy entries"
                print(f"[SOURCE FAIL] {source_url}: {message}")
                errors.append(f"{source_url}: {message}")
        except requests.RequestException as exc:
            message = f"{type(exc).__name__}: {exc}"
            print(f"[SOURCE FAIL] {source_url}: {message}")
            errors.append(f"{source_url}: {message}")

    if not merged_proxies:
        details = "\n".join(f"  - {item}" for item in errors)
        raise SystemExit(
            "Could not download proxy entries from any source.\n"
            "Source downloads may use the computer's configured proxy; proxy-node "
            "tests still ignore local proxy settings.\n"
            f"{details}"
        )

    print(f"Proxy sources loaded: {len(successful_sources)}/{len(SOURCE_URLS)}")
    print(f"Total unique proxies after merging: {len(merged_proxies)}")
    print("Source download: computer-configured proxy/direct fallback")
    return sorted(merged_proxies), ";".join(successful_sources)

def test_proxy(proxy: str):
    """Test this node through itself; never fall back to environment proxies."""
    started = time.perf_counter()
    try:
        with create_direct_session() as session:
            with session.get(
                TEST_URL,
                proxies={"http": proxy, "https": proxy},
                timeout=TIMEOUT,
                allow_redirects=False,
            ) as response:
                latency_ms = (time.perf_counter() - started) * 1000
                if response.status_code == 204:
                    return proxy, round(latency_ms, 1)
    except requests.RequestException:
        pass
    except Exception:
        pass
    return None


def update_opencode_config(config_path: Path, proxies: list[str]) -> None:
    """Replace only proxies/proxyfile while preserving the rest of config.json."""
    if not proxies:
        raise SystemExit(
            "No fast proxies passed the test; config.json was left unchanged."
        )

    config_path = config_path.expanduser().resolve()
    if not config_path.is_file():
        raise SystemExit(f"Config file not found: {config_path}")

    try:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read valid JSON config {config_path}: {exc}") from exc

    if not isinstance(config, dict):
        raise SystemExit(f"Config root must be a JSON object: {config_path}")

    # Fast test results become the active pool. Removing direct prevents
    # anonymous requests from bypassing the tested proxy nodes.
    config["proxies"] = proxies
    config["proxyfile"] = ""

    temp_path = config_path.with_name(config_path.name + ".tmp")
    try:
        temp_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(config_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    print(f"Updated config: {config_path}")
    print(f"Active proxy nodes: {len(proxies)}")
    print("proxyfile cleared; direct node removed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test public proxies and optionally update opencode2api config.json."
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="local opencode2api config.json path; omit when running in GitHub Actions",
    )
    args = parser.parse_args()

    proxies, source_used = download_proxies()
    print("Local environment proxies: DISABLED")
    print("Download source: computer-configured proxy if available")
    print("Each proxy test: routed only through that tested proxy")

    valid: list[tuple[str, float]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(test_proxy, proxy) for proxy in proxies]
        for index, future in enumerate(
            concurrent.futures.as_completed(futures), start=1
        ):
            result = future.result()
            if result:
                valid.append(result)
                print(f"[OK] {result[1]:7.1f} ms  {result[0]}")
            if index % 500 == 0 or index == len(proxies):
                print(f"Progress: {index}/{len(proxies)} valid={len(valid)}")

    valid.sort(key=lambda item: item[1])
    fast = [item for item in valid if item[1] < FAST_LATENCY_MS]

    OUTPUT_FILE.write_text(
        "".join(f"{proxy}\n" for proxy, _ in valid),
        encoding="utf-8",
    )
    FAST_FILE.write_text(
        "".join(f"{proxy}\n" for proxy, _ in fast),
        encoding="utf-8",
    )

    stats = {
        "source": source_used,
        "test_url": TEST_URL,
        "tested": len(proxies),
        "valid": len(valid),
        "fast_lt_1500ms": len(fast),
        "generated_at_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        ),
    }
    STATS_FILE.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(stats, indent=2))

    if not valid:
        raise SystemExit("No valid proxies found")

    if args.config:
        update_opencode_config(
            args.config,
            [proxy for proxy, _ in fast],
        )
    else:
        print(
            "config.json not modified. Run locally with "
            '--config "PATH_TO_opencode2api/config.json" to update it.'
        )


if __name__ == "__main__":
    main()
