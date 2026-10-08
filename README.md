# API Proxy Pool

Free public proxy pool for API.

Source:
- ProxyScrape `all/data.txt`

Workflow:
- GitHub Actions runs every 30 minutes or manually.
- Tests HTTP / HTTPS / ~~SOCKS4~~ / SOCKS5 proxies against `https://www.gstatic.com/generate_204`.
- `valid.txt` contains all proxies that successfully pass the test, sorted by latency.
- `fast.txt` contains valid proxies below 1500 ms.
- `stats.json` records the latest test statistics.

## Use with API

Point API's proxy file at:

```text
https://raw.githubusercontent.com/Swcmb/api-proxy-pool/main/valid.txt
```

Or download `valid.txt` locally.

## Important

These are public proxies. Treat them as untrusted infrastructure and do not send secrets or sensitive traffic through them.
