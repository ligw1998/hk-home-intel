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

## 当前实现

当前系统已经实现：

- 官方源 SRPE 的 development / detail / document 导入链路
- 商业源 Centanet 与 Ricacorp 的 listing / price event 导入链路
- canonical 数据模型与本地 SQLite 开发数据库
- 地图页、房源流、单盘详情、单 listing 详情、watchlist、activity、system monitor、compare
- refresh plan、commercial search monitor、基础本地 scheduler

当前默认仍采用轻量本地开发模式，不依赖 Docker。数据库启动基线使用 SQLite；如果未来需要 PostgreSQL/PostGIS，仓库内保留了最小化的可选容器草案 `infra/docker/compose.optional.yml`。

## 当前状态

- `Phase 1` 已完成：可信官方数据底座
- `Phase 2` 已完成：本地工作台成型
- `Phase 3` 已完成到 compare baseline、双商业源和 monitor 管理层
- 下一步更适合进入 `Phase 4`：决策辅助、偏好收敛、评分和更明确的买房工作流
