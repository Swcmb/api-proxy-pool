# Proxy Pool Builder

基于 GitHub Actions + mubeng 自动构建高质量代理池。项目自动从多个公开代理源获取代理数据，完成代理标准化、去重、分片处理，并使用最新版本 mubeng 进行高并发存活检测。最终生成 `alive.txt`、`alive.json`、`metadata.json`、`clash.yaml`、`base64.txt`，适合 OpenCode2API 代理池、CC Switch fallback 节点、API Gateway fallback 节点、网络测试代理池、自动化代理服务数据源。

## Features
- 自动获取最新免费代理源
- 自动获取最新 mubeng release
- 支持 HTTP / HTTPS / SOCKS 代理
- hproxy CSV 自动转换标准代理格式
- 多来源代理自动合并、去重、分片
- GitHub Actions Matrix 并行测速
- mubeng 高并发存活检测
- 自动生成 JSON 数据与订阅文件
- GitHub Pages 发布
- 定时自动更新

## Architecture
```text
GitHub Actions
  -> Download Sources
  -> hproxy CSV / proxifly txt
  -> normalize.py
  -> all.txt
  -> split.py
  -> chunk-0 ... chunk-15
  -> mubeng Matrix Jobs
  -> alive files
  -> merge_json.py
  -> alive.txt / alive.json / metadata.json / clash.yaml / base64.txt
```

## Data Sources
### hproxy
来源：`https://github.com/hproxy-com/free-proxy-list`  
文件：`live.csv`  
格式：`ip,port,protocols,anonymity,country,city,latency_ms,uptime_pct,alive`  
示例：`159.203.61.169,8080,http,anonymous,CA,Toronto,43,93.4,true`  
转换：`159.203.61.169 / 8080 / http` -> `http://159.203.61.169:8080`

### proxifly
来源：`https://github.com/proxifly/free-proxy-list`  
文件：`proxies/all/data.txt`  
格式：
```text
http://1.2.3.4:8080
https://5.6.7.8:3128
socks5://9.9.9.9:1080
```
处理：直接读取并合并。

### mubeng
来源：`https://github.com/mubeng/mubeng`  
用途：代理连通性检测、存活代理筛选、高并发检测。  
每次运行：获取最新 release、下载对应版本、执行代理检测。

## Workflow
```text
Download Sources
  -> hproxy live.csv + proxifly data.txt
  -> normalize.py
  -> all.txt
  -> split.py
  -> chunk files
  -> mubeng
  -> alive files
  -> merge_json.py
  -> output files
```

## Generated Files
### alive.txt
纯代理列表：
```text
http://1.2.3.4:8080
https://5.6.7.8:3128
socks5://9.9.9.9:1080
```
适用于 curl、proxychains、OpenCode2API、CC Switch、代理测试工具。

### alive.json
```json
[
  {"proxy": "http://1.2.3.4:8080"},
  {"proxy": "https://5.6.7.8:3128"}
]
```
用途：API 服务读取、Web 前端展示、程序自动调用。

### metadata.json
```json
{
  "generated_at": "2026-10-14T00:00:00+00:00",
  "count": 8231,
  "sources": [
    "proxifly/free-proxy-list",
    "hproxy-com/free-proxy-list"
  ],
  "checker": "mubeng"
}
```
字段：`generated_at` 生成时间，`count` 可用代理数量，`sources` 代理来源，`checker` 检测工具。

### clash.yaml
```yaml
proxies:
  - name: proxy-0
    type: http
    server: 1.2.3.4
    port: 8080
```
适用于 Clash、Mihomo。

### base64.txt
Base64 订阅格式，适用于支持 Base64 代理订阅的软件。

## GitHub Pages Subscription
地址：`https://username.github.io/repository/`  
文件：`/alive.txt`、`/alive.json`、`/clash.yaml`、`/base64.txt`、`/metadata.json`

## Configuration
### Split Count
默认：`CHUNKS: 16`，即 `all.txt -> chunk-0.txt ... chunk-15.txt`。代理数量增加时可设为 `CHUNKS: 32`。

### Matrix Concurrency
默认：`CONCURRENCY: 8`，对应 `strategy.max-parallel: 8`，表示同时运行 8 个 GitHub Runner 执行 mubeng。

### mubeng Parameters
```bash
mubeng -f proxy.txt -o alive.txt -c 500 --timeout 10
```
参数：`-f` 输入代理列表，`-o` 输出存活代理，`-c` 并发连接数，`--timeout` 检测超时时间。

## GitHub Actions Runner
使用：`runs-on: ubuntu-latest`。原因：网络请求量大、检测时间长、需要稳定运行环境。  
不使用：`runs-on: ubuntu-slim`。原因：`ubuntu-slim` 最大运行时间 15 分钟，代理池构建通常超过该限制。

## Schedule
默认每 6 小时自动更新：`cron: "0 */6 * * *"`  
每天：`cron: "0 0 * * *"`  
每小时：`cron: "0 * * * *"`

## Manual Run
GitHub Repository -> Actions -> Proxy Pool Builder -> Run workflow

## Local Test
要求：`Python >= 3.10`  
安装：`pip install -r requirements.txt`  
运行：
```bash
python scripts/normalize.py live.csv proxifly.txt all.txt
python scripts/split.py all.txt 16
python scripts/merge_json.py alive output
```

## Directory Structure
```text
.
├── .github/workflows/proxy-check.yml
├── scripts/normalize.py
├── scripts/split.py
├── scripts/merge_json.py
├── requirements.txt
├── output/alive.txt
├── output/alive.json
├── output/metadata.json
├── output/clash.yaml
├── output/base64.txt
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
测试规模：`60000+ proxies`  
推荐配置：`CHUNKS: 16`、`CONCURRENCY: 8`  
mubeng：`connections: 500`、`timeout: 10s`  
典型运行时间：`30 - 90 minutes`

## Future Extension
代理质量评分、延迟排序、国家/地区过滤、匿名等级筛选、自动淘汰低质量节点、历史可用率统计、多区域 Runner 测试、动态 Proxy API Gateway。

## License
MIT
