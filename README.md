# API Proxy Pool

Automatically collect, test, and publish public proxy nodes for API clients and Clash-compatible clients.

## Sources

Both sources are merged and deduplicated before testing:

- [Proxifly — all proxy protocols](https://github.com/proxifly/free-proxy-list/blob/main/proxies/all/data.txt), with download mirrors as fallbacks.
- [HProxy — elite proxy list](https://github.com/hproxy-com/free-proxy-list/blob/main/elite.txt). Bare `IP:port` entries are tested as HTTP, HTTPS, and SOCKS5.

Only HTTP, HTTPS, and SOCKS5 nodes are kept. SOCKS4/SOCKS4a entries are excluded.

## Generated files

| File | Purpose |
| --- | --- |
| [`valid.txt`](https://raw.githubusercontent.com/Swcmb/api-proxy-pool/main/valid.txt) | All nodes that pass the connectivity test, sorted by latency |
| [`fast.txt`](https://raw.githubusercontent.com/Swcmb/api-proxy-pool/main/fast.txt) | Valid nodes with latency below 1500 ms |
| [`clash.yaml`](https://raw.githubusercontent.com/Swcmb/api-proxy-pool/main/clash.yaml) | Generated Clash-compatible configuration |
| [`stats.json`](https://raw.githubusercontent.com/Swcmb/api-proxy-pool/main/stats.json) | Source and test statistics |

GitHub Actions runs the test workflow every 30 minutes and also supports manual runs. It downloads source lists with the configured mirrors, tests each node through that node itself, and commits changed output files.

## Use with an API client

Set the client's proxy-list URL to:

```text
https://raw.githubusercontent.com/Swcmb/api-proxy-pool/main/valid.txt
```

For a smaller, lower-latency list, use:

```text
https://raw.githubusercontent.com/Swcmb/api-proxy-pool/main/fast.txt
```

## Run locally

Requires Python 3.10+.

```bash
python -m pip install requests PySocks
python -m unittest discover -s tests -v
python scripts/test_proxies.py
```

Optional: update a local `opencode2api` `config.json` using the tested fast nodes:

```bash
python scripts/test_proxies.py --config /path/to/config.json
```

## Publish the Clash subscription to Gist

Configure the repository Actions secrets `GIST_TOKEN` and `GIST_ID`. The token needs permission to update Gists. The separate Gist workflow publishes the latest committed `clash.yaml` every six hours without re-running the full proxy scan.

## Security

These are public, untrusted proxy servers. Operators may observe or modify traffic. Do not send credentials, API keys, or sensitive data through public proxies.
