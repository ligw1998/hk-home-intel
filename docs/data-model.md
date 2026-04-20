# 数据模型

## 1. 建模目标

模型的核心不是“网页上的房源记录”，而是统一表达以下对象：

- 楼盘/屋苑
- 期数/座
- 户型模板
- 具体单位
- 在售记录
- 成交记录
- 原始文档
- 价格和状态变化事件
- 用户自己的决策记录

设计原则：

- canonical object 与 source snapshot 分离
- 强制保留原始 payload 和来源字段
- 允许 `unit_instance` 缺失，避免因识别不到单位而丢数据
- 派生分析尽量落到独立表，减少主表污染

## 2. 当前实现基线与目标模型

当前数据库里已经稳定使用的核心对象是：

- `development`
- `listing`
- `transaction`
- `document`
- `price_event`
- `source_snapshot`
- `watchlist_item`
- `launch_watch_project`
- `search_preset`
- `commercial_search_monitor`
- `refresh_job_run`

也就是说，当前系统是以 `development / listing / transaction / document / monitor / launch-watch` 这组对象为主干。

下面这张关系图里，`phase_block / unit_type / unit_instance` 更偏后续增强目标，而不是当前每条数据都已经稳定落库的强依赖。

## 3. 实体关系总览

```text
development 1---n listing
development 1---n transaction
development 1---n document
listing 1---n price_event
development 1---n watchlist_item
development 1---n launch_watch_project
development 1---n commercial_search_monitor

# target enhancement
development 1---n phase_block
development 1---n unit_type
phase_block 1---n unit_type
phase_block 1---n unit_instance
unit_type 1---n unit_instance
unit_instance 1---n listing
unit_instance 1---n transaction
unit_instance 1---n watchlist_item
```

## 4. 核心主表

### 4.1 `development`

楼盘/屋苑级对象，是地图和详情页的主入口。

```text
development
- id
- name_zh
- name_en
- aliases_json
- address_raw
- address_normalized
- district
- subdistrict
- region
- lat
- lng
- location_point           # 未来若切 PostGIS 时可引入
- developer_names_json
- tenure_type
- completion_year
- age_years
- phase_count
- block_count
- listing_segment        # new / first_hand_remaining / second_hand / mixed
- tags_json
- source_confidence
- created_at
- updated_at
```

说明：

- `aliases_json` 保存别名和不同来源的命名
- 当前实现主要依赖 `lat / lng`
- `location_point` 更适合作为未来 PostgreSQL + PostGIS 扩展位
- `listing_segment` 是当前系统视角下的主要归类，不是永久属性
- API 层会基于 `development + listing + document + transaction` 再聚合出：
  - `source_coverage`
  - `coverage_status`
  - `coverage_notes`
  - `data_gap_flags`
  这些属于派生摘要，而不是持久化主表字段

### 4.2 `listing`

市场上的一次在售记录，不等于 canonical 单位本身。

```text
listing
- id
- source
- source_listing_id
- source_url
- development_id
- phase_block_id
- unit_instance_id
- unit_type_id
- title
- listing_type           # new / first_hand_remaining / second_hand
- asking_price_hkd
- price_per_sqft
- bedrooms
- bathrooms
- saleable_area_sqft
- gross_area_sqft
- status                 # active / pending / sold / withdrawn / unknown
- first_seen_at
- last_seen_at
- last_snapshot_id
- raw_payload_json
- created_at
- updated_at
```

说明：

- `source + source_listing_id` 建唯一索引
- `unit_instance_id` 允许为空，便于先落库再补识别

### 4.3 `transaction`

成交事实，可来自 SRPE、官方统计、商业站点或手工录入。

```text
transaction
- id
- source
- source_record_id
- source_url
- development_id
- phase_block_id
- unit_instance_id
- unit_type_id
- transaction_date
- registration_date
- price_hkd
- price_per_sqft
- transaction_type       # primary / secondary
- payment_terms_json
- doc_ref
- raw_payload_json
- created_at
- updated_at
```

### 4.4 `document`

原始文档及其解析结果。

```text
document
- id
- development_id
- phase_block_id
- source
- source_doc_id
- source_url
- doc_type               # brochure / price_list / sales_arrangement / transaction_record / floor_plan
- title
- file_path
- mime_type
- content_hash
- published_at
- parsed_text
- metadata_json
- created_at
- updated_at
```

### 4.5 `price_event`

用于房源流和价格历史追踪。

```text
price_event
- id
- listing_id
- event_type             # new_listing / price_drop / price_raise / relist / sold / withdrawn / status_change
- old_price_hkd
- new_price_hkd
- old_status
- new_status
- event_at
- snapshot_id
- created_at
```

### 4.6 `watchlist_item`

用户自己的决策对象。

```text
watchlist_item
- id
- development_id
- unit_instance_id
- decision_stage         # watch / visit / negotiate / hold / reject / buy
- personal_score
- expected_budget_hkd
- estimated_tax_hkd
- note
- risk_note
- contact_json
- created_at
- updated_at
```

### 4.7 `launch_watch_project`

未来 `1-3 年` 新盘 / 待抽签 / 近期开售观察池对象。

```text
launch_watch_project
- id
- source
- source_project_id
- display_name
- district
- region
- launch_stage
- expected_launch_window
- official_site_url
- srpe_url
- linked_development_id
- is_active
- note
- raw_payload_json
- created_at
- updated_at
```

### 4.8 `commercial_search_monitor`

商业 source 的可运行搜索入口。

```text
commercial_search_monitor
- id
- source
- name
- search_url
- scope_type
- development_id
- is_active
- priority_level
- default_limit
- with_details
- detail_limit
- detail_policy
- created_at
- updated_at
```

### 4.9 目标增强表：`phase_block / unit_type / unit_instance`

这三张表仍属于后续增强目标，用来更细地表达期数、座、户型模板与具体单位。

### 4.9.1 `phase_block`

表达期数、座、栋等楼栋层级。

```text
phase_block
- id
- development_id
- phase_name
- block_name
- tower_no
- address_fragment
- completion_year
- floor_count
- unit_count
- created_at
- updated_at
```

### 4.9.2 `unit_type`

户型模板，便于跨楼盘对比。

```text
unit_type
- id
- development_id
- phase_block_id
- layout_signature
- bedrooms
- bathrooms
- saleable_area_sqft
- gross_area_sqft
- balcony_area_sqft
- utility_platform_area_sqft
- orientation_default
- floor_plan_asset_id
- source_confidence
- created_at
- updated_at
```

建议：

- `layout_signature` 用于归并相似户型，如 `3br-2ba-742sf-rect-living`

### 4.9.3 `unit_instance`

具体到楼层和室号的单位实例。

```text
unit_instance
- id
- development_id
- phase_block_id
- unit_type_id
- floor_label
- floor_numeric
- flat
- room_no
- orientation
- view_tags_json
- saleable_area_sqft
- gross_area_sqft
- is_rooftop
- is_special_unit
- created_at
- updated_at
```

## 5. 辅助表

### 5.1 `source_snapshot`

保存抓取快照元数据。

```text
source_snapshot
- id
- source
- object_type
- object_external_id
- source_url
- snapshot_kind          # html / json / pdf / image
- file_path
- content_hash
- http_status
- fetched_at
- parse_status
- metadata_json
```

### 5.2 `development_alias`

强化 development 名称映射。

```text
development_alias
- id
- development_id
- alias
- language
- source
- confidence
- created_at
```

### 5.3 `address_mapping`

标准地址与原始地址的映射。

```text
address_mapping
- id
- raw_address
- normalized_address
- geocode_source
- lat
- lng
- confidence
- created_at
- updated_at
```

### 5.4 `policy_rule`

税费和政策规则。

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
- created_at
- updated_at
```

### 5.5 `comparable_set`

可比盘结果缓存。

```text
comparable_set
- id
- anchor_type            # development / unit_type / unit_instance
- anchor_id
- comparable_type
- comparable_id
- score
- reason_json
- created_at
- updated_at
```

## 6. 主键与约束建议

- 所有主表使用 UUID
- `listing(source, source_listing_id)` 唯一
- `transaction(source, source_record_id)` 尽量唯一
- `document(source, source_doc_id)` 或 `content_hash` 做去重辅助
- `development(name_zh, address_normalized)` 不能强制唯一，需保留人工裁决空间

## 7. 索引建议

### 7.1 常规索引

- `development(district, subdistrict, completion_year)`
- `listing(status, listing_type, asking_price_hkd)`
- `transaction(transaction_date, transaction_type)`
- `document(doc_type, published_at)`
- `price_event(event_at, event_type)`

### 7.2 地理索引

- `development(location_point)` 上建 GiST 索引

### 7.3 搜索索引

- `development(name_zh, name_en, aliases_json)` 的 FTS 向量
- `listing(title)` 的 FTS 向量
- `document(parsed_text)` 的 FTS 向量

## 8. 版本化策略

以下对象建议用“当前态 + 快照/事件”并存：

- `listing`
- `document`
- `development` 的关键名称与地址字段

不建议每次直接覆盖后丢失历史。

实现方式建议二选一：

1. 主表存当前态，历史进入 `_history` 表
2. 主表存当前态，变化通过 `source_snapshot` + `price_event` + `audit_log` 回放

首版优先第二种，复杂度更低。

## 9. 统一字段口径

为避免后续混乱，以下口径建议在 schema 层固定：

- 面积默认使用平方呎 `sqft`
- 价格默认使用港币 `HKD`
- 时间统一存 UTC，展示时转香港时区
- 楼层同时保留原始字符串和可排序数值
- `listing_type` 与 `transaction_type` 分离，不混用

## 10. 状态机建议

### 10.1 `listing.status`

```text
unknown -> active -> pending -> sold
                \-> withdrawn
```

### 10.2 `watchlist_item.decision_stage`

```text
watch -> visit -> negotiate -> buy
   \-> hold
   \-> reject
```

## 11. 派生指标建议

以下指标不直接放主表原子字段，可通过物化视图或分析表生成：

- development 最近 30/90 天 active listing 数
- development 最近 6/12 个月成交中位数
- unit_type 可比均价
- price_event 日增量统计
- watchlist 决策摘要

## 12. 首版最小表集

如果首版控制复杂度，只先建这些表：

- `development`
- `listing`
- `transaction`
- `document`
- `source_snapshot`
- `watchlist_item`

第二阶段再补：

- `phase_block`
- `unit_type`
- `unit_instance`
- `price_event`
- `policy_rule`
- `comparable_set`
