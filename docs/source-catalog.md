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

### 2.2A：预售 / 待抽签 / 新盘前哨源

用途：

- 提前发现未来 `1-3 年` 可能进入销售期的新盘
- 在 `SRPE` 正式出现之前，先建立 `development watch` 候选池
- 追踪“准备开价 / 开放示位 / 收票 / 抽签 / 首轮销售”这些时效性更强的节点

特点：

- `SRPE` 只能覆盖已经进入《一手住宅物业销售条例》销售文件链路的项目
- 对“快将推售”或“刚获预售但未正式上载完整销售文件”的项目，往往不够早
- 需要官方与商业信号交叉验证，而不是只信单一站点

建议优先接入：

1. Lands Department `pre-sale consent` 月报 / 季报
2. Housing Bureau `Private Housing Supply in the Primary Market`
3. SRPA / SRPE 中 vendor-designated website 入口
4. 开发商项目官网或项目 microsite
5. 商业源的一手快讯 / 新盘时间表页

系统定位：

- 这类 source 先服务 `development discovery`
- 不直接当作 listing 真相源
- 更适合产出：
  - `launch_watch`
  - `expected_launch_window`
  - `official_site_url`
  - `watch_reason`

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

当前已锁定的首批商业源优先级：

1. 中原地产香港 `https://hk.centanet.com/info/index`
2. 利嘉阁 `https://www.ricacorp.com/zh-hk/`

说明：

- 这两个 source 已写入开发基线，后续不会被遗忘或替换成低优先级站点
- 当前实现里，这两个商业源都已经进入日常可用状态：
  - `Centanet`：commercial discovery / monitor / batch refresh 已打通
  - `Ricacorp`：commercial discovery / monitor / batch refresh 已打通
- 当前角色分工更准确地说是：
  1. `SRPE` 提供官方 development / document 基线
  2. `Centanet` 负责主商业源 listing 扩量
  3. `Ricacorp` 提供第二商业源视角与交叉验证

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

当前实现里，source adapter 能力主要由代码固定；可配置运行入口分别维护在 `configs/commercial_monitors.toml`、`configs/launch_watch_projects.toml` 和 `configs/scheduler.toml`。如果后续 source 数量继续扩大，再考虑增加独立的 source registry 配置。

## 4. 建议首批接入顺序

### Phase 1

1. SRPE
2. 地址/地理标准化服务
3. 一个商业 listing 源
   当前锁定为中原地产香港

目标：

- 打通新盘、一手余货、地图定位、文档抓取、基础二手供给补充

当前状态补充：

- Phase 1 定义下的 `SRPE` 基线已经完成
- 商业源不再只是“后续阶段规划”，而是已经进入日常运行
- `launch-watch` 也已形成一条独立官方观察池主线：
  - `landsd-pending`
  - `landsd-issued`
  - `srpe-recent-docs`
  - `srpe-active`

### Phase 2

1. 第二个商业 listing 源
   当前锁定为利嘉阁
2. 预售 / 待抽签 / 新盘前哨源
3. 成交/统计类官方源
4. 图片补齐和文档抽取增强

当前状态补充：

- `利嘉阁` 已不再只是规划项，而是当前已可用的第二商业源
- `预售 / 待抽签 / 新盘前哨源` 已有第一版落地，当前优先级最高的是：
  - `LandsD pre-sale consent`
  - `SRPE recent docs`
  - `SRPE active`
- `Housing Bureau` 仍更适合作为宏观供应背景层，而不是当前项目级观察池的主清单
- 当前 UI 会把这些官方观察信号进一步分成：
  - `LandsD Pending`
  - `LandsD Issued`
  - `Recent Pricing`
  - `Recent Brochure`
  - `SRPE Active`
  - `Commercial Launch`
- `Commercial Launch` 是商业一手快讯/新盘提示的交叉验证层，不替代 `LandsD / SRPE` 官方信号

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

当前实现采用“官方扩盘、商业补充”的身份策略：

- `SRPE` development 是官方 canonical identity 的最高优先级来源
- `Centanet / Ricacorp` 匹配到已有 SRPE 楼盘时，不覆盖 `source / source_external_id / source_url` 这类主身份字段
- 商业源仍然可以补 `aliases_json / tags_json / developer_names_json`、缺失地址与地区字段、listing、价格事件和覆盖状态
- 如果先由商业源创建了 development，后续 SRPE 命中同盘时，允许提升为 SRPE canonical identity
- `/system` 会统计“商业 canonical 但已有官方 artifacts”的异常，用来提示是否有历史数据需要复查

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
