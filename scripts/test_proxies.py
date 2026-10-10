import argparse
import concurrent.futures
import json
import os
import re
import time
from pathlib import Path

import requests

# 每个逻辑源可以有多个候选 URL（主地址 + 镜像/备用 API），任一成功即算该源成功。
SOURCE_GROUPS = (
    {
        "name": "proxifly-all",
        "urls": (
            "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt",
            "https://ghproxy.net/https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt",
            "https://gh-proxy.com/https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt",
        ),
    },
    {
        "name": "hproxy-elite",
        "urls": (
            "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/elite.txt",
        ),
    },
)

TEST_URL = "https://www.gstatic.com/generate_204"
TIMEOUT = 8
MAX_WORKERS = 200
FAST_LATENCY_MS = 1500

DOWNLOAD_TIMEOUT = 30
DOWNLOAD_RETRIES = 3
DOWNLOAD_BACKOFF = 1.5
MIN_PAYLOAD_BYTES = 64

OUTPUT_FILE = Path("valid.txt")
FAST_FILE = Path("fast.txt")
STATS_FILE = Path("stats.json")
CLASH_FILE = Path("clash.yaml")

# 允许 protocol:// 前缀可选；无前缀的行默认按 http 处理。
RAW_PROXY_PATTERN = re.compile(
    r"^(?:(?P<protocol>[a-zA-Z0-9]+)://)?"
    r"(?P<host>[A-Za-z0-9.\-_]+):(?P<port>\d+)$"
)

DEFAULT_PROTOCOL = "http"

# 允许保留的协议；socks4 / socks4a 不在此列。
ALLOWED_PROTOCOLS = {"http", "https", "socks5"}

# 明确要排除的协议（Clash / Clash Meta 不支持 socks4）。
EXCLUDED_PROTOCOLS = {"socks4", "socks4a"}

CLASH_TYPE = {
    "http": "http",
    "https": "http",   # https 代理在 Clash 里是 type: http + tls: true
    "socks5": "socks5",
}

DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/plain,text/*;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
}

GIST_API = "https://api.github.com/gists"


def create_direct_session() -> requests.Session:
    """Ignore machine-level HTTP(S)_PROXY / ALL_PROXY environment variables."""
    session = requests.Session()
    session.trust_env = False
    session.proxies.clear()
    return session


def parse_proxies(
    content: str, *, expand_bare: bool = False
) -> tuple[set[str], int]:
    """Parse supported proxy entries; optionally probe bare host:port as common protocols."""
    allowed: set[str] = set()
    excluded_count = 0

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = RAW_PROXY_PATTERN.fullmatch(line)
        if not match:
            continue

        raw_protocol = match.group("protocol")
        protocol = (raw_protocol or DEFAULT_PROTOCOL).lower()

        if protocol in EXCLUDED_PROTOCOLS:
            excluded_count += 1
            continue

        host = match.group("host")
        try:
            port = int(match.group("port"))
        except ValueError:
            continue
        if not 1 <= port <= 65535:
            continue

        protocols = (
            ("http", "https", "socks5")
            if expand_bare and raw_protocol is None
            else (protocol,)
        )
        allowed.update(
            f"{candidate}://{host}:{port}"
            for candidate in protocols
            if candidate in ALLOWED_PROTOCOLS
        )

    return allowed, excluded_count


def fetch_url(url: str, timeout: float) -> tuple[str | None, str | None]:
    """一次请求尝试。返回 (content, error)。允许下载源时使用系统/环境代理。"""
    try:
        with requests.Session() as session:
            session.headers.update(DOWNLOAD_HEADERS)
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            content = response.text

        size = len(content.encode("utf-8", errors="ignore"))
        if size < MIN_PAYLOAD_BYTES:
            return None, f"payload too small ({size} bytes)"
        return content, None
    except requests.RequestException as exc:
        return None, f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def download_group(group: dict) -> tuple[str, str | None, str | None, str | None]:
    """尝试组内所有镜像；整组失败后带退避重试。

    返回 (name, content, used_url, error)。
    """
    name = group["name"]
    urls = group["urls"]
    last_errors: list[str] = []

    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        for url in urls:
            content, err = fetch_url(url, DOWNLOAD_TIMEOUT)
            if content is not None:
                return name, content, url, None
            print(f"  [MIRROR FAIL] {name} attempt {attempt}: {url} -> {err}")
            last_errors.append(f"{url} -> {err}")
        if attempt < DOWNLOAD_RETRIES:
            time.sleep(DOWNLOAD_BACKOFF * attempt)

    tail = last_errors[-len(urls):]
    return name, None, None, " | ".join(tail)


def download_proxies() -> tuple[list[str], dict, dict, dict, int]:
    """Download ALL source groups in parallel, merge and dedupe.

    返回 (proxies, per_source, per_source_excluded, used_url, total_excluded)。
    """
    total_mirrors = sum(len(g["urls"]) for g in SOURCE_GROUPS)
    print(
        f"Downloading {len(SOURCE_GROUPS)} source groups "
        f"({total_mirrors} mirror URLs) in parallel "
        f"(retries={DOWNLOAD_RETRIES}, timeout={DOWNLOAD_TIMEOUT}s, "
        f"excluding socks4/socks4a) ..."
    )

    all_proxies: set[str] = set()
    per_source: dict[str, int] = {}
    per_source_excluded: dict[str, int] = {}
    used_url: dict[str, str] = {}
    errors: list[str] = []
    total_socks4_excluded = 0

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(SOURCE_GROUPS)
    ) as executor:
        futures = {
            executor.submit(download_group, g): g for g in SOURCE_GROUPS
        }
        for future in concurrent.futures.as_completed(futures):
            name, content, url_used, err = future.result()
            if content is None:
                print(f"[SOURCE FAIL] {name}: {err}")
                errors.append(f"{name}: {err}")
                continue

            proxies, socks4_count = parse_proxies(content, expand_bare=(name == "hproxy-elite"))
            if not proxies:
                message = (
                    f"download ok ({url_used}) but contained no supported proxy "
                    f"entries (excluded socks4/socks4a: {socks4_count})"
                )
                print(f"[SOURCE FAIL] {name}: {message}")
                errors.append(f"{name}: {message}")
                continue

            per_source[name] = len(proxies)
            per_source_excluded[name] = socks4_count
            used_url[name] = url_used
            total_socks4_excluded += socks4_count

            before = len(all_proxies)
            all_proxies |= proxies
            added = len(all_proxies) - before
            print(
                f"[SOURCE OK] {name}  via {url_used}  "
                f"(+{added}, source total={len(proxies)}, "
                f"excluded socks4/socks4a={socks4_count})"
            )

    if not all_proxies:
        details = "\n".join(f"  - {item}" for item in errors)
        raise SystemExit(
            "Could not download a proxy list from any source.\n"
            "Source downloads may use the computer's configured proxy; "
            "proxy-node tests still ignore local proxy settings.\n"
            f"{details}"
        )

    print(f"Merged unique proxies: {len(all_proxies)}")
    print(f"Total socks4/socks4a entries excluded: {total_socks4_excluded}")
    return (
        sorted(all_proxies),
        per_source,
        per_source_excluded,
        used_url,
        total_socks4_excluded,
    )


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


# ---------- Clash 完整配置生成 ----------

def to_clash_config(proxies: list[str], max_nodes: int = 200) -> str:
    """生成完整 Clash 配置，可直接作为订阅内容。

    包含 mixed-port、proxies、proxy-groups、rules 四部分。
    max_nodes 限制写入配置的节点数量，避免 YAML 过大。
    """
    lines = [
        "# Clash config auto-generated by api-proxy-pool",
        "# Generated at: " + time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "",
        "mixed-port: 7890",
        "allow-lan: false",
        "mode: rule",
        "log-level: warning",
        "external-controller: 127.0.0.1:9090",
        "",
        "proxies:",
    ]

    names: list[str] = []
    added = 0
    seen_names: set[str] = set()

    for p in proxies:
        if added >= max_nodes:
            break
        scheme, _, rest = p.partition("://")
        host, _, port = rest.rpartition(":")
        scheme = scheme.lower()
        if scheme in EXCLUDED_PROTOCOLS or scheme not in CLASH_TYPE:
            continue

        base_name = f"{scheme}-{host}-{port}"
        name = base_name
        suffix = 1
        while name in seen_names:
            suffix += 1
            name = f"{base_name}-{suffix}"
        seen_names.add(name)
        names.append(name)

        lines.append(f'  - name: "{name}"')
        lines.append(f"    type: {CLASH_TYPE[scheme]}")
        if scheme == "https":
            lines.append("    tls: true")
        lines.append(f"    server: {host}")
        lines.append(f"    port: {port}")
        added += 1

    if added == 0:
        return ""

    # proxy-groups
    lines += [
        "",
        "proxy-groups:",
        '  - name: "手动选择"',
        "    type: select",
        "    proxies:",
        '      - "自动选择"',
        "      - DIRECT",
        '  - name: "自动选择"',
        "    type: url-test",
        "    url: http://www.gstatic.com/generate_204",
        "    interval: 300",
        "    tolerance: 50",
        "    proxies:",
    ]
    for n in names:
        lines.append(f'      - "{n}"')

    # rules
    lines += [
        "",
        "rules:",
        "  - GEOIP,CN,DIRECT",
        '  - MATCH,手动选择',
        "",
    ]

    return "\n".join(lines)


# ---------- GitHub Gist 发布 ----------

def publish_to_gist(
    gist_id: str,
    token: str,
    content: str,
    filename: str = "clash.yaml",
) -> str:
    """创建或更新 GitHub Gist，返回 Gist ID。

    - gist_id 为空时创建新 Gist。
    - gist_id 非空时更新已有 Gist。
    - 返回实际使用的 Gist ID（新建时为新 ID）。
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }

    payload = {
        "description": "Auto-generated Clash proxy subscription",
        "public": False,
        "files": {
            filename: {"content": content},
        },
    }

    if gist_id:
        url = f"{GIST_API}/{gist_id}"
        resp = requests.patch(url, headers=headers, json=payload, timeout=30)
    else:
        url = GIST_API
        resp = requests.post(url, headers=headers, json=payload, timeout=30)

    if resp.status_code not in (200, 201):
        raise SystemExit(
            f"Gist publish failed: HTTP {resp.status_code}\n{resp.text[:500]}"
        )

    data = resp.json()
    actual_id = data["id"]
    html_url = data["html_url"]
    raw_url = data["files"][filename]["raw_url"]

    print(f"Gist published: {html_url}")
    print(f"Gist ID: {actual_id}")
    print(f"Raw subscription URL: {raw_url}")
    return actual_id


# ---------- opencode2api 配置更新（保留原有功能） ----------

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
        description=(
            "Test public proxies, generate a full Clash subscription config, "
            "and optionally publish it to GitHub Gist."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="local opencode2api config.json path; omit when running in CI",
    )
    parser.add_argument(
        "--gist-id",
        default=os.environ.get("GIST_ID", ""),
        help="existing Gist ID to update; omit to create a new Gist "
             "(env: GIST_ID)",
    )
    parser.add_argument(
        "--gist-token",
        default=os.environ.get("GIST_TOKEN", ""),
        help="GitHub personal access token with 'gist' scope "
             "(env: GIST_TOKEN)",
    )
    parser.add_argument(
        "--max-nodes",
        type=int,
        default=200,
        help="max nodes to write into the Clash config (default: 200)",
    )
    parser.add_argument(
        "--no-clash",
        action="store_true",
        help="do not write clash.yaml",
    )
    args = parser.parse_args()

    (
        proxies,
        per_source,
        per_source_excluded,
        used_url,
        total_socks4_excluded,
    ) = download_proxies()

    print("Local environment proxies: DISABLED")
    print(f"Source groups used ({len(per_source)}/{len(SOURCE_GROUPS)}):")
    for name, count in per_source.items():
        print(f"  - {name}: {count} entries  via {used_url.get(name, '?')}")
    print("Protocols tested: http / https / socks5 (socks4/socks4a excluded)")
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
        "source_groups": [g["name"] for g in SOURCE_GROUPS],
        "mirrors_per_group": {g["name"]: len(g["urls"]) for g in SOURCE_GROUPS},
        "per_source_counts": per_source,
        "per_source_excluded_socks4": per_source_excluded,
        "used_url": used_url,
        "source_count": len(per_source),
        "excluded_protocols": sorted(EXCLUDED_PROTOCOLS),
        "total_excluded_socks4": total_socks4_excluded,
        "download_retries": DOWNLOAD_RETRIES,
        "download_timeout": DOWNLOAD_TIMEOUT,
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

    # ---- Clash 完整配置生成 ----
    clash_text = ""
    if not args.no_clash:
        source_pool = [p for p, _ in fast] or [p for p, _ in valid]
        clash_text = to_clash_config(source_pool, max_nodes=args.max_nodes)
        if clash_text:
            CLASH_FILE.write_text(clash_text, encoding="utf-8")
            node_count = clash_text.count("  - name:")
            print(f"Wrote Clash config: {CLASH_FILE} ({node_count} nodes)")
        else:
            print("No Clash-compatible proxies to export.")

    # ---- GitHub Gist 发布 ----
    if clash_text and args.gist_token:
        new_gist_id = publish_to_gist(
            gist_id=args.gist_id,
            token=args.gist_token,
            content=clash_text,
            filename="clash.yaml",
        )
        if not args.gist_id:
            print(
                f"\n首次创建 Gist 完成。请把 Gist ID 添加到 GitHub Secrets "
                f"的 GIST_ID 中，下次将自动更新：{new_gist_id}"
            )
    elif clash_text:
        print(
            "Gist not published. Set GIST_TOKEN (and optionally GIST_ID) "
            "to enable auto-publishing."
        )

    if args.config:
        update_opencode_config(
            args.config,
            [proxy for proxy, _ in fast],
        )
    else:
        print(
            'config.json not modified. Use --config "PATH" to update it.'
        )


if __name__ == "__main__":
    main()