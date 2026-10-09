#!/usr/bin/env bash
# build-license-module.sh —— 将 pc/server/milk_license 编译为原生扩展（Windows .pyd）
#
# 目的（TASK-159 / DEC-062）：
#   交付物不再包含可读的授权校验源码。把 milk_license 的每个子模块用 Nuitka
#   编译成独立的扩展模块（.pyd），源码 .py 在打包时被替换掉。
#
# 产物（默认）：<repo>/.build/license-module/milk_license/
#   __init__.py                     （保留的包标记，仅 docstring，无逻辑）
#   ed25519.cp311-win_amd64.pyd
#   codec.cp311-win_amd64.pyd
#   keys.cp311-win_amd64.pyd
#   store.cp311-win_amd64.pyd
#   state.cp311-win_amd64.pyd
#   service.cp311-win_amd64.pyd
#   policy.cp311-win_amd64.pyd
#   guard.cp311-win_amd64.pyd
#   MANIFEST.txt                    （文件大小 + sha256，便于复核）
#
# 平台：必须在 Windows（Git Bash / MSYS2 / Cygwin）上运行。
#   Windows 的 .pyd 无法从 Linux/WSL 交叉编译；Linux 侧只负责把这里产出的
#   预编译产物塞进安装器 payload（见 README-license-module.md）。
#
# 可覆盖的环境变量：
#   MILK_PYTHON                    指定 Python 解释器（默认 <repo>/.venv/Scripts/python.exe）
#   MILK_UV                        指定 uv 可执行文件（默认从 PATH 查找 uv）
#   MILK_LICENSE_BUILD_WORKDIR     指定纯 ASCII 编译工作目录
#   MILK_LICENSE_SKIP_VERIFY=1     跳过构建后的自检（import + 全部授权测试）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SERVER_DIR="$ROOT_DIR/pc/server"
SRC_PKG="$SERVER_DIR/milk_license"
OUT_DIR="$ROOT_DIR/.build/license-module"

# 固定版本：任何人重复构建都得到同一 Nuitka。
NUITKA_VERSION="4.2.2"

# 子模块清单（不含 __init__.py，它在交付物中保留为普通 .py 包标记）。
MODULES=(ed25519 codec keys store state service policy guard)

# ── 平台检查 ───────────────────────────────────────────────────
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) ;;
  *)
    echo "错误：本脚本只能在 Windows(Git Bash/MSYS2/Cygwin) 上运行以产出 Windows .pyd。" >&2
    echo "      Windows 扩展模块无法从 Linux/WSL 交叉编译；请在开发机 Windows 上运行，" >&2
    echo "      再由 Linux/WSL 的安装器打包脚本消费 .build/license-module/ 的产物。" >&2
    exit 1
    ;;
esac

# ── 定位 Python ────────────────────────────────────────────────
if [[ -n "${MILK_PYTHON:-}" ]]; then
  PYTHON="$MILK_PYTHON"
elif [[ -f "$ROOT_DIR/.venv/Scripts/python.exe" ]]; then
  PYTHON="$ROOT_DIR/.venv/Scripts/python.exe"
elif [[ -f "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/.venv/bin/python"
elif command -v python >/dev/null 2>&1; then
  PYTHON="$(command -v python)"
else
  echo "错误：找不到 Python。请设置 MILK_PYTHON 指向 Python 3.11 解释器。" >&2
  exit 1
fi

echo "==> Python: $PYTHON"
"$PYTHON" -c 'import sys; print("    version:", sys.version.split()[0])'

if [[ ! -d "$SRC_PKG" ]]; then
  echo "错误：找不到源包 $SRC_PKG" >&2
  exit 1
fi

# ── 确保固定版本 Nuitka ────────────────────────────────────────
installed_version="$("$PYTHON" -c 'import nuitka; print(nuitka.__version__)' 2>/dev/null || true)"
if [[ "$installed_version" != "$NUITKA_VERSION" ]]; then
  echo "==> 安装 nuitka==$NUITKA_VERSION（当前：${installed_version:-未安装}）"
  UV_BIN="${MILK_UV:-$(command -v uv || true)}"
  if [[ -n "$UV_BIN" ]]; then
    "$UV_BIN" pip install --python "$PYTHON" "nuitka==$NUITKA_VERSION"
  else
    "$PYTHON" -m pip install "nuitka==$NUITKA_VERSION"
  fi
else
  echo "==> 已安装 nuitka==$NUITKA_VERSION"
fi

# ── 纯 ASCII 编译工作目录 ──────────────────────────────────────
# 项目路径含中文；编译器/Nuitka 处理中文路径可能失败，因此把源码复制到
# ASCII 临时目录后再编译（见 TASK-159 环境说明）。
if [[ -n "${MILK_LICENSE_BUILD_WORKDIR:-}" ]]; then
  WORK_ROOT="$MILK_LICENSE_BUILD_WORKDIR"
else
  TMP_WIN="$("$PYTHON" -c 'import tempfile; print(tempfile.gettempdir())')"
  if command -v cygpath >/dev/null 2>&1; then
    TMP_UNIX="$(cygpath -u "$TMP_WIN")"
  else
    TMP_UNIX="$TMP_WIN"
  fi
  WORK_ROOT="$TMP_UNIX/milk-license-build"
fi

echo "==> 编译工作目录: $WORK_ROOT"
rm -rf "$WORK_ROOT"
mkdir -p "$WORK_ROOT/src/milk_license" "$WORK_ROOT/out"
cp "$SRC_PKG"/*.py "$WORK_ROOT/src/milk_license/"

# ── 逐个编译子模块 ─────────────────────────────────────────────
# --mode=module            单模块 → 扩展模块
# --no-pyi-file            不生成 .pyi 桩文件
# --remove-output          编译后清理中间 build 目录
# --assume-yes-for-downloads  允许 Nuitka 自动下载编译器（若本机无 MSVC/gcc）
cd "$WORK_ROOT/src/milk_license"
for mod in "${MODULES[@]}"; do
  echo "==> 编译 $mod.py"
  "$PYTHON" -m nuitka \
    --mode=module \
    --no-pyi-file \
    --remove-output \
    --assume-yes-for-downloads \
    --output-dir="$WORK_ROOT/out" \
    "$mod.py"
done

# ── 汇总产物 ───────────────────────────────────────────────────
echo "==> 汇总产物到 $OUT_DIR"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR/milk_license"
cp "$SRC_PKG/__init__.py" "$OUT_DIR/milk_license/__init__.py"
cp "$WORK_ROOT/out"/*.pyd "$OUT_DIR/milk_license/"

# 校验：每个子模块都必须有对应 .pyd
for mod in "${MODULES[@]}"; do
  if ! compgen -G "$OUT_DIR/milk_license/$mod*.pyd" > /dev/null; then
    echo "错误：缺少 $mod 的 .pyd 产物" >&2
    exit 1
  fi
done

# ── 清单 ───────────────────────────────────────────────────────
MANIFEST="$OUT_DIR/MANIFEST.txt"
{
  echo "# milk_license 编译产物清单"
  echo "# nuitka==$NUITKA_VERSION  python=$("$PYTHON" -c 'import sys;print(sys.version.split()[0])')"
  echo "# 生成时间(UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# 格式: sha256  size_bytes  filename"
  (cd "$OUT_DIR/milk_license" && sha256sum ./* | while read -r sum name; do
     name="${name#\*}"   # Git Bash 的 sha256sum 会以 '*' 前缀标记二进制文件
     size="$(wc -c < "$name" | tr -d ' ')"
     printf '%s  %s  %s\n' "$sum" "$size" "${name#./}"
   done)
} > "$MANIFEST"
echo "==> 清单: $MANIFEST"
cat "$MANIFEST"

# ── 自检：移除源码后 import + 全部授权测试必须通过 ────────────────
if [[ "${MILK_LICENSE_SKIP_VERIFY:-0}" == "1" ]]; then
  echo "==> MILK_LICENSE_SKIP_VERIFY=1，跳过自检"
  exit 0
fi

echo "==> 自检：在干净副本中移除 milk_license 源码后运行"
VERIFY_DIR="$WORK_ROOT/verify-server"
rm -rf "$VERIFY_DIR"
mkdir -p "$VERIFY_DIR"
# 复制 pc/server 的最小必要内容（tests + pyproject），并放入编译产物包。
cp -a "$SERVER_DIR/tests" "$VERIFY_DIR/tests"
cp "$SERVER_DIR/pyproject.toml" "$VERIFY_DIR/pyproject.toml"
mkdir -p "$VERIFY_DIR/milk_license"
cp "$SRC_PKG"/*.py "$VERIFY_DIR/milk_license/"
# 把子模块源码改名为 .bak（等价于移除），只保留 __init__.py + .pyd
for mod in "${MODULES[@]}"; do
  mv "$VERIFY_DIR/milk_license/$mod.py" "$VERIFY_DIR/milk_license/$mod.py.bak"
done
cp "$OUT_DIR/milk_license"/*.pyd "$VERIFY_DIR/milk_license/"
find "$VERIFY_DIR" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true

echo "--- 干净目录内容 ---"
ls -la "$VERIFY_DIR/milk_license"

echo "--- import 自检 ---"
(cd "$VERIFY_DIR" && "$PYTHON" -c "from milk_license import codec, state, policy, service, guard, keys, store; print('ok')")

echo "--- pytest 自检（应全部通过）---"
# 不加 -q：pyproject 已配置 addopts=-q，单次 -q 会保留 "N passed" 汇总行。
(cd "$VERIFY_DIR" && "$PYTHON" -m pytest tests/test_license_ed25519.py tests/test_license_state.py)

echo "==> 完成：产物位于 $OUT_DIR/milk_license"
