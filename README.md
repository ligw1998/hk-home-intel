# HK Home Intel

本仓库用于建设一套本地优先的香港住宅置业研究系统，目标是把分散在官方平台、开发商资料、一手销售平台和商业中介站点上的信息统一成可比较、可追踪、可决策的工作台。

当前仓库已经具备可运行的本地研究工作台基线，后续设计与开发说明以 `docs/` 为准。

## 文档索引

- [系统架构](docs/architecture.md)
- [数据模型](docs/data-model.md)
- [数据源目录](docs/source-catalog.md)
- [API 设计](docs/api-design.md)
- [开发路线图](docs/roadmap.md)
- [本地开发](docs/local-development.md)
- [运行手册](docs/operations.md)
- [命令速查](docs/command-cheatsheet.md)

## 产品目标

- 聚合香港新盘、一手余货、楼龄较新的二手住宅信息
- 支持地图看盘、户型对比、成交参考、文档归档、watchlist 决策
- 以日级更新为主，保留原始快照，支持历史变化追踪
- 优先服务单一买家的本地研究和判断，不做公开分发平台

## 首版技术方向

- Backend: FastAPI + SQLAlchemy
- DB: SQLite（当前默认），后续可切 PostgreSQL + PostGIS
- Scheduler / Worker: 本地 worker + refresh plans
- Collector: httpx / curl fallback + BeautifulSoup/lxml
- Frontend: Next.js + TypeScript + Leaflet
- Storage: 本地文件系统，后续可切对象存储

## 设计原则

- 本地优先，所有核心数据和文档可在本机完整保存
- 官方源优先，商业源用于补足实时性和图片等弱结构化信息
- 结构化优先，抓取只是入口，核心价值在规范化和实体合并
- 变更追踪优先，所有关键对象都要支持版本化和快照回溯
- 策略可配置，税费、评分、源优先级、刷新频率都不写死

## 当前实现

当前系统已经实现：

- 官方源 SRPE 的 development / detail / document 导入链路
- 商业源 Centanet 与 Ricacorp 的 listing / price event 导入链路
- development 级 `source_coverage / coverage_status / data_gap_flags`
  - 可以直接看出一个盘当前是只有 `SRPE` baseline，还是已经有商业源与活跃 listing 覆盖
- `launch-watch` 观察池与官方信号层
  - `landsd-pending`
  - `landsd-issued`
  - `landsd-all`
  - `srpe-recent-docs`
  - `srpe-active`
- canonical 数据模型与本地 SQLite 开发数据库
- 地图页、房源流、单盘详情、单 listing 详情、watchlist、activity、system monitor、compare、launch-watch
- refresh plan、commercial search monitor、基础本地 scheduler

当前默认仍采用轻量本地开发模式，不依赖 Docker。数据库启动基线使用 SQLite；如果未来需要 PostgreSQL/PostGIS，仓库内保留了最小化的可选容器草案 `infra/docker/compose.optional.yml`。

## 当前状态

- `Phase 1` 已完成：可信官方数据底座
- `Phase 2` 已完成：本地工作台成型
- `Phase 3` 已完成到 compare baseline、双商业源和 monitor 管理层
- 下一步更适合进入 `Phase 4`：决策辅助、偏好收敛、评分和更明确的买房工作流

## Quickstart

默认工作目录：

```bash
cd /Users/ligw1998/Projects/hk-home-intel
```

### Fresh Clone

```bash
git clone <your-repo-url>
cd hk-home-intel
conda create -n py311 python=3.11 -y
conda run -n py311 python -m pip install --no-build-isolation -e ".[dev]"
npm install
cp .env.example .env
conda run -n py311 alembic upgrade head
```

启动：

```bash
conda run -n py311 hhi-api
npm run dev:web
```

默认地址：

- API: `http://127.0.0.1:8000`
- Web: `http://127.0.0.1:3000`

### First Data Load

```bash
conda run -n py311 hhi-worker import-srpe-index --lang en --limit 50 --offset 0
conda run -n py311 hhi-worker sync-launch-watch-config
conda run -n py311 hhi-worker sync-launch-watch-official --source landsd-all
conda run -n py311 hhi-worker sync-launch-watch-official --source srpe-recent-docs
conda run -n py311 hhi-worker discover-commercial-monitor-candidates --source centanet --limit 20 --validate --create-monitors
conda run -n py311 hhi-worker set-commercial-monitors-active --source centanet --auto-discovered
conda run -n py311 hhi-worker discover-commercial-monitor-candidates --source ricacorp --limit 20 --validate --create-monitors
conda run -n py311 hhi-worker set-commercial-monitors-active --source ricacorp --auto-discovered
conda run -n py311 hhi-worker run-commercial-search-monitors --source centanet --limit-override 20
conda run -n py311 hhi-worker run-commercial-search-monitors --source ricacorp --limit-override 20
```

如果还想把范围更宽的官方一手观察池也同步进来：

```bash
conda run -n py311 hhi-worker sync-launch-watch-official --source srpe-active
```

## 当前主要页面

- `/map`
- `/listings`
- `/compare`
- `/shortlist`
- `/launch-watch`
- `/system`

当前 UI 补充：

- `/launch-watch`
  - 默认按官方信号强度分组显示，先看更接近待抽签 / 近期开售的项目
- `/map`
  - 打开 `Show launch-watch` 后可同时查看观察池项目
  - 右侧 `Selected` 面板会直接展示 development coverage / data-gap 提示

## 进一步阅读

- 环境与本地运行：[`docs/local-development.md`](docs/local-development.md)
- 命令速记：[`docs/command-cheatsheet.md`](docs/command-cheatsheet.md)
- 运行策略：[`docs/operations.md`](docs/operations.md)
