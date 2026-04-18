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

如果你希望结果页导入后顺手补全每条 listing 的 detail 字段，但仍然不默认保存 raw HTML：

```bash
conda run -n py311 hhi-worker import-centanet-search --url 'https://hk.centanet.com/findproperty/list/buy/%E5%8C%AF%E7%92%BD_3-EESPWPPYPS' --limit 10 --with-details
```

这会在 search import 后继续抓 listing detail 页面，并把地址、更新日期、月供、楼龄、座向、标签、简介等字段补到本地 `listing`。只有你额外加 `--save-detail-snapshots` 时，才会为这些 detail 页保留原始 HTML 快照。

如果你确认某个搜索页是完整范围、不是手动截断结果，还可以显式启用页面级撤盘识别：

```bash
conda run -n py311 hhi-worker import-centanet-search --url 'https://hk.centanet.com/findproperty/list/buy/%E5%8C%AF%E7%92%BD_3-EESPWPPYPS' --detect-withdrawn
```

这会把该搜索页中已消失、但本地仍标记为 `active` 的 listing 改为 `withdrawn`，并写入 `price_event`。注意：它要求完整导入当前搜索页，因此不要与 `--limit` 同时使用。

按单条中原 listing URL 导入 detail 字段：

```bash
conda run -n py311 hhi-worker import-centanet-detail --url 'https://hk.centanet.com/findproperty/detail/...'
```

这条命令会解析单条商业源 listing 的 detail 页面，并把地址、更新日期、月供、楼龄、座向、标签、简介等字段补到已存在的 `listing` 记录里。默认不会保存 raw HTML。

如果你需要为某个重点 listing 留一份调试或取证级别的原始 HTML：

```bash
conda run -n py311 hhi-worker import-centanet-detail --url 'https://hk.centanet.com/findproperty/detail/...' --save-snapshot
```

这会额外保存一份受控的 `detail_page` snapshot，但它不是商业源的默认保留策略。

如果你已经导入过一批中原 search rows，后续想只给这些旧记录批量补 detail 字段：

```bash
conda run -n py311 hhi-worker backfill-centanet-details --limit 20
```

这条命令会扫描本地已有的 `centanet` listing，优先补那些仍缺少地址、更新日期、楼龄、座向、简介等 detail 字段的记录。默认不保存 raw HTML；如果你明确想保留重点盘的原始页，再加 `--save-snapshots`。

如果你已经进入 Phase 3C，想把中原搜索结果页 URL 当成一组“受监控入口”来维护，而不是每次手动填单个 URL：

```bash
conda run -n py311 hhi-worker run-commercial-search-monitor --monitor-id <monitor_id>
conda run -n py311 hhi-worker run-commercial-search-monitors --source centanet
```

第一条会运行单个已保存 monitor；第二条会批量运行某个 source 下的全部 active monitors。后续接入利嘉阁时，会复用同一层 monitor 管理，而不是为第二商业源重复做一套 URL 手工刷新逻辑。

`/system` 页里的 commercial monitor 现在还支持两层上限控制：

- `Default limit`：每次 search refresh 最多处理多少条结果
- `Detail limit`：当 `with_details = true` 时，最多补多少条 detail 页

推荐把 detail limit 设得比 search limit 更小。这样可以维持较好的 listing 覆盖，同时把最耗时的商业 detail enrichment 控制在重点样本范围内。

如果你想直接低频导入一页真实利嘉阁买盘结果，用于验证第二商业源链路：

```bash
conda run -n py311 hhi-worker import-ricacorp-search --url 'https://www.ricacorp.com/zh-hk/property/list/buy' --limit 5
```

当前 Ricacorp 先接的是搜索结果页 parser，能把 `development / listing / price_event` 写入本地；detail enrichment 不是这一轮的重点。

如果你想在当前阶段直接并排比较多个 development，可打开：

```text
http://localhost:3000/compare?ids=<development_id_1>,<development_id_2>
```

如果只传一个 development id，compare 页会自动拉同区/同 segment/相近价格带的候选 comparables，方便从单盘详情继续扩成并排比较。

前端当前也已经有 compare tray：

- 首页、地图、watchlist、development detail 都可以直接 `Add to compare`
- watchlist 页支持 `Add filtered to compare`
- compare tray 固定显示在页面右下角，可直接进入 `/compare`
- compare 页本身也支持对已选 development 直接 `Remove from compare`

当前 compare 的推荐策略会尽量避免噪音结果：

- 如果候选盘只是在 broad region 相同，但面积或价格带差异过大，系统会直接不显示
- 如果没有足够接近的 comparable，compare 页会显示说明文案，而不是硬塞明显不相关的候选

如果你想通过系统页以 plan 的方式低频刷新一个中原搜索页，当前也已经内置了：

- `/system` -> `centanet_probe`

它默认是手动 plan，不会自动跑；适合把一个重点屋苑或搜索条件作为商业源观察窗，而不是做大范围商业站抓取。

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

如果你想把已有 commercial development 的 `district / region / address_normalized` 统一规范一遍，并用已有坐标补 broad region：

```bash
conda run -n py311 hhi-worker backfill-development-geography
```

这条命令不访问外网，适合在 compare、map、watchlist 依赖地区字段前做一次本地清洗。

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
- Listing event feed: `http://127.0.0.1:3000/listings`
- Listing detail: `http://127.0.0.1:3000/listings/<listing_id>`
- Map view: `http://127.0.0.1:3000/map`
- System view: `http://127.0.0.1:3000/system`
- Watchlist view: `http://127.0.0.1:3000/watchlist`
- Development detail: `http://127.0.0.1:3000/developments/<development_id>`

`/system` 页面现在也支持直接从 UI 触发 refresh plan，并能显示 plan 是否 due、下一次运行时间、以及运行到点的自动计划。
`/system` 页面还新增了 `Commercial Search Monitors`，可在网页里直接创建、编辑、删除和运行受监控的中原搜索入口。
`/activity` 页面会汇总最近的 refresh jobs、source snapshots、watchlist 更新，并支持按 kind、source、development 过滤。

如果你准备逐步扩大真实 monitor 数量，也可以直接用配置文件同步：

```bash
conda run -n py311 hhi-worker sync-commercial-monitor-config --dry-run
conda run -n py311 hhi-worker sync-commercial-monitor-config
```

默认读取：

- `configs/commercial_monitors.toml`

如果你准备增加更多真实 monitor 或开始更高频的商业源刷新，建议先看：

- [运行手册](operations.md)

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
