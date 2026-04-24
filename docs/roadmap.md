# 开发路线图

## 1. 目标

路线图遵循“先打通核心决策闭环，再扩展覆盖面”的原则。系统的第一价值不是抓得多，而是能让你每天低成本筛选、比较、追踪和收敛候选盘。

## 2. 总体阶段

## 当前状态概览

当前实现已经明显超过“只有官方 baseline”的阶段，比较准确的位置是：

- `SRPE` 基线：已完成
- `map / shortlist / compare / system / launch-watch`：已可用
- `Centanet / Ricacorp` commercial discovery + monitor + batch refresh：已可用
- source identity merge：已采用 SRPE 优先、商业源补充覆盖的策略
- `launch-watch` 官方信号层：已具备
  - `landsd-pending`
  - `landsd-issued`
  - `landsd-all`
  - `srpe-recent-docs`
  - `srpe-active`

所以当前更接近：

- Phase 3 已经基本落地
- Phase 4 的部分工作台能力也已经开始出现，包括 compact UI、compare tray、System readiness / data-quality 卡片和 map data-gap 标签

## Phase 0: 设计与脚手架

目标：

- 固化架构与数据模型
- 初始化仓库结构
- 准备本地运行基础设施

交付物：

- 文档基线
- `docker-compose` 设计草案
- FastAPI / Next.js / worker 脚手架
- DB migration 初始化方案

完成标准：

- 本地一键启动空白系统
- SQLite 本地模式可用
- 基础健康检查接口可访问

## Phase 1: 最小可用版

目标：

- 打通“官方 source -> 规范化 -> 存储 -> 展示”的第一个可运行闭环
- 建立后续所有页面和数据源都要复用的 canonical 基线

范围：

- 接入 1 个高价值官方源
- 建 `development` / `listing` / `transaction` / `document` / `watchlist_item`
- development 列表与详情 API
- 官方文档元数据与文件落盘链路
- 三语字段存储与 API fallback
- development detail 页
- map/watchlist 的 baseline UI

完成标准：

- 至少一个官方 source 能端到端入库并在 Web 中浏览
- development / document / watchlist 形成可验证闭环
- 后续新 source 不需要重做主数据模型

当前实现说明：

- 当前代码实际上已经基本完成这一定义下的 Phase 1
- 已完成内容包括：
  1. SRPE live index / detail / document download
  2. development 列表、详情、map baseline、watchlist baseline
  3. 三语字段底座、快照与本地文档落盘
- 所以接下来不建议继续无限扩张 Phase 1，而应进入 Phase 2

## Phase 2: 工作台成型

目标：

- 把当前“技术闭环”升级成真正可日常使用的本地研究工作台

范围：

- 真实地图能力
- bbox / region / district 查询与更完整筛选
- geocoding 与坐标覆盖率提升
- watchlist 工作台页
- 基础 scheduler / refresh job / system monitor
- 首个可视化更新流或最近变化面板

完成标准：

- 地图页具备稳定的筛选、点选、详情联动能力
- watchlist 能支持阶段、备注、基础决策管理
- 能用定时任务完成日级更新，而不是全靠手动命令

当前实现说明：

- 这部分已完成
- `/system`、`/map`、`/watchlist`、`/shortlist`、`/compare` 都已进入日常可用范围

## Phase 3: 追踪与比较

目标：

- 把静态看盘变成动态追踪和横向比较

当前建议拆成 3 个子阶段：

1. `Phase 3A`
   - `price_event`
   - `GET /api/v1/listings/feed`
   - 第一商业源 adapter scaffold
   - 房源变化事件的规范化与入库
2. `Phase 3B`
   - 用户偏好过滤层与可保存 preset
   - 房源流页面增强
   - 单 listing / 单 development 变化时间线
   - 基础历史价格视图
3. `Phase 3C`
   - 商业源搜索入口管理 / 自动发现 baseline
   - 第一个比较页
   - 第二商业源
   - 跨源 comparable 与成交参考联动

范围：

- 第一个商业源
- `price_event`
- 房源流页面
- 户型/单位比较页
- 历史价格曲线
- 成交参考页
- 文档中心
- 第二个商业源

完成标准：

- 每天能快速看到新增、降价、售出、撤盘
- 可对多个相似户型并排比较
- 单盘支持查看关键文档和历史变化

当前实现说明：

- 这部分也已经基本落地
- 已有：
  - `price_event`
  - `/api/v1/listings/feed`
  - `Centanet`
  - `Ricacorp`
  - `commercial monitor discovery / batch refresh`
  - `launch-watch`

推荐顺序：

1. 先把 `price_event` 和 listing feed API 落成基础层
2. 再接入中原地产香港，优先验证“新增 / 降价 / 撤盘”事件
3. 进入 `Phase 3B` 时优先补“用户偏好过滤层”
   - 预算上限
   - 房型偏好（例如 `2房 > 3房 > 1房`）
   - 楼龄上限（例如优先 `<=10`，可扩到 `<=15`）
   - 目标 segment（新房 / 一手余货 / 二手）
4. 进入 `Phase 3C` 时，先把商业源搜索入口管理层落好
   - monitored search URLs
   - 单条 / 批量 refresh
   - 后续第二商业源复用同一入口管理层
5. 在此基础上再做 compare 页和第二商业源，不把扩源能力做成一堆孤立脚本
6. compare baseline 先以 development 级 side-by-side 为主
   - current band
   - observed range
   - bedroom mix
   - source mix
   - latest listing event
   - suggested comparables
7. commercial monitor 进入日常使用后，再补运行策略分层
   - search result limit
   - detail enrichment limit
   - 单条 detail 失败不拖垮整批 refresh

## Phase 4: 决策辅助

目标：

- 让系统开始主动帮助筛选和判断

范围：

- 评分与排序模型
- 可比盘匹配
- 通勤时间和生活配套标签
- 风险标签
- 看房笔记录入
- 经纪联系人管理
- 税费规则模块

完成标准：

- shortlist 可按解释性分数排序
- 每个候选项可展示“为什么值得看/为什么应谨慎”

## Phase 5: 智能增强

目标：

- 提升效率，但不让系统变成黑盒

范围：

- 文档自动摘要
- 新房源自动匹配 comparable
- 异常价格提示
- 智能去重辅助
- 重点项目变化摘要

完成标准：

- 每日打开系统即可看到高价值变化摘要
- 用户仍可回到原始证据链验证

## 3. 推荐任务拆解顺序

### 3.1 基础设施

1. 初始化 monorepo 目录
2. 先用 SQLite 跑通本地模式；后续需要时再切 PostgreSQL + PostGIS
3. 建 migration 机制
4. 建本地对象存储目录

### 3.2 领域模型

1. 建 core schema
2. 建枚举和状态机
3. 建 source snapshot 管道

### 3.3 首个 source

1. 选 SRPE
2. 实现 adapter
3. 建文档抓取和落库
4. 打通 development 详情页

### 3.4 地图能力

1. 建 geocode 流程
2. development 点位落库
3. Web 地图页和 bbox 查询

### 3.5 watchlist

1. 收藏 API
2. UI 操作栏
3. 备注和决策阶段

## 4. 里程碑建议

### Milestone A

内容：

- 能导入一个官方源
- 能打开 development 详情
- 能落官方文档到本地

### Milestone B

内容：

- 地图页、watchlist、scheduler 达到可日常使用
- 能完成低频日级刷新
- 能开始形成稳定 shortlist

备注：

- 这是新的 Phase 2 收尾标准，不再要求商业源已经接入

### Milestone C

内容：

- 能导入第一个商业源
- 能比较多个 development / unit type
- 能看成交参考、价格事件和文档

备注：

- 第一商业源默认按中原地产香港实现
- 第二商业源默认按利嘉阁实现

## 5. 质量门槛

每阶段都建议设定以下门槛：

- 数据可追溯：任一字段能回到来源和快照
- 变更可回放：关键对象历史不丢失
- 页面可用：地图和详情页在本地稳定工作
- 可维护：source adapter 与业务逻辑分层
- 可扩展：不因新增一个 source 而大改系统

## 6. 风险优先级

首期最需要提前控制的风险：

1. 地址与楼盘实体合并错误
2. 商业源结构不稳定
3. 模型过度复杂导致迟迟无法上线

对应策略：

1. development 先稳定，再逐步细化到 unit
2. 先接少量高价值 source，不追求覆盖面
3. 优先把首个闭环做完，而不是并行铺太多模块

## 7. 建议的近期执行清单

如果按当前项目状态继续往前推进，建议下一步按这个顺序：

1. 继续提高 `Ricacorp` commercial discovery 的候选质量与覆盖率
2. 继续收紧 `launch-watch` 的官方信号分层，优先保留更接近待抽签 / 近期开售的项目
3. 把 `launch-watch` 与 `map / shortlist / compare` 的联动解释继续补强
4. 收敛批量运行策略与 `/system` 可观测性，降低偶发超时的影响
5. 继续用 `/system` 的 `Commercial Canonical Official Artifacts` 指标复查历史 source identity 异常
6. 再评估是否需要引入更多官方供应背景层，例如 `Housing Bureau`
