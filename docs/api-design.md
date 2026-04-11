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

## 4. API 分组

### 4.1 Developments

#### `GET /api/v1/developments`

地图和列表入口。

支持筛选：

- `listing_segment`
- `district`
- `subdistrict`
- `price_min`
- `price_max`
- `saleable_area_min`
- `saleable_area_max`
- `bedrooms`
- `completion_year_min`
- `completion_year_max`
- `near_mtr`
- `bbox`
- `tags`
- `sort`
- `page`
- `page_size`

返回：

- 基础摘要
- 地图点位
- 当前价格带
- active listing 数
- 最近成交摘要
- watchlist 状态

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

### 4.2 Units

#### `GET /api/v1/unit-types/{id}`

返回户型模板详情。

#### `GET /api/v1/unit-types/compare`

批量对比多个户型模板。

参数：

- `ids`

返回：

- 面积
- 房型
- 单价
- 总价
- 图纸
- 关键标签
- 同盘/跨盘可比说明

#### `GET /api/v1/unit-instances/{id}`

返回具体单位详情与相关 listing、transaction。

### 4.3 Listings

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

#### `GET /api/v1/listings/{id}`

返回单条 listing 详情和历史。

#### `GET /api/v1/listings/{id}/events`

返回价格与状态变动时间线。

### 4.4 Transactions

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

### 4.5 Documents

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

### 4.6 Watchlist

#### `GET /api/v1/watchlist`

返回收藏和决策清单。

#### `POST /api/v1/watchlist`

新增关注对象。

请求体：

```json
{
  "development_id": "uuid",
  "unit_instance_id": "uuid",
  "decision_stage": "watch",
  "note": "optional"
}
```

#### `PATCH /api/v1/watchlist/{id}`

更新状态、预算、备注、风险结论。

#### `DELETE /api/v1/watchlist/{id}`

删除 watchlist 项。

### 4.7 Policies

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

### 4.8 System

#### `GET /api/v1/system/health`

返回系统健康状态。

#### `GET /api/v1/system/sources`

返回各 source 最近更新时间、失败次数、成功率。

#### `GET /api/v1/system/jobs`

返回近期任务执行记录。

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

- 默认分页参数：`page=1`, `page_size=20`
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
