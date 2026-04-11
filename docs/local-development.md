# 本地开发

## 1. 当前定位

Phase 0 默认采用轻量本地开发模式，不依赖 Docker。

- Python: `conda` 环境 `py311`
- Web: 本地 Node.js
- Database: 默认 SQLite
- Docker: 可选，仅在后续需要 PostgreSQL/PostGIS 时引入

## 2. Python 依赖安装

在仓库根目录执行：

```bash
conda run -n py311 python -m pip install -e ".[dev]"
```

## 3. Web 依赖安装

```bash
npm install
```

## 4. 环境变量

复制环境模板：

```bash
cp .env.example .env
```

如果需要切到 PostgreSQL，可修改：

```bash
HHI_DATABASE_URL=postgresql+psycopg://user:password@127.0.0.1:5432/hk_home_intel
```

如果前端运行在 `localhost:3000` 或 `127.0.0.1:3000`，默认 CORS 已允许这两个来源。若你后续改了前端地址，可同步修改：

```bash
HHI_CORS_ALLOW_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
```

## 5. 启动 API

```bash
conda run -n py311 hhi-api
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/v1/health
```

## 6. 启动 worker

```bash
conda run -n py311 hhi-worker
```

## 7. 启动 Web

```bash
npm run dev:web
```

默认地址：

- Web: `http://127.0.0.1:3000`
- API: `http://127.0.0.1:8000`

## 8. 当前 Phase 0 能力

- FastAPI 服务骨架
- 基础健康检查
- worker 占位命令
- Next.js 本地页面骨架
- 运行目录自动初始化
- Alembic 迁移脚手架

## 9. 后续计划

- Phase 1 引入首批 schema 与 revision
- Phase 1 接入首个 source adapter
- Phase 1 增加 development 列表和地图接口
