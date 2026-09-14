#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PC_DIR="$ROOT_DIR/pc"
BUILD_ROOT="$ROOT_DIR/.build/windows-installer"
PAYLOAD_DIR="$BUILD_ROOT/payload"
CONFIG_STAGE="$BUILD_ROOT/config"
TOOLS_DIR="$BUILD_ROOT/tools"
RELEASE_DIR="$ROOT_DIR/发布版本"
PYTHON_BIN="${MILK_PYTHON:-$HOME/miniforge3/envs/milk/bin/python}"
PYTHON_EMBED_URLS=(
  "https://mirrors.aliyun.com/python-release/windows/python-3.11.9-embed-amd64.zip"
  "https://mirrors.huaweicloud.com/python/3.11.9/python-3.11.9-embed-amd64.zip"
  "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
)
APP_VERSION="1.0.4"
OUTPUT_STAGE="$BUILD_ROOT/MilkWeigh-Windows-Setup.exe"
OUTPUT_RELEASE="$RELEASE_DIR/牧衡辅料称重防错系统-Windows-${APP_VERSION}-Setup.exe"

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
cp "$PC_DIR/server/seed.py" "$PAYLOAD_DIR/server/seed.py"
cp "$PC_DIR/server/restore_backup.py" "$PAYLOAD_DIR/server/restore_backup.py"
cp "$PC_DIR/packaging/windows/seed_install.py" "$PAYLOAD_DIR/server/seed_install.py"
cp "$PC_DIR/packaging/windows/MilkWeighService.py" "$PAYLOAD_DIR/server/MilkWeighService.py"
cp "$PC_DIR/packaging/windows/smtp_test.py" "$PAYLOAD_DIR/server/smtp_test.py"
cp "$PC_DIR/packaging/windows/restore_backup.ps1" "$PAYLOAD_DIR/server/restore_backup.ps1"
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

MAKENSIS_BIN="$(command -v makensis || true)"
if [[ -z "$MAKENSIS_BIN" ]]; then
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

"$MAKENSIS_BIN" \
  -DROOT_DIR="$BUILD_ROOT" \
  -DOUT_FILE="$OUTPUT_STAGE" \
  -DAPP_ICON="$BUILD_ROOT/app.ico" \
  -DAPP_VERSION="$APP_VERSION" \
  "$PC_DIR/packaging/windows/installer.nsi"

cp "$OUTPUT_STAGE" "$OUTPUT_RELEASE"
chmod 755 "$OUTPUT_RELEASE"
sha256sum "$OUTPUT_RELEASE" > "$OUTPUT_RELEASE.sha256"
echo "Windows installer created: $OUTPUT_RELEASE"
