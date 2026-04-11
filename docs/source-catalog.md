# 数据源目录

## 1. 目标

数据源设计不是“尽可能多抓站点”，而是明确每类 source 在系统中的角色：

- 哪些是事实地基
- 哪些是实时补充
- 哪些只用于地址和地理标准化
- 哪些需要人工介入

## 2. Source 分层

### 2.1 A 类：官方结构化源

用途：

- 宏观市场背景
- 一手官方文档
- 成交和库存的可信基线

特点：

- 可信度最高
- 更新频率较低
- 结构相对稳定

建议优先接入：

1. SRPE
2. Land Registry / data.gov.hk 相关统计
3. Rating and Valuation Department 统计

### 2.2 B 类：半官方与地理服务源

用途：

- 地址标准化
- 楼盘定位
- 中英文地址/楼盘映射

特点：

- 适合做 normalization 辅助
- 不适合作为唯一真相源

建议优先接入：

1. Address Lookup Service
2. Lands Department Location Search / Geocoding 类服务

### 2.3 C 类：商业 listing 源

用途：

- 当前在售状态
- 图片
- 装修描述
- 经纪备注
- 二手实时供给

特点：

- 实时性最好
- 噪声最高
- 字段口径不统一
- 反爬和页面结构变化风险高

对系统的定位：

- 作为 `listing_snapshot` 和补充字段来源
- 不作为唯一事实源

### 2.4 D 类：人工补充源

用途：

- 你自己上传的 PDF、楼书、平面图、聊天截图
- 经纪口头信息整理
- 看房笔记和主观风险判断

特点：

- 价值很高
- 无法完全自动化
- 需要系统原生支持录入和归档

## 3. Source Adapter 统一模型

每个 source 通过独立 adapter 接入，至少声明这些能力：

```yaml
source:
  name:
  kind: official|geo|commercial|manual
  priority:
  discover_mode:
  fetch_mode:
  rate_limit:
  retry_policy:
  supports_documents:
  supports_images:
  supports_transactions:
```

建议在 `configs/sources.yaml` 中维护。

## 4. 建议首批接入顺序

### Phase 1

1. SRPE
2. 地址/地理标准化服务
3. 一个商业 listing 源

目标：

- 打通新盘、一手余货、地图定位、文档抓取、基础二手供给补充

### Phase 2

1. 第二个商业 listing 源
2. 成交/统计类官方源
3. 图片补齐和文档抽取增强

### Phase 3

1. 更多商业源
2. 手工录入面板
3. 高价值 watchlist 项目专项抓取

## 5. 各类 source 采集策略

### 5.1 官方文档型

适用对象：

- SRPE 文档页
- 政府开放数据

策略：

- 定时拉取索引页
- 对文档链接做内容哈希去重
- 文档更新后触发解析流水线

### 5.2 商业列表型

适用对象：

- 中介列表页与详情页

策略：

- 低频 discover
- 命中增量后再抓 detail
- 首选列表页 diff，减少无效详情请求
- 每个 source 独立限速和退避

### 5.3 地理服务型

适用对象：

- 地址标准化接口
- geocoding 服务

策略：

- 先缓存后请求
- 同一原始地址不重复调用
- 人工纠错优先级高于外部服务返回

## 6. 关键字段优先级

不同 source 间应定义字段优先级，而不是简单覆盖。

建议：

- 地址标准名：官方地理服务 > 官方文档 > 商业 listing
- 价单/成交：SRPE/官方文档 > 商业 listing
- 图片：商业 listing > 开发商公开物料 > 手工补充
- 在售状态：商业 listing 当前态 + 官方文档交叉校验

## 7. Source 可信度模型

建议每条记录附带 `source_confidence`，可用三档起步：

- `high`
- `medium`
- `low`

判定示例：

- 官方成交纪录：`high`
- SRPE 价单与售楼书：`high`
- 商业站点标准字段：`medium`
- 经纪备注和机器提取字段：`low`

## 8. 反风控与节流原则

商业源遵循以下原则：

- 低频、随机化间隔
- 列表页优先，详情页按需抓取
- 缓存 `etag`、`last-modified` 或内容哈希
- 失败后指数退避
- 不做并发刷站
- 不做分布式抓取
- 不绕过登录或付费墙

## 9. 原始快照保存策略

对每个 source，建议落以下至少一种快照：

- 原始 HTML
- 原始 JSON
- 文档文件
- 图片缩略图或原图

额外元数据：

- source URL
- fetched at
- content hash
- parser version
- selector version

## 10. 解析与落库策略

建议分两步：

1. `raw -> parsed`
2. `parsed -> canonical`

不要在抓取阶段直接写主表。

原因：

- 方便重跑解析
- 页面选择器变更时可回放
- 可分别审计抓取错误和规范化错误

## 11. 人工补充入口设计

需要支持以下手工对象：

- 新楼盘或别名手动映射
- 单位识别纠错
- 文档上传
- 看房笔记
- 经纪联系人
- 风险标签

这部分不是补丁功能，而是系统长期质量的重要组成。

## 12. Source 失败处理

每个 source 需要以下监控字段：

- 最近成功时间
- 连续失败次数
- 最近错误类型
- 选择器版本
- 平均抓取耗时

失败策略建议：

- 连续失败触发告警
- 暂停高成本详情抓取
- 保留失败样本快照以便调试
