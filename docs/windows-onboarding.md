# Windows Onboarding

本项目可以在 Windows + conda 环境下运行，不需要额外改业务代码。Windows 主要差异在于 PowerShell 命令写法、Node.js/npm 安装方式、SQLite 路径和可能的 `npm.ps1` 执行策略。

## 1. 前置工具

需要先准备：

- `git`
- `conda` 或 `miniconda`
- Python `3.11`
- Node.js `20+`
- `npm`

检查：

```powershell
git --version
conda --version
node --version
npm --version
```

如果 `node` 或 `npm` 不存在，任选一种方式安装。

## 2. 安装 Node.js / npm

### 方式 A：winget 安装系统级 Node.js

适合这台 Windows 还会跑其他前端项目的情况。

```powershell
winget install OpenJS.NodeJS.LTS
```

安装后重新打开 PowerShell，再检查：

```powershell
node --version
npm --version
```

### 方式 B：conda 安装 Node.js

适合希望 Node.js 跟项目 conda 环境绑定的情况。

```powershell
conda create -n py311 python=3.11 -y
conda activate py311
conda install -c conda-forge nodejs=20 -y
```

检查：

```powershell
node --version
npm --version
```

如果你已经有 `py311` 环境，只需要执行 `conda activate py311` 和 `conda install -c conda-forge nodejs=20 -y`。

### 方式 C：官网下载 LTS

也可以直接安装 Node.js LTS。安装完成后重新打开 PowerShell，再执行：

```powershell
node --version
npm --version
```

## 3. Clone 和安装依赖

```powershell
git clone <your-repo-url>
cd hk-home-intel
conda create -n py311 python=3.11 -y
conda run -n py311 python -m pip install --no-build-isolation -e ".[dev]"
npm install
Copy-Item .env.example .env
conda run -n py311 alembic upgrade head
```

如果你已经创建过 `py311`，可以跳过 `conda create -n py311 python=3.11 -y`。

## 4. PowerShell npm 执行策略

正常情况下可以直接执行：

```powershell
npm install
npm run dev:web
```

如果 PowerShell 报 `npm.ps1 cannot be loaded`，可以先用 `cmd /c` 绕过：

```powershell
cmd /c npm install
cmd /c npm run dev:web
```

也可以修改当前用户的 PowerShell execution policy：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

如果只是为了跑本项目，使用 `cmd /c npm ...` 通常就够了。

## 5. 环境变量和 SQLite 路径

默认 `.env.example` 已经适合本地 SQLite：

```bash
HHI_DATABASE_URL=sqlite:///./data/dev/hk_home_intel.db
```

这个相对路径要求你从仓库根目录运行 `hhi-api` 和 `hhi-worker`。

如果要改成 Windows 绝对路径，建议使用 forward slash：

```bash
HHI_DATABASE_URL=sqlite:///C:/Users/<you>/Projects/hk-home-intel/data/dev/hk_home_intel.db
```

不要写成普通反斜杠路径，避免 SQLite URL 解析不一致。

## 6. 启动服务

开一个 PowerShell 启动 API：

```powershell
conda run -n py311 hhi-api
```

另开一个 PowerShell 启动 Web：

```powershell
npm run dev:web
```

如果遇到 `npm.ps1` 问题：

```powershell
cmd /c npm run dev:web
```

默认地址：

- API: `http://127.0.0.1:8000`
- Web: `http://127.0.0.1:3000`

## 7. 健康检查

PowerShell 推荐：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/developments
```

浏览器也可以直接打开：

- `http://127.0.0.1:8000/api/v1/health`
- `http://127.0.0.1:3000`

## 8. 首轮数据导入

如果是空库，可以按这个顺序导入基础数据：

```powershell
conda run -n py311 hhi-worker import-srpe-index --lang en --limit 50 --offset 0
conda run -n py311 hhi-worker sync-launch-watch-config
conda run -n py311 hhi-worker sync-launch-watch-official --source landsd-all
conda run -n py311 hhi-worker sync-launch-watch-official --source srpe-recent-docs
conda run -n py311 hhi-worker discover-commercial-monitor-candidates --source centanet --limit 20 --validate --create-monitors
conda run -n py311 hhi-worker set-commercial-monitors-active --source centanet --auto-discovered
conda run -n py311 hhi-worker run-commercial-search-monitors --source centanet --limit-override 20
```

如果要补 Ricacorp：

```powershell
conda run -n py311 hhi-worker discover-commercial-monitor-candidates --source ricacorp --limit 20 --validate --create-monitors
conda run -n py311 hhi-worker set-commercial-monitors-active --source ricacorp --auto-discovered
conda run -n py311 hhi-worker run-commercial-search-monitors --source ricacorp --limit-override 20
```

如果要把更宽的一手官方观察池同步进来：

```powershell
conda run -n py311 hhi-worker sync-launch-watch-official --source srpe-active
```

## 9. 常见问题

- `npm` 找不到：先安装 Node.js `20+`，然后重新打开 PowerShell。
- `npm.ps1 cannot be loaded`：用 `cmd /c npm ...`，或设置 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`。
- API 能启动但读不到数据库：确认从仓库根目录运行，或把 `HHI_DATABASE_URL` 改成 Windows 绝对 SQLite URL。
- 官方/商业源抓取失败：确认 Windows 网络、代理和 TLS 正常；如果你设置了系统代理，默认 `HHI_HTTP_TRUST_ENV=true` 会继承环境代理。
