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
