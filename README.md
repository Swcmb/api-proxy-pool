# Proxy Pool Builder
基于 GitHub Actions + mubeng 的自动化代理池构建系统。从多个公开代理源自动采集代理数据，完成标准化、去重、分片，并调用最新版 mubeng 高并发存活检测，生成高质量可用代理池。结果支持 OpenCode2API 代理池、CC Switch fallback 节点、API Gateway 代理节点、网络测试代理池、自动化代理服务数据源。

## Features
- 自动获取最新免费代理源与 mubeng release
- 支持 HTTP / HTTPS / SOCKS 代理
- hproxy CSV 自动转换标准代理格式
- 多来源代理自动合并、去重、分片
- GitHub Actions Matrix 并行测速，mubeng 高并发存活检测
- 自动生成 JSON 数据与代理订阅文件，定时更新

## Data Sources
### hproxy
来源：https://github.com/hproxy-com/free-proxy-list
文件：`live.csv`
格式：
```csv
ip,port,protocols,anonymity,country,city,latency_ms,uptime_pct,alive
159.203.61.169,8080,http,anonymous,CA,Toronto,43,93.4,true
```
转换：`159.203.61.169,8080,http` → `http://159.203.61.169:8080`

### proxifly
来源：https://github.com/proxifly/free-proxy-list
文件：`proxies/all/data.txt`
格式：
```text
http://1.2.3.4:8080
https://5.6.7.8:3128
socks5://9.9.9.9:1080
```
处理：直接读取并合并。

### mubeng
测速工具：https://github.com/mubeng/mubeng
功能：TCP/HTTP 代理检测、高并发测速、存活代理筛选。
每次 GitHub Actions 运行：查询最新 release → 下载最新版本 → 执行代理检测。

## Workflow
```text
GitHub Actions → Download Sources
  ├─ hproxy CSV ─┐
  └─ proxifly txt ┘ → normalize.py → all.txt → split.py
  → chunk-0 ... chunk-15 → mubeng Matrix Jobs → alive files
  → merge_json.py → alive.txt / alive.json / metadata.json
```

## Generated Files
### alive.txt
纯代理列表：
```text
http://1.2.3.4:8080
https://5.6.7.8:3128
socks5://9.9.9.9:1080
```
用途：curl、proxychains、OpenCode2API、CC Switch、代理测试工具。

### alive.json
```json
[
  {"proxy": "http://1.2.3.4:8080"},
  {"proxy": "https://5.6.7.8:3128"}
]
```
用途：API 服务读取、Web 前端展示、自动化程序调用。

### metadata.json
```json
{
  "generated_at": "2026-10-14T00:00:00+00:00",
  "count": 8231,
  "sources": ["proxifly/free-proxy-list", "hproxy-com/free-proxy-list"],
  "checker": "mubeng"
}
```
| 字段 | 说明 |
|-|-|
| generated_at | 生成时间 |
| count | 可用代理数量 |
| sources | 代理来源 |
| checker | 检测工具 |

## Configuration
### Proxy Split
默认 `CHUNKS: 16`，即 `all.txt` 分片为 `chunk-0.txt` ... `chunk-15.txt`。代理数量增加时可设为 `CHUNKS: 32`。

### Matrix Concurrency
默认 `CONCURRENCY: 8`，对应 `strategy.max-parallel: 8`，即同时运行 8 个 GitHub Runner 执行 mubeng 检测。

### mubeng Parameters
```bash
mubeng -f proxy.txt -o alive.txt -c 500 --timeout 10
```
| 参数 | 作用 |
|-|-|
| `-f` | 输入代理列表 |
| `-o` | 输出存活代理 |
| `-c` | 并发连接数 |
| `--timeout` | 单代理检测超时 |

## GitHub Actions Runner
使用 `runs-on: ubuntu-latest`。代理检测包含大量网络请求、长时间任务、高并发任务，不使用 `ubuntu-slim`，因其最大运行时间 15 分钟，不适合大规模代理检测。

## Schedule
默认每 6 小时更新：
```yaml
schedule:
  - cron: "0 */6 * * *"
```
每天：`cron: "0 0 * * *"`；每小时：`cron: "0 * * * *"`。

## Manual Run
GitHub Repository → Actions → Proxy Pool Builder → Run workflow。

## Local Test
环境：Python >= 3.10。安装：`pip install -r requirements.txt`。
```bash
python scripts/normalize.py live.csv proxifly.txt all.txt
python scripts/split.py all.txt 16
python scripts/merge_json.py alive output
```

## Directory Structure
```text
.
├── .github/workflows/proxy-check.yml
├── scripts
│   ├── normalize.py
│   ├── split.py
│   └── merge_json.py
├── output
│   ├── alive.txt
│   ├── alive.json
│   └── metadata.json
└── README.md
```

## API Usage Example
```python
import json
with open("alive.json", encoding="utf-8") as f:
    proxies = json.load(f)
for proxy in proxies:
    print(proxy["proxy"])
```

## Performance
测试规模：`60000+ proxies`。推荐配置：`CHUNKS=16`、`CONCURRENCY=8`、`mubeng connections=500`。典型运行时间：`30 - 90 minutes`。

## Future Extension
计划支持：GitHub Pages 订阅地址、Clash 配置生成、Base64 订阅、Proxy API Endpoint、延迟排序、国家筛选、匿名等级筛选、自动淘汰低质量节点。

## License
MIT