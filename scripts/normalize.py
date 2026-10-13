from __future__ import annotations

import csv
import sys
from pathlib import Path

VALID_PROTOCOLS = {"http", "https", "socks4", "socks5"}
VALID_PREFIXES = ("http://", "https://", "socks4://", "socks5://")


def load_hproxy_csv(path: Path) -> set[str]:
    proxies: set[str] = set()

    if not path.exists():
        return proxies

    with path.open(encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            alive = str(row.get("alive") or "").lower()
            if alive != "true":
                continue

            ip = (row.get("ip") or "").strip()
            port = (row.get("port") or "").strip()
            if not ip or not port:
                continue

            protocols = row.get("protocols")
            if protocols is None:
                protocols = "http"

            for protocol in protocols.split(","):
                protocol = protocol.strip().lower()
                if protocol in VALID_PROTOCOLS:
                    proxies.add(f"{protocol}://{ip}:{port}")

    return proxies


def load_proxifly_txt(path: Path) -> set[str]:
    proxies: set[str] = set()

    if not path.exists():
        return proxies

    with path.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            proxy = line.strip()
            if proxy and proxy.startswith(VALID_PREFIXES):
                proxies.add(proxy)

    return proxies


def write_proxies(path: Path, proxies: set[str]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for proxy in sorted(proxies):
            f.write(f"{proxy}\n")


def main() -> None:
    if len(sys.argv) != 4:
        print(
            f"Usage: {Path(sys.argv[0]).name} "
            "<hproxy_live.csv> <proxifly_data.txt> <output.txt>",
            file=sys.stderr,
        )
        raise SystemExit(1)

    csv_file = Path(sys.argv[1])
    proxifly_file = Path(sys.argv[2])
    output = Path(sys.argv[3])

    proxies: set[str] = set()
    proxies.update(load_hproxy_csv(csv_file))
    proxies.update(load_proxifly_txt(proxifly_file))

    write_proxies(output, proxies)

    print("=" * 50)
    print(f"Generated proxies: {len(proxies)}")
    print(f"Output: {output}")
    print("=" * 50)

    if not proxies:
        raise RuntimeError("No valid proxy generated")


if __name__ == "__main__":
    main()
