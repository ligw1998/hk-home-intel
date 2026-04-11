# HK Home Intel

本仓库用于建设一套本地优先的香港住宅置业研究系统，目标是把分散在官方平台、开发商资料、一手销售平台和商业中介站点上的信息统一成可比较、可追踪、可决策的工作台。

当前阶段先落技术设计基线，后续开发以 `docs/` 为准。

## 文档索引

- [系统架构](docs/architecture.md)
- [数据模型](docs/data-model.md)
- [数据源目录](docs/source-catalog.md)
- [API 设计](docs/api-design.md)
- [开发路线图](docs/roadmap.md)
- [本地开发](docs/local-development.md)

## 产品目标

- 聚合香港新盘、一手余货、楼龄较新的二手住宅信息
- 支持地图看盘、户型对比、成交参考、文档归档、watchlist 决策
- 以日级更新为主，保留原始快照，支持历史变化追踪
- 优先服务单一买家的本地研究和判断，不做公开分发平台

## 首版技术方向

- Backend: FastAPI + SQLAlchemy
- DB: PostgreSQL + PostGIS
- Scheduler / Worker: APScheduler 或 Celery
- Collector: Playwright + httpx + BeautifulSoup/lxml
- Frontend: Next.js + TypeScript + MapLibre GL
- Storage: 本地文件系统，后续可切 MinIO

## 设计原则

- 本地优先，所有核心数据和文档可在本机完整保存
- 官方源优先，商业源用于补足实时性和图片等弱结构化信息
- 结构化优先，抓取只是入口，核心价值在规范化和实体合并
- 变更追踪优先，所有关键对象都要支持版本化和快照回溯
- 策略可配置，税费、评分、源优先级、刷新频率都不写死

## Phase 0 当前状态

已初始化：

- `apps/api` FastAPI 服务骨架
- `apps/worker` worker 占位命令
- `apps/web` Next.js 本地页面骨架
- `packages/shared` 共享配置与运行时工具
- `docs/local-development.md` 本地启动说明

Phase 0 默认不依赖 Docker。数据库启动基线使用 SQLite；如果未来需要 PostgreSQL/PostGIS，仓库内保留了最小化的可选容器草案 `infra/docker/compose.optional.yml`。
