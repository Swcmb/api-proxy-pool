import sys
import json
import base64
from pathlib import Path
from datetime import datetime, timezone

source = Path(sys.argv[1])
output = Path(sys.argv[2])

output.mkdir(parents=True, exist_ok=True)

alive = set()

for file in source.rglob("*.txt"):
    for line in file.read_text(encoding="utf-8").splitlines():
        proxy = line.strip()
        if proxy:
            alive.add(proxy)

alive = sorted(alive)

# alive.txt
(output / "alive.txt").write_text("\n".join(alive), encoding="utf-8")

# alive.json
with open(output / "alive.json", "w", encoding="utf-8") as f:
    json.dump([{"proxy": p} for p in alive], f, indent=2)

# metadata.json
metadata = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "count": len(alive),
    "sources": [
        "hproxy-com/free-proxy-list",
        "proxifly/free-proxy-list",
    ],
    "checker": "mubeng",
}

with open(output / "metadata.json", "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2)

# base64.txt
encoded = base64.b64encode("\n".join(alive).encode()).decode()
(output / "base64.txt").write_text(encoded, encoding="utf-8")

# clash.yaml
with open(output / "clash.yaml", "w", encoding="utf-8") as f:
    f.write("proxies:\n")
    for i, p in enumerate(alive):
        addr = p.replace("http://", "").replace("https://", "")
        host, port = addr.rsplit(":", 1)
        f.write(
            f"- name: proxy-{i}\n"
            f"  type: http\n"
            f"  server: {host}\n"
            f"  port: {port}\n"
        )

print(metadata)