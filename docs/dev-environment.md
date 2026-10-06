# 开发环境复现（PC 端）

> 目的：在一台新的 Windows 机器上，用 **uv** 复现 `milk-milk-go/pc` 的开发环境并运行起来。
> 本文档已验证可复现（2026-10-06）。

## 0. 环境基线（本机已验证）

| 项 | 值 |
|---|---|
| uv | `0.11.30` |
| Python | **CPython 3.11.15**（由 uv 管理，无需系统预装，也**不需要 conda**） |
| Node / npm | `v24.12.0` / `11.6.2`（前端） |
| 后端依赖 | 见 `pc/server/requirements.lock`（锁定 38 个包） |
| 后端端口 | **8011** |
| 默认管理员 | `admin` / `admin123`（首次登录强制改密） |
| 数据库 | `pc/data/milk_weigh.sqlite3`（首次运行自动创建） |

## 1. 前置条件

- Windows 10/11
- 安装 **uv**（二选一）：
  ```powershell
  winget install --id astral-sh.uv
  # 或
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- 安装 **Node.js**（≥ 18，建议 LTS）用于前端
- 无需 conda；无需手动安装 Python（uv 会自动下载 3.11）

## 2. 创建 Python 环境

在**仓库根目录**（`milk-milk-go/`）执行：

```powershell
cd milk-milk-go
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe -r pc\server\requirements.lock
```

> - **复现请用 `requirements.lock`**（版本已锁定）；`requirements.txt` 只声明版本区间，会解析到当时最新版，可能导致行为漂移。
> - 环境创建在仓库内 `.venv/`，已在 `.gitignore` 中忽略。

## 3. 初始化数据库与演示数据

```powershell
cd pc\server
..\..\.venv\Scripts\python.exe seed.py
```

输出示例：`14 materials, 6 recipes, ... 10 material images`。
演示图片素材位于 `pc/data/uploads`。

## 4. 运行后端

```powershell
cd pc\server
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8011 --reload
```

浏览器打开 <http://127.0.0.1:8011/> ，用 `admin` / `admin123` 登录。

## 5. 前端（React + Vite，位于 `pc/`）

构建产物 `pc/dist/` 已被 `.gitignore` 忽略，**新克隆的仓库里没有它**，需要先构建。

### 5.1 让后端 8011 直接提供界面（日常使用 / 验收）

```powershell
cd pc
npm install
npm run build
```

`npm run build` 会生成 `pc/dist/`，后端启动时会自动托管该目录（见 `app/main.py` 的 `frontend_dir`）。

构建后访问 <http://127.0.0.1:8011/> 即能看到界面。
**若未构建**，根路径只会返回 JSON（`{"service": "...", "version": "..."}`），这不是故障。

### 5.2 前端开发模式（改前端源码时用，带热更新）

```powershell
cd pc
npm install
npm run dev
```

访问 <http://127.0.0.1:5173/>（`/api` 已代理到 `127.0.0.1:8011`）。

改动源码后若想在 8011 上看到效果，需要重新执行 `npm run build`。

## 6. 端口 8011 冲突处理

若本机安装过正式版，Windows 服务 **`MilkWeighBackend`**（默认开机自启）会占用 8011，开发版将无法启动。

```powershell
# 需要管理员权限
Stop-Service MilkWeighBackend -Force
Set-Service MilkWeighBackend -StartupType Disabled

# 需要恢复正式版时：
Set-Service MilkWeighBackend -StartupType Automatic
Start-Service MilkWeighBackend
```

## 7. 运行测试

```powershell
cd pc\server
..\..\.venv\Scripts\python.exe -m pytest
```

## 8. 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| `python` 是 Python 2.7 | 系统默认 python 指向 conda base；**必须**用 `.venv\Scripts\python.exe` |
| 端口被占用 (`Errno 10048`) | 正式版服务占着 8011，见第 6 节 |
| 打开 8011 只看到 JSON，没有界面 | `pc/dist/` 不存在（被 gitignore）。执行 `cd pc; npm install; npm run build`，见第 5.1 节 |
| 依赖要升级/更新 | 重新解析锁：`uv pip compile pc/server/requirements.txt --python-version 3.11 -o pc/server/requirements.lock`，再 `uv pip install --python .venv\Scripts\python.exe -r pc/server/requirements.lock` |
| 移动/删除 `*.sqlite3` 报 `WinError 32 文件被占用` | Windows 不允许替换仍被打开的文件。未显式关闭的 SQLite 连接（`with sqlite3.connect(...)` 只提交事务、不关闭连接）会一直持有句柄；请改用 `with closing(sqlite3.connect(...))`。服务端在原地替换数据库文件（恢复备份）前必须先释放连接池，见 `app/db/session.py` 的 `release_database_handles()`。 |

## 9. 参考

- 后端接口文档：运行后访问 <http://127.0.0.1:8011/docs>
- 后端说明：`pc/server/README.md`
