# 系统架构

## 1. 背景与目标

这套系统不是“另一个香港房产 App”，而是面向单一高价值买家的本地置业研究终端。核心目标有四个：

1. 发现新盘、一手余货和楼龄较新的二手盘最新变化
2. 比较同区、同预算、同面积、同通勤条件下的横向可比项
3. 追踪楼盘、座、户型、单位、价单、成交和放盘状态的历史变化
4. 支持 shortlist 收敛，而不是展示海量 listing

## 2. 设计原则

- 本地优先：数据、图片、PDF、快照默认保存到本地
- 官方优先：官方或半官方源作为事实地基，商业站点用于补足实时性
- 结构化优先：先统一对象模型，再做页面、分析和评分
- 低频稳态：首轮全量，后续以天级别增量更新为主
- 可追溯：保留原始 HTML/JSON/PDF/图片及抓取时间、内容哈希、来源 URL
- 合规保守：商业站点低频、限速、带缓存，不做对外公开分发
- 策略可配置：税费、评分、刷新策略、源优先级通过配置管理

## 3. 范围边界

### 3.1 首期纳入

- 新盘与楼花项目
- 一手已开售但仍有未售单位的项目
- 楼龄不超过 10 年的二手住宅
- 官方文档、在售 listing、成交记录、图片、平面图、项目文档
- 用户手工录入的看房笔记、经纪信息、主观判断

### 3.2 首期不做

- 对外分享门户
- 高频近实时监控
- 自动下单或交易流程集成
- 全香港所有物业类别的覆盖
- 完整移动端原生 App

## 4. 总体模块拆分

系统拆为六个子系统。

### 4.1 数据采集层

职责：

- 拉取官方结构化数据、文档、商业 listing 页面和图片
- 做基础节流、重试、缓存、变更检测
- 保存原始快照

核心组件：

- `collector`：针对不同 source 的 adapter
- `fetcher`：统一 HTTP/浏览器抓取能力
- `snapshot store`：HTML/JSON/PDF/图片归档

### 4.2 规范化与实体合并层

职责：

- 地址标准化
- 中英文楼盘名、别名、期数、座数统一
- 字段标准化和单位换算
- 同源去重与跨源实体合并

核心组件：

- `normalizer`
- `entity resolver`
- `canonical mapper`

### 4.3 存储与索引层

职责：

- 管理结构化主数据
- 存储原始文档和图片
- 提供空间查询和全文搜索

当前默认组合：

- SQLite：本地结构化主库
- 本地文件系统：文档、图片、HTML/PDF 快照
- API 层聚合查询：当前阶段先不单独引入外部搜索引擎

后续扩量建议：

- PostgreSQL + PostGIS：更大规模、多终端或更重空间查询时再切换
- 对象存储：需要远程共享文件时再考虑 MinIO 或兼容 S3 的方案
- 全文搜索：先保持数据库内聚合，必要时再补 FTS/索引层

### 4.4 更新与调度层

职责：

- 定时任务
- 增量更新
- 优先级刷新
- 失败退避
- 指标监控

推荐机制：

- 官方源：每日或每周
- 商业源：每日低频分时轮询
- watchlist：提升单盘刷新频率
- 只有内容哈希变更时入新版本

### 4.5 分析与评分层

职责：

- 可比盘匹配
- 价格合理性评估
- 成交带统计
- 去化分析
- 通勤与生活配套打分
- 风险标签与决策辅助

### 4.6 本地 Web UI 层

职责：

- 地图与筛选入口
- 单盘深挖
- 户型与单位比较
- 成交参考
- 文档查看
- watchlist 工作流

## 5. 逻辑架构图

```text
                +----------------------+
                |    External Sources  |
                |----------------------|
                | official / geo /     |
                | commercial / manual  |
                +----------+-----------+
                           |
                           v
                +----------------------+
                |  Collector Adapters  |
                | Playwright / httpx   |
                +----------+-----------+
                           |
                 raw files | metadata
                           v
                +----------------------+
                | Snapshot Store       |
                | html/json/pdf/image  |
                +----------+-----------+
                           |
                           v
                +----------------------+
                | Normalizer / Resolver|
                | address/entity merge |
                +----------+-----------+
                           |
                           v
                +----------------------+
                | SQLite / local files |
                | canonical + raw      |
                +----------+-----------+
                           |
                           v
                +----------------------+
                | API Service          |
                | FastAPI              |
                +----------+-----------+
                           |
                           v
                +----------------------+
                | Web UI               |
                | Next.js + Leaflet    |
                +----------------------+
```

## 6. 当前目录结构与后续扩展

```text
hk-home-intel/
├─ apps/
│  ├─ api/
│  ├─ web/
│  └─ worker/
├─ packages/
│  ├─ domain/
│  ├─ connectors/
│  ├─ normalization/
│  ├─ analytics/
│  ├─ parsing/
│  └─ shared/
├─ data/
│  ├─ raw/
│  ├─ snapshots/
│  ├─ documents/
│  ├─ images/
│  └─ exports/
├─ infra/
│  ├─ docker/          # 预留，当前默认不依赖
│  ├─ migrations/
│  └─ scripts/
├─ configs/
│  ├─ sources.yaml
│  ├─ scheduler.yaml
│  └─ scoring.yaml
└─ docs/
```

## 7. 建议服务拆分

### 7.1 `apps/worker`

职责：

- 执行采集任务
- 执行解析与规范化
- 触发变更检测和派生分析

### 7.2 `apps/api`

职责：

- 向前端提供 REST API
- 暴露筛选、地图、详情、对比、成交、文档、watchlist 接口

### 7.3 `apps/web`

职责：

- 交互式地图和 tab 页
- 对比与决策界面
- 手工录入补充入口

当前实现补充：

- 地图层使用 `Leaflet + react-leaflet`
- 已有页面包括：
  - `/map`
  - `/listings`
  - `/compare`
  - `/shortlist`
  - `/launch-watch`
  - `/system`
- `/launch-watch` 已从平铺列表升级为按官方信号强度分组的观察工作台
- `/map` 的 `Selected` 面板会直接暴露 development coverage / data-gap

## 8. 核心数据流

```text
discover -> fetch -> snapshot -> parse -> normalize -> resolve entity
-> upsert canonical objects -> emit events -> refresh analytics -> serve UI
```

详细说明：

1. `discover`：发现项目、listing 或待抓取文档链接
2. `fetch`：拉取 HTML/API/PDF/图片，并记录抓取元数据
3. `snapshot`：写入原始文件与内容哈希
4. `parse`：从原始文件抽出结构化字段
5. `normalize`：做字段清洗、面积单位统一、地址标准化
6. `resolve entity`：把记录映射到 canonical development / unit / listing
7. `upsert`：写入主库并保留历史版本
8. `emit events`：生成价格变动、状态变动、文档更新等事件
9. `refresh analytics`：刷新统计指标、可比盘、评分等派生结果

## 9. Source Adapter 标准

每个信源都实现相同接口，避免把站点逻辑散落在系统各处。

```python
class SourceAdapter:
    source_name: str

    async def discover_developments(self): ...
    async def discover_listings(self): ...
    async def fetch_listing_detail(self, external_id: str): ...
    async def fetch_documents(self, entity_id: str): ...
    async def parse_snapshot(self, snapshot_path: str): ...
    async def normalize(self, payload: dict): ...
```

统一约束：

- 每个 adapter 有独立限速、User-Agent、失败退避和选择器版本
- 只返回 source 自己最确定的字段
- 不在 adapter 内做跨源实体合并
- 所有原始 payload 都必须可落盘回溯

## 10. 关键对象视角

系统主视图不以 listing 为中心，而以三层对象为中心：

- `development`：楼盘/屋苑
- `unit_type` / `unit_instance`：户型模板和具体单位
- `listing` / `transaction`：市场上的一次放盘或成交事实

原因：

- 同一单位会被多个经纪重复发布
- 一手余货与二手盘的“单套房源”定义并不一致
- 用户做判断时更常从楼盘、户型、单位出发

## 11. 地理与通勤能力

首版地理能力建议控制在可落地范围内：

- 保存 development 的点位
- 支持地图聚合、框选、半径搜索、距离最近地铁站
- 先做静态 POI 映射与距离估算
- 通勤时间先做基础版本，可后续接入更完整路线服务

## 12. 前端信息架构

建议的主要 tab：

1. 地图看盘
2. 房源流
3. 楼盘详情
4. 户型/单位比较
5. 成交参考
6. 文档中心
7. 收藏与决策清单
8. 系统监控

首页主布局建议为三栏：

- 左：筛选器
- 中：地图与聚合点位
- 右：候选集、对比栏、watchlist

## 13. 更新策略

### 13.1 全量与增量

- 首次：全量抓取目标区域与重点源
- 后续：以增量扫描为主
- watchlist：按项目提高更新优先级

### 13.2 触发条件

- 列表页新增/移除项
- 详情页内容哈希变化
- 文档目录出现新文件
- 价单/成交纪录册发布日期变化

### 13.3 版本化对象

以下对象默认需要版本化：

- listing 状态与叫价
- transaction 导入批次
- document 内容哈希
- development 别名与标准地址

## 14. 税费与政策规则模块

政策和税率属于时变规则，不能硬编码在业务逻辑里。建议单独做规则模块：

- 使用生效日期区间
- 支持按买家身份和价格区间匹配
- 支持未来税率调整
- 结果输出为明细项，而不是单个总额

建议数据结构：

```text
policy_rule
- id
- rule_type
- effective_from
- effective_to
- subject_scope
- condition_json
- formula_json
- source_ref
```

## 15. 监控与可运维性

系统监控页至少显示：

- 各 source 最近成功抓取时间
- 今日新增 listing 数
- 今日价格变更事件数
- 失败任务数
- 快照存储增长
- 解析失败率
- 去重命中率

## 16. 风险与控制

### 16.1 技术风险

- 商业站点页面结构频繁变化
- 不同源对面积、楼层、景观的定义不一致
- 同单位跨源匹配误判

### 16.2 合规风险

- 商业 listing 复用边界不明确
- 高频访问可能触发风控

### 16.3 控制策略

- 商业源低频限速
- 保留来源链接和抓取时间
- 本地个人研究使用，不做外部分发
- 优先使用官方或半官方开放数据

## 17. 首版落地建议

首版只求把“发现、比较、追踪”打通。

建议先做：

1. 2 个官方源 + 1 个商业源
2. `development` / `listing` / `transaction` / `document` 主表
3. 地址标准化和 development 合并
4. 地图页、详情页、watchlist
5. 每日更新和事件流

这样可以在控制复杂度的前提下尽快形成可用系统。
