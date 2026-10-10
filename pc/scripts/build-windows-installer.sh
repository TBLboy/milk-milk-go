#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PC_DIR="$ROOT_DIR/pc"
BUILD_ROOT="$ROOT_DIR/.build/windows-installer"
PAYLOAD_DIR="$BUILD_ROOT/payload"
CONFIG_STAGE="$BUILD_ROOT/config"
TOOLS_DIR="$BUILD_ROOT/tools"
RELEASE_DIR="$ROOT_DIR/发布版本"

# Host platform: the Windows build differs from the Linux/WSL one in three ways
# (path separators inside installer.nsi, the NSIS script charset, and which Python
# performs the cross-platform wheel download).
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) IS_WINDOWS=1 ;;
  *)                    IS_WINDOWS=0 ;;
esac

if [[ "$IS_WINDOWS" -eq 1 && -z "${MILK_PYTHON:-}" ]]; then
  echo "On Windows, set MILK_PYTHON to a Python 3.11 interpreter that has pip, e.g." >&2
  echo "  MILK_PYTHON=\"$ROOT_DIR/.venv/Scripts/python.exe\"" >&2
  echo "(a uv-created venv has no pip by default; bootstrap it with -m ensurepip --upgrade)" >&2
  exit 1
fi

PYTHON_BIN="${MILK_PYTHON:-$HOME/miniforge3/envs/milk/bin/python}"
PYTHON_EMBED_URLS=(
  "https://mirrors.aliyun.com/python-release/windows/python-3.11.9-embed-amd64.zip"
  "https://mirrors.huaweicloud.com/python/3.11.9/python-3.11.9-embed-amd64.zip"
  "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
)
APP_VERSION="1.0.6"
OUTPUT_STAGE="$BUILD_ROOT/MilkWeigh-Windows-Setup.exe"
OUTPUT_RELEASE="$RELEASE_DIR/乍甸乳业辅料防错追溯系统-Windows-${APP_VERSION}-Setup.exe"
DEMO_MATERIAL_IMAGE_IDS=(
  "FILE-7f014209079f8bb72d1ffcc7"
  "FILE-de3e92b165b028854881aed2"
  "FILE-5e607996c8a06ceaca9ef951"
  "FILE-ca585337246d195956b87179"
  "FILE-92b5154561699d6f8e645d83"
  "FILE-734589df56298ab824901c0a"
  "FILE-45eeeef499a05d0f6927b4cc"
  "FILE-3a172e22eb7ab931e58104f0"
  "FILE-3b2fcd46ca0324c9fe2cd2cc"
  "FILE-1b859f40464b081cec1d9836"
)

mkdir -p "$BUILD_ROOT" "$PAYLOAD_DIR" "$CONFIG_STAGE" "$RELEASE_DIR"
rm -rf "$PAYLOAD_DIR" "$CONFIG_STAGE" "$TOOLS_DIR"
mkdir -p "$PAYLOAD_DIR" "$CONFIG_STAGE" "$TOOLS_DIR"

cd "$PC_DIR"
npm run build

if [[ ! -f "$PC_DIR/server/.env" ]]; then
  echo "缺少未跟踪的 pc/server/.env，无法注入 SMTP 和恢复密码配置。" >&2
  exit 1
fi

for key in MILK_ADMIN_RECOVERY_SECRET_HASH MILK_SMTP_USERNAME MILK_SMTP_PASSWORD; do
  if ! grep -q "^${key}=" "$PC_DIR/server/.env"; then
    echo "pc/server/.env 缺少 ${key}。" >&2
    exit 1
  fi
done

cp -a "$PC_DIR/dist" "$PAYLOAD_DIR/dist"
mkdir -p "$PAYLOAD_DIR/server"
cp -a "$PC_DIR/server/app" "$PAYLOAD_DIR/server/app"

# 授权核心：只交付编译产物（DEC-062 / TASK-159），绝不交付 milk_license 的 .py 源码。
# 编译产物由 Windows 构建机上的 pc/scripts/build-license-module.sh 生成。
LICENSE_MODULE_DIR="$ROOT_DIR/.build/license-module/milk_license"
if [[ ! -d "$LICENSE_MODULE_DIR" ]]; then
  echo "缺少授权模块编译产物：$LICENSE_MODULE_DIR" >&2
  echo "请先在 Windows 构建机执行 pc/scripts/build-license-module.sh，再打安装包。" >&2
  exit 1
fi
for source_file in "$LICENSE_MODULE_DIR"/*.py; do
  if [[ "$(basename "$source_file")" != "__init__.py" ]]; then
    echo "授权模块目录含源码文件：$source_file —— 拒绝把可读源码打进安装包。" >&2
    exit 1
  fi
done
if ! compgen -G "$LICENSE_MODULE_DIR/*.pyd" > /dev/null; then
  echo "授权模块目录没有 .pyd 编译产物：$LICENSE_MODULE_DIR" >&2
  exit 1
fi
mkdir -p "$PAYLOAD_DIR/server/milk_license"
cp "$LICENSE_MODULE_DIR/__init__.py" "$PAYLOAD_DIR/server/milk_license/__init__.py"
cp "$LICENSE_MODULE_DIR"/*.pyd "$PAYLOAD_DIR/server/milk_license/"

cp "$PC_DIR/server/seed.py" "$PAYLOAD_DIR/server/seed.py"
cp "$PC_DIR/server/restore_backup.py" "$PAYLOAD_DIR/server/restore_backup.py"
cp "$PC_DIR/packaging/windows/seed_install.py" "$PAYLOAD_DIR/server/seed_install.py"
cp "$PC_DIR/packaging/windows/MilkWeighService.py" "$PAYLOAD_DIR/server/MilkWeighService.py"
cp "$PC_DIR/packaging/windows/smtp_test.py" "$PAYLOAD_DIR/server/smtp_test.py"
cp "$PC_DIR/packaging/windows/restore_backup.ps1" "$PAYLOAD_DIR/server/restore_backup.ps1"
mkdir -p "$PAYLOAD_DIR/server/demo_assets/uploads"
for file_id in "${DEMO_MATERIAL_IMAGE_IDS[@]}"; do
  source_dir="$PC_DIR/data/uploads/${file_id:0:8}"
  mapfile -t matches < <(find "$source_dir" -maxdepth 1 -type f -name "${file_id}.*" -print)
  if [[ "${#matches[@]}" -ne 1 ]]; then
    echo "演示辅料图片缺失或重复：${file_id}" >&2
    exit 1
  fi
  target_dir="$PAYLOAD_DIR/server/demo_assets/uploads/${file_id:0:8}"
  mkdir -p "$target_dir"
  cp "${matches[0]}" "$target_dir/"
done
find "$PAYLOAD_DIR/server" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$PAYLOAD_DIR/server" -type f -name "*.pyc" -delete

mkdir -p "$PAYLOAD_DIR/python"
PYTHON_EMBED_DOWNLOADED=0
for url in "${PYTHON_EMBED_URLS[@]}"; do
  if curl -fL --retry 2 --retry-all-errors --connect-timeout 20 "$url" -o "$BUILD_ROOT/python-embed.zip"; then
    PYTHON_EMBED_DOWNLOADED=1
    break
  fi
done
if [[ "$PYTHON_EMBED_DOWNLOADED" -ne 1 ]]; then
  echo "无法下载 Windows Python 嵌入式运行时。" >&2
  exit 1
fi
unzip -q "$BUILD_ROOT/python-embed.zip" -d "$PAYLOAD_DIR/python"
cp "$PC_DIR/packaging/windows/python311._pth" "$PAYLOAD_DIR/python/python311._pth"

if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
  echo "pip is not available in $PYTHON_BIN" >&2
  echo "bootstrap it with: \"$PYTHON_BIN\" -m ensurepip --upgrade" >&2
  exit 1
fi

"$PYTHON_BIN" -m pip install \
  --target "$PAYLOAD_DIR/python/Lib/site-packages" \
  --platform win_amd64 \
  --python-version 3.11 \
  --implementation cp \
  --abi cp311 \
  --only-binary=:all: \
  --no-compile \
  --disable-pip-version-check \
  --upgrade \
  -r "$PC_DIR/server/requirements-installer.txt"

find "$PAYLOAD_DIR/python/Lib/site-packages" -maxdepth 2 -type d -name "bin" -prune -exec rm -rf {} +
find "$PAYLOAD_DIR/python/Lib/site-packages" -type d -name "__pycache__" -prune -exec rm -rf {} +

cp "$PAYLOAD_DIR/python/Lib/site-packages/pywin32_system32/pythoncom311.dll" "$PAYLOAD_DIR/python/"
cp "$PAYLOAD_DIR/python/Lib/site-packages/pywin32_system32/pywintypes311.dll" "$PAYLOAD_DIR/python/"
cp "$PAYLOAD_DIR/python/Lib/site-packages/win32/pythonservice.exe" "$PAYLOAD_DIR/python/"
cp "$PC_DIR/server/.env" "$CONFIG_STAGE/.env"
chmod 600 "$CONFIG_STAGE/.env"

cp "$PC_DIR/packaging/windows/app.ico" "$BUILD_ROOT/app.ico"

# makensis is a native binary: on Windows it needs Windows-style paths, the -DWIN
# switch (installer.nsi then uses "\" separators, which the Windows build of
# makensis requires), and -INPUTCHARSET UTF8 because installer.nsi is UTF-8 without
# a BOM and the Windows build defaults to the ANSI code page.
if [[ "$IS_WINDOWS" -eq 1 ]]; then
  MAKENSIS_ROOT="$(cygpath -w "$BUILD_ROOT")"
  MAKENSIS_OUT="$(cygpath -w "$OUTPUT_STAGE")"
  MAKENSIS_ICON="$(cygpath -w "$BUILD_ROOT/app.ico")"
  MAKENSIS_SCRIPT="$(cygpath -w "$PC_DIR/packaging/windows/installer.nsi")"
  MAKENSIS_PLATFORM="-DWIN"
else
  MAKENSIS_ROOT="$BUILD_ROOT"
  MAKENSIS_OUT="$OUTPUT_STAGE"
  MAKENSIS_ICON="$BUILD_ROOT/app.ico"
  MAKENSIS_SCRIPT="$PC_DIR/packaging/windows/installer.nsi"
  MAKENSIS_PLATFORM=""
fi

MAKENSIS_BIN="$(command -v makensis || true)"
if [[ -z "$MAKENSIS_BIN" ]]; then
  if [[ "$IS_WINDOWS" -eq 1 ]]; then
    echo "makensis not found on PATH. Install NSIS for Windows and add its Bin directory to PATH." >&2
    exit 1
  fi
  (
    cd "$TOOLS_DIR"
    apt-get download nsis nsis-common
  )
  NSIS_ROOT="$TOOLS_DIR/nsis-root"
  mkdir -p "$NSIS_ROOT"
  dpkg-deb -x "$TOOLS_DIR"/nsis_*.deb "$NSIS_ROOT"
  dpkg-deb -x "$TOOLS_DIR"/nsis-common_*.deb "$NSIS_ROOT"
  MAKENSIS_BIN="$NSIS_ROOT/usr/bin/makensis"
  export NSISDIR="$NSIS_ROOT/usr/share/nsis"
fi

# shellcheck disable=SC2086  # MAKENSIS_PLATFORM is intentionally word-split (may be empty)
"$MAKENSIS_BIN" \
  -INPUTCHARSET UTF8 \
  $MAKENSIS_PLATFORM \
  -DROOT_DIR="$MAKENSIS_ROOT" \
  -DOUT_FILE="$MAKENSIS_OUT" \
  -DAPP_ICON="$MAKENSIS_ICON" \
  -DAPP_VERSION="$APP_VERSION" \
  "$MAKENSIS_SCRIPT"

cp "$OUTPUT_STAGE" "$OUTPUT_RELEASE"
chmod 755 "$OUTPUT_RELEASE"
sha256sum "$OUTPUT_RELEASE" > "$OUTPUT_RELEASE.sha256"
echo "Windows installer created: $OUTPUT_RELEASE"
