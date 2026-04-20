# Operations

本文件面向本机长期使用与后续更大批量真实数据导入前的稳定运行。

## Source Strategy

### SRPE

- 适合做 development / detail / official document 基线
- 建议保留日级 refresh
- 大批量补档时可用 `offset + limit` 逐步推进

### Centanet

- 推荐默认策略：
  - `default_limit = 20`
  - `detail_limit = 8`
  - `priority = 70`
  - `detail_policy = priority_only`
- 含义：
  - 搜索页保持中等覆盖
  - detail 只补重点 monitor
  - 避免整批 refresh 因全量 detail 过慢

### Ricacorp

- 推荐默认策略：
  - `default_limit = 30`
  - `with_details = false`
  - `priority = 55`
  - `detail_policy = never`
- 含义：
  - 先以 search-page listing 覆盖为主
  - 暂不把 detail enrichment 作为常规运行路径

## Cleanup

商业源 HTML 快照本身已经有按对象保留最近几份的内置裁剪。除此之外，建议定期做一次运行期清理：

```bash
conda run -n py311 hhi-worker cleanup-runtime-artifacts
```

默认策略：

- 删除 30 天以前、且超出每个 job_name 最近 20 条之外的 refresh jobs
- 删除 14 天以前的商业源 `search_page` HTML 快照，但每个对象至少保留最近 5 份
- 删除 7 天以前的商业源 `detail_page` HTML 快照，但每个对象至少保留最近 5 份

可调参数：

```bash
conda run -n py311 hhi-worker cleanup-runtime-artifacts \
  --refresh-job-days 45 \
  --keep-latest-jobs-per-name 30 \
  --search-snapshot-days 21 \
  --detail-snapshot-days 10 \
  --keep-latest-snapshots-per-object 8
```

## Preflight Validation

在准备扩大真实数据覆盖前，先做一次小规模 live 验收：

```bash
conda run -n py311 hhi-worker import-srpe-index --lang en --limit 20 --offset 120
conda run -n py311 hhi-worker run-commercial-search-monitors --source ricacorp
conda run -n py311 hhi-worker run-commercial-search-monitors --source centanet --limit-override 10
conda run -n py311 hhi-worker backfill-development-geography
```

重点查看：

- `/system`
  - `Recent Refresh Jobs`
  - `Commercial Search Monitors`
- `/map`
  - source filter
  - selected detail / open source
- `/listings`
  - recent market moves
- `/compare`
  - add/remove
  - suggested comparables

## Batch Expansion Advice

在正式扩大 monitor 数量前，建议按这个顺序推进：

1. 先增加 monitored search URLs，不立刻开 detail
2. 用 `priority_level` 标出重点 monitor
3. 只给高优先级 monitor 开 `detail_policy = priority_only`
4. 每次扩量后先看 `/system` 的 health 与 recent failures
5. 定期执行 `cleanup-runtime-artifacts`

### Buyer-Focus Rollout

如果目标是优先覆盖更适合你的盘，建议把优先级拆成两层：

1. `development coverage`
   - 先决定哪些楼盘值得进入候选池
   - 这里主要看：
     - `new`
     - `first_hand_remaining`
     - `second_hand <= 10 years`
     - `second_hand <= 15 years`
     - 核心区域
     - 是否已有商业源覆盖 / watchlist 信号
2. `listing expansion`
   - 再决定哪些盘值得继续补 commercial listing / detail
   - 这里才更重视：
     - 价值带：`HK$8M-HK$18M`
     - 房型优先：`2房 > 3房 > 1房 > 开放式`
     - 户型面积：`400-750 sqft`（约 `37-70 sqm`）

### Upcoming New Launch Watch

如果目标从“当前盘面”扩展到“未来 `1-3 年` 值得提前留意的新盘 / 待抽签项目”，建议单独维护一条 `launch-watch` 主线，而不要把它混进普通二手 listing refresh。

原因：

- `SRPE` 更适合“已经进入销售文件阶段”的一手项目
- 真正临近推售的盘，往往会先在：
  - `LandsD` 预售同意书统计
  - `SRPE` 近期价单 / 销售安排 / 楼书动作
  - 开发商官网 / 项目 microsite
  - 商业源一手快讯 / 新盘时间表
 里出现

建议顺序：

1. 先用 `LandsD pending / issued` 建最前置的官方预售信号层
2. 再用 `SRPE recent docs` 捕捉近期真的有价单 / 销售安排 / 楼书动作的项目
3. 需要更宽范围时，再用 `SRPE active` 补仍在官方一手链路中的近期开售窗口
4. 再给重点项目补 `official_site_url`
5. 再用商业源确认：
   - 是否开始开放示位
   - 是否开始收票 / 抽签
   - 是否进入首轮销售
6. 只有进入 `launch-watch` 高优先级的盘，才补更密集的日常追踪

如果先用人工整理的公开信号做第一批候选，可以直接同步：

```bash
conda run -n py311 hhi-worker sync-launch-watch-config --dry-run
conda run -n py311 hhi-worker sync-launch-watch-config
```

如果要把官方 `LandsD` 最新待批预售项目直接同步进 `launch-watch`：

```bash
conda run -n py311 hhi-worker sync-launch-watch-official --source landsd-pending --dry-run
conda run -n py311 hhi-worker sync-launch-watch-official --source landsd-pending
```

如果要把官方 `LandsD` 最新已批预售 / 转让同意项目同步进 `launch-watch`：

```bash
conda run -n py311 hhi-worker sync-launch-watch-official --source landsd-issued --dry-run
conda run -n py311 hhi-worker sync-launch-watch-official --source landsd-issued
```

默认配置文件：

- `configs/launch_watch_projects.toml`

查看当前候选池：

- `GET /api/v1/launch-watch`

如果想一条命令同步两类 `LandsD` 官方信号：

```bash
conda run -n py311 hhi-worker sync-launch-watch-official --source landsd-all --dry-run
conda run -n py311 hhi-worker sync-launch-watch-official --source landsd-all
```

如果想把近期真的在 `SRPE` 上有价单 / 销售安排 / 楼书动作的项目纳入观察池：

```bash
conda run -n py311 hhi-worker sync-launch-watch-official --source srpe-recent-docs --dry-run
conda run -n py311 hhi-worker sync-launch-watch-official --source srpe-recent-docs
```

如果想再把范围放宽到当前仍在 `SRPE` 一手链路里的近期开售项目：

```bash
conda run -n py311 hhi-worker sync-launch-watch-official --source srpe-active --dry-run
conda run -n py311 hhi-worker sync-launch-watch-official --source srpe-active
```

建议的 monitor 扩量顺序：

1. 先增加官方 `SRPE` development 覆盖，用来补新盘 / 一手余货底座
2. 再增加围绕重点区域和重点屋苑的 `Centanet` monitored searches
3. 只给已经出现 buyer-focus listing 信号的 monitor 开较高优先级和 detail
4. 再用 `Ricacorp` 补第二商业源视角，不急着全量开 detail
5. 对 `>15 years` 的 second-hand development 默认降级，不作为第一波自动扩量主力
6. 每次只增加少量 monitor，先看 compare / shortlist / map 是否开始出现噪音

## Config-Driven Monitor Expansion

如果开始进入“逐步扩量”的阶段，建议不要只在 `/system` 页面里手工加 monitor，而是同时维护一份配置文件：

- 默认文件：`configs/commercial_monitors.toml`

先 dry run 看会新增或更新什么：

```bash
conda run -n py311 hhi-worker sync-commercial-monitor-config --dry-run
```

确认无误后再实际写入数据库：

```bash
conda run -n py311 hhi-worker sync-commercial-monitor-config
```

建议做法：

1. 把“buyer-focus”相关 monitor 先写进这个 TOML
2. 每次扩量只新增少量 URL
3. 同步后再去 `/system` 看 health / strategy / recent failures

## Development-Driven Commercial Discovery

如果接下来要把商业源从“手工给 URL”推进到“自动扩量”，先不要盲扫全站。更稳的路径是：

1. 从当前 development pool 出发
2. 只挑还没有该 source 覆盖的楼盘
3. 按 buyer-focus 偏好给楼盘排序
4. 自动生成 source-specific search URL 候选
5. 可选地抓回结果页做验证
6. 只把验证通过的候选建成 monitor

Centanet：

```bash
conda run -n py311 hhi-worker discover-commercial-monitor-candidates --source centanet --limit 20 --validate
```

验证通过后，创建 inactive monitor 供 review：

```bash
conda run -n py311 hhi-worker discover-commercial-monitor-candidates --source centanet --limit 20 --validate --create-monitors
```

如果想直接进入 refresh：

```bash
conda run -n py311 hhi-worker discover-commercial-monitor-candidates --source centanet --limit 20 --validate --create-monitors --activate-created
```

如果已经有一批较早创建的 auto-discovered monitor，想按最新的两层优先级重算其策略：

```bash
conda run -n py311 hhi-worker rebalance-commercial-monitors --source centanet
conda run -n py311 hhi-worker rebalance-commercial-monitors --source ricacorp
```

Ricacorp 使用同一套命令：

```bash
conda run -n py311 hhi-worker discover-commercial-monitor-candidates --source ricacorp --limit 20 --validate
```

补充说明：

- `--include-existing`
  让 discovery 把已经有该 source coverage 的 development 也一起带出来，适合复查 URL 质量。
- `--development-id <id>`
  只针对单个楼盘做 discovery，适合先手动验证某个重点盘。

## Development-First Expansion

如果目标是先快速扩大当前 intel 的楼盘覆盖数，而不是立刻深抓每个盘内所有 listing，建议按下面顺序执行：

1. 先扩大官方 `SRPE` 的 development 覆盖
2. 再逐步增加商业源 monitor，让重点楼盘出现 source coverage
3. 只有当某个盘进入 shortlist / watchlist / buyer-focus 范围后，再继续补 listing detail

### Step 1: 扩官方楼盘覆盖

先按 offset 分批导入官方 development：

```bash
conda run -n py311 hhi-worker import-srpe-index --lang en --limit 100 --offset 0
conda run -n py311 hhi-worker import-srpe-index --lang en --limit 100 --offset 100
conda run -n py311 hhi-worker import-srpe-index --lang en --limit 100 --offset 200
```

如果想补官方 detail / document metadata，再对较小窗口开启：

```bash
conda run -n py311 hhi-worker import-srpe-index --lang en --limit 30 --offset 0 --with-details
```

### Step 2: 同步并运行商业 monitor

先把 `configs/commercial_monitors.toml` 里的 monitored URLs 同步到数据库：

```bash
conda run -n py311 hhi-worker sync-commercial-monitor-config --dry-run
conda run -n py311 hhi-worker sync-commercial-monitor-config
```

然后分别跑商业源：

```bash
conda run -n py311 hhi-worker run-commercial-search-monitors --source centanet --limit-override 20
conda run -n py311 hhi-worker run-commercial-search-monitors --source ricacorp --limit-override 30
```

### Step 3: 只对重点盘补 detail

如果某批 `Centanet` monitor 已经跑通，但还不想让 detail 成本太高，建议：

- 先把 monitor 的 `detail_policy` 设为 `priority_only`
- `detail_limit` 保持在 `8-12`
- 让 detail 只落在高优先级 monitor 上

## Failure and Blocking Signals

如果真实扩量时开始遇到风控、限流或抓取不稳定，系统当前会这样表现：

- 单条 detail 抓取失败：
  - batch 仍然成功
  - `summary.detail_failures` 上升
  - `/system` 中 monitor health 变成 `warning`

- 单个 monitor 整体失败：
  - `Recent Refresh Jobs` 出现 `failed`
  - batch wrapper 不会拖垮其他 monitor
  - `/system` 中该 monitor 会变成 `failing`

- 很久没成功运行：
  - `/system` 中会变成 `stale`

常见触发信号包括：

- `403 / 429`
- captcha / challenge 页面
- 连接超时明显增多
- detail_failures 持续升高

遇到这种情况时，当前推荐的第一反应不是立刻全量重跑，而是先：

1. 下调 `default_limit`
2. 关闭或收紧 `with_details / detail_limit`
3. 降低 monitor 数量和频率
4. 观察 `/system` 的 health 是否恢复

如果这样仍然持续失败，再进入代理 / 随机 IP 方案。
