# Proxy Pool Builder
基于 GitHub Actions + mubeng 自动构建高质量代理池。自动从多个免费代理源获取代理，标准化、去重、分片，并使用最新版本 mubeng 进行存活检测，最终生成 `alive.txt`、`alive.json`、`metadata.json`。适合作为 OpenCode2API 代理池、CC Switch 代理池、API Gateway fallback 节点、网络测试代理池、自动化代理服务数据源。

## Features
- 自动获取最新代理源
- 自动获取最新 mubeng
- 支持 HTTP / HTTPS / SOCKS 代理
- CSV 自动转换标准代理格式
- 自动去重
- 自动分片并行测速
- GitHub Actions Matrix 并发
- 自动生成 JSON 数据
- 定时更新

## Data Sources
### hproxy
来源：`https://github.com/hproxy-com/free-proxy-list`
格式：
```csv
ip,port,protocols,anonymity,country,city,latency_ms,uptime_pct,alive
159.203.61.169,8080,http,anonymous,CA,Toronto,43,93.4,true
```
转换：`http://159.203.61.169:8080`

### proxifly
来源：`https://github.com/proxifly/free-proxy-list`
文件：`proxies/all/data.txt`，直接读取代理地址。

### mubeng
测速工具：`https://github.com/mubeng/mubeng`，每次运行自动获取最新 release。

## Workflow
```text
GitHub Actions -> Download Sources -> hproxy CSV / proxifly txt -> normalize.py -> all.txt -> split.py -> chunk-0.txt ... chunk-15.txt -> mubeng -> alive files -> merge_json.py -> alive.txt / alive.json / metadata.json
```

## Generated Files
### alive.txt
纯代理列表：
```text
http://1.2.3.4:8080
https://5.6.7.8:3128
socks5://9.9.9.9:1080
```
适合 curl、proxychains、OpenCode2API、CC Switch。

### alive.json
```json
[
  {"proxy": "http://1.2.3.4:8080"},
  {"proxy": "https://5.6.7.8:3128"}
]
```
适合 API 服务、Web 前端、程序读取。

### metadata.json
```json
{
  "generated_at": "2026-10-14T00:00:00+00:00",
  "count": 8231,
  "sources": ["proxifly/free-proxy-list", "hproxy-com/free-proxy-list"],
  "checker": "mubeng"
}
```

## Configuration
### 分片数量
默认 `CHUNKS: 16`，表示 `all.txt -> chunk-0.txt ... chunk-15.txt`。代理多时改为 `CHUNKS: 32`。

### 并发数量
默认 `CONCURRENCY: 8`，控制同时运行的 mubeng Job，例如 `max-parallel: 8` 表示 8 个 GitHub Runner 同时测速。

### mubeng 参数
```bash
mubeng -f proxy.txt -o alive.txt -c 500 --timeout 10
```
| 参数 | 作用 |
| --- | --- |
| `-f` | 输入代理列表 |
| `-o` | 输出存活代理 |
| `-c` | 并发连接数 |
| `--timeout` | 单代理超时 |

## GitHub Actions Runner
使用 `runs-on: ubuntu-latest`。`ubuntu-latest` 用于长任务、编译、测速；`ubuntu-slim` 用于简单任务。本项目代理数量大、网络请求多、需要 mubeng 长时间运行，因此不能用 `ubuntu-slim`，它最大 15 分钟。

## Schedule
默认：
```yaml
schedule:
  - cron: "0 */6 * * *"
```
每 6 小时更新一次。每天：`cron: "0 0 * * *"`；每小时：`cron: "0 * * * *"`。

## Manual Run
GitHub：`Actions -> Proxy Pool Builder -> Run workflow`。

## Local Test
需要 `python >=3.10`。
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
with open("alive.json") as f:
    proxies = json.load(f)
for proxy in proxies:
    print(proxy["proxy"])
```

## Performance
代理 60000+，分片 16，并发 8，mubeng 500 connections，典型运行 30-90 minutes。

## License
MIT