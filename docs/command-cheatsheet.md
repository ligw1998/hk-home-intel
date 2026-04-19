# Command Cheatsheet

本文件是本项目的运行命令速记版，目标是回答两类问题：

- 现在要扩哪些盘，先跑什么、后跑什么
- 每条命令到底在做什么

默认工作目录：

```bash
cd /Users/ligw1998/Projects/hk-home-intel
```

默认 Python 环境：

```bash
conda run -n py311 ...
```

## 0. Fresh Clone Setup

如果你是在另一台电脑上 `git clone` 一个全新仓库，先做这套准备：

```bash
git clone <your-repo-url>
cd hk-home-intel
conda create -n py311 python=3.11 -y
conda run -n py311 python -m pip install --no-build-isolation -e ".[dev]"
npm install
cp .env.example .env
conda run -n py311 alembic upgrade head
```

启动：

```bash
conda run -n py311 hhi-api
npm run dev:web
```

快速检查：

```bash
curl http://127.0.0.1:8000/api/v1/health
```

如果是空库，接下来再按本文件里的 `SRPE -> commercial discovery -> batch refresh -> launch-watch` 顺序导入数据。

## Source Roles

先记住各 source 的角色：

- `SRPE`
  - 官方 development / document 基线
  - 偏新盘、一手、一手余货、曾进入官方销售披露链路的项目
- `Centanet`
  - 第一商业源
  - 当前最成熟的 commercial listing 扩量源
- `Ricacorp`
  - 第二商业源
  - 用来补另一视角，不完全依赖单一商业站点
- `launch-watch`
  - 未来 `1-3 年` 新盘 / 待抽签 / 近期开售观察池
  - 不等同于普通 listing feed

## 1. Quickstart

如果你现在想做一轮“围绕偏好盘扩量”的标准流程，直接按这个顺序：

```bash
conda run -n py311 hhi-worker import-srpe-index --lang en --limit 1000 --offset 0
conda run -n py311 hhi-worker discover-commercial-monitor-candidates --source centanet --limit 20 --validate --create-monitors
conda run -n py311 hhi-worker set-commercial-monitors-active --source centanet --auto-discovered
conda run -n py311 hhi-worker discover-commercial-monitor-candidates --source ricacorp --limit 20 --validate --create-monitors
conda run -n py311 hhi-worker set-commercial-monitors-active --source ricacorp --auto-discovered
conda run -n py311 hhi-worker run-commercial-search-monitors --source centanet --limit-override 20
conda run -n py311 hhi-worker run-commercial-search-monitors --source ricacorp --limit-override 20
```

如果你还想把未来新盘观察池一起刷新，再加：

```bash
conda run -n py311 hhi-worker sync-launch-watch-official --source landsd-pending
conda run -n py311 hhi-worker sync-launch-watch-official --source landsd-issued
```

## 2. Expand Development Base

### SRPE Import

最常用：

```bash
conda run -n py311 hhi-worker import-srpe-index --lang en --limit 1000 --offset 0
```

作用：

- 从 `SRPE` 官方住宅项目索引导入一批 development
- 补官方名称、地址、经纬度、document 元信息
- 现在也会补一个低成本年份 proxy，用于 `/map` 的 `Max Age (Years)` 更早生效

注意：

- 这条命令不会按你的买家偏好筛盘
- 它主要是扩官方底座，不是 buyer-focus 精筛
- `SRPE` 不是“全香港所有楼盘”，而是“进入过 SRPE 官方销售披露体系的住宅项目”

### `--lang`

- `--lang en`
  - 走英文接口
  - 通常更适合做 canonical development 基线
- `--lang zh-HK`
  - 走中文接口
  - 更适合补中文显示字段

### `--offset` 说明

```bash
conda run -n py311 hhi-worker import-srpe-index --lang en --limit 100 --offset 100
conda run -n py311 hhi-worker import-srpe-index --lang en --limit 100 --offset 200
```

含义：

- `offset` 目前是“从 SRPE 当前返回列表换一个起点取窗口”
- 它更像轮转窗口，不是严格的 API 分页

所以它适合：

- 逐步往后扫更多 development

但不适合把它理解成：

- 精确的第 `101-200` 条、第 `201-300` 条分页语义

## 3. Expand Commercial Sources

这部分是 buyer-focus 扩量的主线。

### 步骤 1：发现并验证候选盘

中原：

```bash
conda run -n py311 hhi-worker discover-commercial-monitor-candidates --source centanet --limit 20 --validate
```

利嘉阁：

```bash
conda run -n py311 hhi-worker discover-commercial-monitor-candidates --source ricacorp --limit 20 --validate
```

作用：

- 从当前 development pool 里挑“值得补商业源”的盘
- 生成 source-specific `search_url`
- `--validate` 会实际访问结果页，确认 URL 确实对应该盘

你可以把这一步理解成：

- 找盘
- 验证入口是否靠谱

### 步骤 2：把候选注册成 monitor

中原：

```bash
conda run -n py311 hhi-worker discover-commercial-monitor-candidates --source centanet --limit 20 --validate --create-monitors
```

利嘉阁：

```bash
conda run -n py311 hhi-worker discover-commercial-monitor-candidates --source ricacorp --limit 20 --validate --create-monitors
```

作用：

- 对验证通过的候选创建 commercial monitor
- 如果 monitor 早就存在，不会重复创建

输出里重点看：

- `validated`
- `existing_monitor_id`
- `created_monitor_id`

### 步骤 3：批量启用 auto-discovered monitors

中原：

```bash
conda run -n py311 hhi-worker set-commercial-monitors-active --source centanet --auto-discovered
```

利嘉阁：

```bash
conda run -n py311 hhi-worker set-commercial-monitors-active --source ricacorp --auto-discovered
```

作用：

- 把 auto-discovered monitors 设为 `active = true`
- 之后 batch refresh 就会默认跑它们

如果想暂停：

```bash
conda run -n py311 hhi-worker set-commercial-monitors-active --source centanet --auto-discovered --inactive
```

如果只想先动前几条：

```bash
conda run -n py311 hhi-worker set-commercial-monitors-active --source ricacorp --auto-discovered --limit 3
```

### 步骤 4：真正抓 listing

中原：

```bash
conda run -n py311 hhi-worker run-commercial-search-monitors --source centanet --limit-override 20
```

利嘉阁：

```bash
conda run -n py311 hhi-worker run-commercial-search-monitors --source ricacorp --limit-override 20
```

作用：

- 真正执行 active monitors
- 抓搜索页
- 导入 listing
- 记录 snapshot
- 按 monitor 策略决定要不要抓 detail
- 产出 `price_events`

说明：

- `Centanet` 当前通常更重，因为很多 monitor 会带 detail
- `Ricacorp` 当前默认更轻，主要是 search-page listing 覆盖

### 临时包含 inactive monitor

如果只是临时验证，不想先激活：

```bash
conda run -n py311 hhi-worker run-commercial-search-monitors --source centanet --limit-override 20 --include-inactive
conda run -n py311 hhi-worker run-commercial-search-monitors --source ricacorp --limit-override 20 --include-inactive
```

## 4. Refresh New Launch Watch

### 手工 starter seeds

```bash
conda run -n py311 hhi-worker sync-launch-watch-config --dry-run
conda run -n py311 hhi-worker sync-launch-watch-config
```

作用：

- 同步 `configs/launch_watch_projects.toml`
- 把人工整理的新盘观察项写入系统

### 官方来源

待批预售：

```bash
conda run -n py311 hhi-worker sync-launch-watch-official --source landsd-pending --dry-run
conda run -n py311 hhi-worker sync-launch-watch-official --source landsd-pending
```

已批预售 / 转让同意：

```bash
conda run -n py311 hhi-worker sync-launch-watch-official --source landsd-issued --dry-run
conda run -n py311 hhi-worker sync-launch-watch-official --source landsd-issued
```

作用：

- 从官方 `LandsD` 把未来 `1-3 年` 值得提前跟踪的新盘项目同步进观察池
- 尽量补 `official_site_url` / `linked_development`

查看位置：

- `/launch-watch`
- `/map` 里打开 `Show launch-watch`

## 5. Daily Maintenance

如果不是大扩量，而是日常刷新，建议这几条就够：

```bash
conda run -n py311 hhi-worker import-srpe-index --lang en --limit 50 --offset 0
conda run -n py311 hhi-worker run-commercial-search-monitors --source centanet --limit-override 20
conda run -n py311 hhi-worker run-commercial-search-monitors --source ricacorp --limit-override 20
conda run -n py311 hhi-worker sync-launch-watch-official --source landsd-pending
```

然后看：

- `/map`
- `/launch-watch`
- `/system`

## 6. Common Outputs

### `validated`

- `true`
  - 入口验证通过
- `false`
  - 候选 URL 不够可靠，不会继续创建 monitor

### `existing_monitor_id`

- 非空
  - 这条 monitor 已经存在
  - 系统会去重，不会重复创建

### `created_monitor_id`

- 非空
  - 本次新建成功

### `failed_monitor_count`

- 表示整条 monitor 运行失败数量
- 常见原因：
  - 搜索页超时
  - 目标站点临时慢
  - 页面结构变化

### `detail_failures`

- 表示搜索页成功，但部分 detail enrichment 失败
- 不等于整条 monitor 失败

## 7. Recommended Mental Model

把整套流程记成四步就够：

1. `import-srpe-index`
   - 扩官方 development 底座
2. `discover-commercial-monitor-candidates`
   - 找值得补商业源的盘，并验证入口
3. `set-commercial-monitors-active`
   - 启用 monitor
4. `run-commercial-search-monitors`
   - 真正抓 listing

如果再加未来新盘，就是第 5 步：

5. `sync-launch-watch-*`
   - 刷新未来 `1-3 年` 新盘观察池

## 8. Related Docs

- [operations.md](./operations.md)
- [source-catalog.md](./source-catalog.md)
- [roadmap.md](./roadmap.md)
- [local-development.md](./local-development.md)
