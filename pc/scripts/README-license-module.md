# milk_license 原生模块构建与安装器集成（TASK-159 / DEC-062）

本目录的 `build-license-module.sh` 把 `pc/server/milk_license` 的每个子模块用
**Nuitka** 编译成 Windows 原生扩展（`.pyd`），使交付物不再包含可读的授权校验
源码。构建脚本只涉及编译，不修改 `milk_license` 的业务逻辑。

## 1. 构建（必须在 Windows 上运行）

Windows 的 `.pyd` 无法从 Linux/WSL 交叉编译，因此本步骤在开发机 Windows 上完成。

```bash
# 在 Git Bash / MSYS2 / Cygwin 中
bash pc/scripts/build-license-module.sh
```

脚本会：

1. 使用仓库内 `.venv` 的 Python 3.11（可用 `MILK_PYTHON` 覆盖）；
2. 确保安装固定版本 `nuitka==4.2.2`（用 `uv pip install`，可用 `MILK_UV` 指定 uv）；
3. 把源码复制到纯 ASCII 临时目录（项目路径含中文，避免编译器处理中文路径失败）；
4. 逐个模块执行（完整命令，逐字）：

   ```bash
   python -m nuitka \
     --mode=module \
     --no-pyi-file \
     --remove-output \
     --assume-yes-for-downloads \
     --output-dir=<ASCII工作目录>/out \
     <module>.py
   ```

   模块清单：`ed25519 codec keys store state service policy guard`
   （`__init__.py` 不编译，作为包标记保留，仅含 docstring，无逻辑）；

5. 把产物汇总到 `<repo>/.build/license-module/milk_license/`；
6. 生成 `MANIFEST.txt`（sha256 + 字节数）；
7. 自检：在 `pc/server` 的干净副本中把子模块源码改名为 `.py.bak`，
   只留 `__init__.py` + `.pyd`，然后执行
   `python -c "from milk_license import codec, state, policy, service, guard, keys, store; print('ok')"`
   与 `pytest tests/test_license_ed25519.py tests/test_license_state.py`
   （应为 **54 passed**）。

### 产物（默认位置 `<repo>/.build/license-module/milk_license/`）

| 文件 | 说明 |
|---|---|
| `__init__.py` | 包标记（仅 docstring） |
| `ed25519.cp311-win_amd64.pyd` | 纯 Python Ed25519 验签 |
| `codec.cp311-win_amd64.pyd` | 授权串编解码 |
| `keys.cp311-win_amd64.pyd` | 内置公钥 |
| `store.cp311-win_amd64.pyd` | 多副本状态存储 |
| `state.cp311-win_amd64.pyd` | 授权状态判定 |
| `service.cp311-win_amd64.pyd` | LicenseService |
| `policy.cp311-win_amd64.pyd` | 访问策略清单 |
| `guard.cp311-win_amd64.pyd` | ASGI 守卫中间件 |

`.build/` 已被根 `.gitignore` 忽略，产物不会进入源码仓库。

### 编译器与 ABI

- 参考机器上 Nuitka 自动检测到 **MSVC `cl 14.3`**（VS 2022 BuildTools）并使用它；
  本机未安装 MSVC 时，`--assume-yes-for-downloads` 允许 Nuitka 自动下载 winlibs GCC。
- 产物是 **cp311-win_amd64** 扩展，与安装器使用的嵌入式 Python
  `python-3.11.9-embed-amd64` 的 ABI 兼容（同一 CPython 3.11 小版本系列）。
- 注意：Nuitka 产物**不是逐字节可复现**（内嵌构建时间等元数据），重复构建的
  sha256 可能不同；固定 Nuitka 版本保证的是同一工具链与可用性，而非相同哈希。

## 2. 安装器 payload 集成

当前 `pc/scripts/build-windows-installer.sh` 只复制了 `pc/server/app` 等，
**没有**复制 `milk_license`（交付时 `app` 会 `import milk_license`）。集成方式：
用本目录产出的编译包替换源码包，即只复制 `__init__.py` + `*.pyd`，**不要**复制
`pc/server/milk_license/*.py` 子模块。

建议在 `build-windows-installer.sh` 中 `cp -a "$PC_DIR/server/app" ...` 附近加入：

```bash
# 授权模块：使用预编译 .pyd（TASK-159 / DEC-062），不复制可读源码
LICENSE_BUILD_DIR="$ROOT_DIR/.build/license-module/milk_license"
if [[ ! -d "$LICENSE_BUILD_DIR" ]]; then
  echo "缺少 milk_license 编译产物；请先在 Windows 上运行 pc/scripts/build-license-module.sh" >&2
  exit 1
fi
mkdir -p "$PAYLOAD_DIR/server/milk_license"
cp "$LICENSE_BUILD_DIR/__init__.py" "$PAYLOAD_DIR/server/milk_license/"
cp "$LICENSE_BUILD_DIR"/*.pyd "$PAYLOAD_DIR/server/milk_license/"
```

说明：

- 不要复制 `pc/server/milk_license/*.py`（`__init__.py` 除外），否则可读源码会进交付物；
- 现有的 `find "$PAYLOAD_DIR/server" ... __pycache__` 清理逻辑可继续保留；
- `app/license_runtime.py` 的 `from milk_license.guard import install` /
  `from milk_license.service import LicenseService` / `from milk_license.store import ...`
  在运行时由 `.pyd` 提供，无需改动 app。

## 3. 待验证项（本机无法验证，需在开发方 Linux/WSL + Windows 上完成）

以下均**未在本机验证**，需在完整打包环境确认：

1. **Linux/WSL 完整安装器打包**：在 WSL/Linux 上运行 `build-windows-installer.sh`，
   确认 payload 中 `server/milk_license/` 只含 `__init__.py` + `*.pyd`，
   且无 `milk_license/*.py` 子模块、无 `__pycache__`/`.pyc`。
2. **安装后运行**：在 Windows 目标机安装后启动服务，确认进程能
   `import milk_license`，`/api/v1/license/status` 正常，输入解锁码可解锁，
   受限模式下守卫中间件按策略拦截。
3. **ABI 兼容**：确认嵌入式 Python 3.11.9 能加载 cp311-win_amd64 的 `.pyd`。
4. **隐藏效果**：确认安装目录中不存在可读的授权校验源码
   （仅 `__init__.py` 的 docstring）。
