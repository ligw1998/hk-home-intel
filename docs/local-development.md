# 本地开发

## 1. 当前定位

Phase 0 默认采用轻量本地开发模式，不依赖 Docker。

- Python: `conda` 环境 `py311`
- Web: 本地 Node.js
- Database: 默认 SQLite
- Docker: 可选，仅在后续需要 PostgreSQL/PostGIS 时引入

## 2. Python 依赖安装

在仓库根目录执行：

```bash
conda run -n py311 python -m pip install --no-build-isolation -e ".[dev]"
```

## 3. Web 依赖安装

```bash
npm install
```

## 4. 环境变量

复制环境模板：

```bash
cp .env.example .env
```

如果需要切到 PostgreSQL，可修改：

```bash
HHI_DATABASE_URL=postgresql+psycopg://user:password@127.0.0.1:5432/hk_home_intel
```

如果前端运行在 `localhost:3000` 或 `127.0.0.1:3000`，默认 CORS 已允许这两个来源。若你后续改了前端地址，可同步修改：

```bash
HHI_CORS_ALLOW_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
```

默认情况下，采集请求会继承 shell 里的 `http_proxy` / `https_proxy`。如果你希望让系统忽略环境代理、直接出网，可设置：

```bash
HHI_HTTP_TRUST_ENV=false
```

## 5. 启动 API

先应用 migration：

```bash
conda run -n py311 alembic upgrade head
```

然后启动 API：

```bash
conda run -n py311 hhi-api
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/v1/health
```

空数据库下，development 列表接口会返回空集合：

```bash
curl http://127.0.0.1:8000/api/v1/developments
```

导入示例 SRPE 数据：

```bash
conda run -n py311 hhi-worker import-srpe-sample
```

导入示例中原二手 listing 数据：

```bash
conda run -n py311 hhi-worker import-centanet-sample
```

按中原结果页 URL 低频导入真实二手 listing：

```bash
conda run -n py311 hhi-worker import-centanet-search --url 'https://hk.centanet.com/findproperty/list/buy/%E5%8C%AF%E7%92%BD_3-EESPWPPYPS' --limit 20
```

这条命令会抓一页中原搜索结果，解析 listing card，并把结果写入 `development / listing / price_event`。当前它适合作为 Phase 3A 的低频入口验证，不适合高频批量抓取。

导入真实 SRPE 官方 index 数据：

```bash
conda run -n py311 hhi-worker import-srpe-index --lang en --limit 20
```

如果你想先低量验证 live ingest，可把 `--limit` 调小到 `5` 或 `10`。当前这条命令只会访问官方 SRPE 接口，不会做高频抓取。

如果你希望同时补抓单盘详情里的官方文档元数据，可加上：

```bash
conda run -n py311 hhi-worker import-srpe-index --lang en --limit 5 --with-details
```

这会额外访问官方单盘详情接口，并导入 `brochure / price list / sales arrangement / transaction record` 文档元数据，但仍不会做高频抓取。

如果你要按 Phase 2 的方式运行一次带任务记录的 SRPE refresh：

```bash
conda run -n py311 hhi-worker run-srpe-refresh --lang en --limit 5
```

这条命令会写入 `refresh_job_run`，供系统监控页查看最近任务结果。

如果你想按配置化 refresh plan 执行：

```bash
conda run -n py311 hhi-worker run-refresh-plan --plan daily_local
conda run -n py311 hhi-worker run-refresh-plan --plan watchlist_probe
conda run -n py311 hhi-worker run-due-refresh-plans
```

计划配置来自 `configs/scheduler.toml`，system 页也会显示这些计划及其任务参数。
当前 `daily_local` 已加入简单轮转策略：每次成功运行后，会把 SRPE index 的抓取窗口按 `rotation_step` 向后推进，避免长期只刷新同一批最前面的 development。
如果你不想直接改 `configs/scheduler.toml`，现在也可以在 `/system` 页面里对 plan 做本地 override，覆盖：

- `auto_run`
- `interval_minutes`
- task `limit`
- task `with_details`
- task `rotation_mode`
- task `rotation_step`

这些 override 会保存在本地数据库里，不会覆盖默认配置文件；你也可以在 UI 中直接 reset 回文件默认值。

如果你想用最小本地 scheduler 轮询并自动执行到点的 plan：

```bash
conda run -n py311 hhi-worker start-local-scheduler --poll-seconds 60 --run-on-start
```

当前默认只有 `daily_local` 会参与自动调度；`watchlist_probe` 仍然是手动验证用计划。

如果你想补齐已有 development 的推断坐标：

```bash
conda run -n py311 hhi-worker backfill-development-coordinates
```

这会对当前库里缺失 `lat/lng` 的 development 做一次基于地址和 district 的回填。

如果你要把某个 SRPE 楼盘的官方 PDF 真正下载到本地文件系统：

```bash
conda run -n py311 hhi-worker download-srpe-documents --source-external-id 11365
```

下载后的文件会落到 `data/documents/srpe/<development_external_id>/`，并回写到 `document.file_path / mime_type / content_hash`。
这条命令已经改成逐份文档提交，若中途中断，可直接重跑续下去。

导入后再访问：

```bash
curl http://127.0.0.1:8000/api/v1/developments
```

按语言查看 development 显示名：

```bash
curl "http://127.0.0.1:8000/api/v1/developments?lang=zh-Hant"
curl "http://127.0.0.1:8000/api/v1/developments?lang=zh-Hans"
curl "http://127.0.0.1:8000/api/v1/developments?lang=en"
```

抓取 SRPE 首页快照：

```bash
conda run -n py311 hhi-worker fetch-srpe-homepage
```

如果你只想本地验证抓取流程，不走外网：

```bash
conda run -n py311 hhi-worker fetch-srpe-homepage --use-fixture
conda run -n py311 hhi-worker discover-srpe-entrypoints --use-fixture
```

## 6. 启动 worker

```bash
conda run -n py311 hhi-worker
```

## 7. 启动 Web

```bash
npm run dev:web
```

默认地址：

- Web: `http://127.0.0.1:3000`
- API: `http://127.0.0.1:8000`
- Activity view: `http://127.0.0.1:3000/activity`
- Map view: `http://127.0.0.1:3000/map`
- System view: `http://127.0.0.1:3000/system`
- Watchlist view: `http://127.0.0.1:3000/watchlist`
- Development detail: `http://127.0.0.1:3000/developments/<development_id>`

`/system` 页面现在也支持直接从 UI 触发 refresh plan，并能显示 plan 是否 due、下一次运行时间、以及运行到点的自动计划。
`/activity` 页面会汇总最近的 refresh jobs、source snapshots、watchlist 更新，并支持按 kind、source、development 过滤。

## 8. 当前 Phase 0 能力

- FastAPI 服务骨架
- 基础健康检查
- worker 占位命令
- Next.js 本地页面骨架
- 运行目录自动初始化
- Alembic 迁移脚手架

## 9. 当前 Phase 1 基线

- canonical domain models
- 初始 migration 与核心表
- `/api/v1/developments` 读取接口
- `/api/v1/developments/{id}` 聚合详情接口
- `/api/v1/watchlist` 最小持久化接口
- `/api/v1/system/overview` 与 `/api/v1/system/refresh-jobs`
- `/api/v1/system/scheduler-plans`
- SRPE adapter scaffold
- SRPE sample import workflow
- SRPE official index live import workflow
- SRPE selected development detail live import workflow
- SRPE official document download workflow
- 三语字段存储基线与 API fallback 显示
- SRPE homepage fetch/discovery baseline
- SRPE official service endpoint reverse engineering baseline
- address normalization 与 district centroid baseline
- 本地 development map 页
- development detail 页中的 watchlist 操作
- watchlist workspace 页
- system monitor 页与 refresh job run 记录
- 配置化 refresh plan 与 worker 执行入口
- recent activity feed 页

## 10. 后续计划

- 当前建议将现状视为“Phase 1 基线已完成”
- 当前处于新的 Phase 2：地图工作台、scheduler、watchlist 工作流、activity feed
- 建议以 `/activity` 作为每日巡检入口，必要时再进入 `/map`、`/watchlist`、`/system`
- 商业源与比较页顺延到新的 Phase 3
