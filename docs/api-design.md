# API 设计

## 1. 目标

API 主要服务本地 Web UI，也为后续 worker、脚本和分析模块提供统一访问层。首版优先 REST，复杂筛选和联查先通过组合查询解决，不急于引入 GraphQL。

## 2. 设计原则

- 资源清晰，按楼盘、单位、listing、成交、文档、watchlist 分组
- 查询显式，筛选条件尽量可枚举和可缓存
- 读写分离，采集写入主要由内部 worker 负责
- 响应中保留来源和可信度，避免前端把派生值当原始事实

## 3. 认证与权限

首版默认本地单用户使用，可先采用以下简化方式：

- 本地运行，无公开暴露
- 写接口仅本地 UI 和内部任务调用
- 后续若需要多终端访问，再补 session 或 token 认证

## 4. 当前已实现 API 分组

当前路由模块位于：

- `activity`
- `commercial_search_monitors`
- `compare`
- `developments`
- `health`
- `launch_watch`
- `listings`
- `policies`
- `search_presets`
- `shortlist`
- `system`
- `watchlist`

下面按“当前已实现基线 + 后续演进方向”来描述，而不是把未来所有接口都视作已上线。

### 4.1 Developments

#### `GET /api/v1/developments`

地图和列表入口。

支持筛选：

- `district`
- `region`
- `listing_segment`
- `listing_segments`
- `has_coordinates`
- `q`
- `min_budget_hkd`
- `max_budget_hkd`
- `bedroom_values`
- `max_age_years`
- `min_saleable_area_sqft`
- `max_saleable_area_sqft`
- `source`
- `lang`
- `limit`
- `offset`

返回：

- 基础摘要
- 地图点位
- 当前价格带
- active listing 数
- 最近成交摘要
- watchlist 状态
- `source_coverage`
  - 每个 source 的 development / listing / document / transaction 覆盖情况
  - `latest_listing_event_at`
- `coverage_status`
  - `baseline_only / partial / rich`
- `coverage_notes`
  - 当前最值得注意的覆盖提示
- `data_gap_flags`
  - 当前仍缺哪类关键数据

#### `GET /api/v1/developments/{id}`

楼盘详情摘要。

返回：

- 基本信息
- 地图与区域信息
- 开发商、入伙年份、标签
- 当前统计
- 最新文档列表
- 最近成交摘要
- 可比盘摘要

#### `GET /api/v1/developments/{id}/listings`

返回该楼盘当前或历史 listing。

参数：

- `status`
- `listing_type`
- `unit_type_id`
- `sort`

#### `GET /api/v1/developments/{id}/transactions`

返回该楼盘成交记录。

参数：

- `months`
- `transaction_type`
- `group_by`

#### `GET /api/v1/developments/{id}/documents`

返回楼盘文档目录。

参数：

- `doc_type`

#### `GET /api/v1/developments/{id}/comparables`

返回可比盘结果及解释。

说明：

- 以上 detail 子路由仍有一部分是目标设计，不代表全部都已经开放
- 当前前端主要消费的是：
  - `GET /api/v1/developments`
  - `GET /api/v1/developments/{id}`
  - `GET /api/v1/developments/{id}/comparables`

### 4.2 Listings / Activity

#### `GET /api/v1/activity`

返回近期跨 development 的市场变化流。

#### `GET /api/v1/listings/feed`

房源流页面使用。

支持筛选：

- `event_type`
- `date_from`
- `date_to`
- `district`
- `listing_type`

返回：

- 新上架
- 降价
- 状态变化
- 新文档/新图片提示

当前实现基线：

- 已落 `/api/v1/listings/feed`
- 当前基于 `price_event` 表返回事件
- 后续商业源接入时，先写入 `price_event`，再由 feed 页面消费

#### `GET /api/v1/listings`

返回 listing 列表，供 `/listings` 与 development detail 视图复用。

#### `GET /api/v1/listings/{id}`

返回单条 listing 详情和历史。

#### `GET /api/v1/listings/{id}/events`

返回价格与状态变动时间线。

当前实现基线：

- 已落 `/api/v1/listings/{id}/events`
- 当前返回该 listing 的事件时间线

#### `GET /api/v1/listings/{id}/price-history`

返回该 listing 的基础价格历史视图。

当前实现基线：

- 已落 `/api/v1/listings/{id}/price-history`
- 当前基于 `price_event.new_price_hkd` 生成价格点
- 返回：
  - 当前价格
  - 上一个价格
  - 历史最低/最高价格
  - 价格点列表

#### `GET /api/v1/search-presets`

返回指定 scope 的已保存筛选 preset。

当前实现基线：

- 已落 `search-presets` CRUD
- 当前主要用于 `/map` 的偏好筛选 preset 保存与复用

### 4.3 Compare / Shortlist / Watchlist

#### `GET /api/v1/compare`

返回当前 compare 工作台需要的 development side-by-side 数据。

#### `GET /api/v1/shortlist`

返回 shortlist 候选与排序解释。

#### `GET /api/v1/watchlist`

返回收藏和决策清单。

#### `POST /api/v1/watchlist`

新增关注对象。

#### `PATCH /api/v1/watchlist/{id}`

更新状态、预算、备注、风险结论。

#### `DELETE /api/v1/watchlist/{id}`

删除 watchlist 项。

### 4.4 Launch Watch

#### `GET /api/v1/launch-watch`

返回未来 `1-3 年` 新盘 / 待抽签 / 近期开售观察池。

当前已返回的重点字段：

- `launch_stage`
- `expected_launch_window`
- `source`
- `signal_bucket`
- `signal_label`
- `signal_rank`
- `official_site_url`
- `srpe_url`
- `linked_development_id`
- `lat / lng`
- `coordinate_mode`

当前前端默认展示逻辑：

- `/launch-watch` 页面会按 `signal_rank + signal_bucket` 分组排序
- 更强的官方信号默认排在更前面，而不是单纯时间倒序

### 4.5 Transactions

#### `GET /api/v1/transactions`

成交参考页使用。

支持筛选：

- `development_id`
- `district`
- `transaction_type`
- `months`
- `saleable_area_band`
- `sort`

#### `GET /api/v1/transactions/stats`

返回成交统计聚合。

支持维度：

- `district`
- `development`
- `unit_type`
- `month`

说明：

- `transactions` 相关接口仍偏目标设计，当前并不是前端主入口
- 当前交易参考更多通过 development 聚合视图提供

### 4.6 Documents

#### `GET /api/v1/documents`

文档中心列表。

支持筛选：

- `development_id`
- `doc_type`
- `source`
- `published_from`
- `published_to`

#### `GET /api/v1/documents/{id}`

返回文档元数据与解析文本。

#### `GET /api/v1/documents/{id}/download`

下载或代理读取本地文件。

### 4.7 Commercial Monitor / System

#### `GET /api/v1/commercial-search-monitors`

返回商业 source monitor 列表与运行策略，供 `/system` 使用。

#### `GET /api/v1/health`

返回系统健康状态。

#### `GET /api/v1/system/*`

返回系统页需要的聚合视图，包括：

- overview
- refresh-jobs
- scheduler-plans
- recent refresh jobs
- source coverage / readiness
- configured refresh plans
- commercial monitor 运行状态

### 4.8 Policies

#### `GET /api/v1/policies/tax-estimate`

按价格、身份、日期返回估算税费。

参数：

- `price_hkd`
- `buyer_profile`
- `transaction_date`

返回：

- 分项税费
- 规则来源
- 计算解释

## 5. 响应对象建议

### 5.1 `development summary`

```json
{
  "id": "uuid",
  "name_zh": "示例楼盘",
  "district": "Hong Kong Island East",
  "listing_segment": "mixed",
  "location": {
    "lat": 22.0,
    "lng": 114.0
  },
  "price_range_hkd": {
    "min": 7800000,
    "max": 13200000
  },
  "active_listing_count": 8,
  "recent_transaction_summary": {
    "count_90d": 3,
    "median_price_per_sqft": 18200
  },
  "watchlist_state": "watch"
}
```

### 5.2 `listing feed event`

```json
{
  "event_type": "price_drop",
  "event_at": "2026-04-12T08:00:00Z",
  "listing_id": "uuid",
  "development": {
    "id": "uuid",
    "name_zh": "示例楼盘"
  },
  "old_price_hkd": 9200000,
  "new_price_hkd": 8880000,
  "source": "commercial_x"
}
```

## 6. 查询与分页

约定：

- 当前默认分页口径优先使用：`limit` + `offset`
- 地图接口允许单独使用 `bbox` + `limit`
- 大量聚合接口优先返回 summary，不直接下发海量明细

## 7. 排序约定

首版支持这些排序：

- `updated_desc`
- `price_asc`
- `price_desc`
- `psf_asc`
- `psf_desc`
- `completion_year_desc`
- `distance_to_mtr_asc`

## 8. 错误响应

统一结构：

```json
{
  "error": {
    "code": "not_found",
    "message": "development not found",
    "details": {}
  }
}
```

常见错误码：

- `bad_request`
- `not_found`
- `conflict`
- `validation_error`
- `internal_error`

## 9. 内部任务接口

如果 worker 通过 API 写入，建议单独走内部命名空间：

- `POST /internal/v1/ingest/snapshots`
- `POST /internal/v1/ingest/listings`
- `POST /internal/v1/ingest/transactions`
- `POST /internal/v1/analytics/recompute`

但首版也可以直接由 worker 访问 DB，避免过早抽象。

## 10. 首版最小 API 集

首版只实现这些就足以支撑可用原型：

1. `GET /api/v1/developments`
2. `GET /api/v1/developments/{id}`
3. `GET /api/v1/developments/{id}/listings`
4. `GET /api/v1/developments/{id}/transactions`
5. `GET /api/v1/listings/feed`
6. `GET /api/v1/documents`
7. `GET /api/v1/watchlist`
8. `POST /api/v1/watchlist`
9. `PATCH /api/v1/watchlist/{id}`
10. `GET /api/v1/system/sources`
