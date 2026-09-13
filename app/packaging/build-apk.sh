#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_DIR="$ROOT_DIR/app"
RELEASE_DIR="$ROOT_DIR/发布版本"
BUILD_ROOT="$ROOT_DIR/.build/android-apk"
SIGNING_DIR="${MILK_APP_SIGNING_DIR:-$HOME/.milkweigh-build}"
KEYSTORE="${MILK_APP_KEYSTORE:-$SIGNING_DIR/milkweigh-release.jks}"
SIGNING_PROPERTIES="$SIGNING_DIR/signing.properties"
JAVA_HOME="${JAVA_HOME:-/home/tbl/android-studio/jbr}"
ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"
APP_VERSION="1.0.1"
APK_NAME="牧衡辅料称重防错系统-Android-${APP_VERSION}.apk"

if [[ ! -x "$JAVA_HOME/bin/java" ]]; then
  echo "未找到 JDK 17+：$JAVA_HOME" >&2
  exit 1
fi

if [[ ! -d "$ANDROID_HOME/platforms/android-35" ]]; then
  echo "未找到 Android SDK Platform 35：$ANDROID_HOME" >&2
  exit 1
fi

mkdir -p "$BUILD_ROOT" "$RELEASE_DIR" "$SIGNING_DIR"
chmod 700 "$SIGNING_DIR"

if [[ ! -f "$KEYSTORE" ]]; then
  STORE_PASSWORD="$(openssl rand -base64 36 | tr -d '/+=' | cut -c1-32)"
  KEY_PASSWORD="$STORE_PASSWORD"
  "$JAVA_HOME/bin/keytool" -genkeypair \
    -keystore "$KEYSTORE" \
    -storepass "$STORE_PASSWORD" \
    -keypass "$KEY_PASSWORD" \
    -alias milkweigh \
    -keyalg RSA \
    -keysize 4096 \
    -validity 3650 \
    -dname "CN=MilkWeigh, OU=Deployment, O=Muheng, L=Unknown, ST=Unknown, C=CN"
  printf 'storePassword=%s\nkeyPassword=%s\nalias=milkweigh\nstoreFile=%s\n' \
    "$STORE_PASSWORD" "$KEY_PASSWORD" "$KEYSTORE" > "$SIGNING_PROPERTIES"
  chmod 600 "$SIGNING_PROPERTIES" "$KEYSTORE"
fi

STORE_PASSWORD="$(sed -n 's/^storePassword=//p' "$SIGNING_PROPERTIES")"
KEY_PASSWORD="$(sed -n 's/^keyPassword=//p' "$SIGNING_PROPERTIES")"
KEY_ALIAS="$(sed -n 's/^alias=//p' "$SIGNING_PROPERTIES")"

if [[ -z "$STORE_PASSWORD" || -z "$KEY_PASSWORD" || -z "$KEY_ALIAS" ]]; then
  echo "发布签名配置不完整：$SIGNING_PROPERTIES" >&2
  exit 1
fi

cd "$APP_DIR"
JAVA_HOME="$JAVA_HOME" ANDROID_HOME="$ANDROID_HOME" ./gradlew clean assembleRelease \
  -x lintVitalAnalyzeRelease \
  -x lintVitalReportRelease \
  -x lintVitalRelease \
  --no-daemon

UNSIGNED_APK="$APP_DIR/app/build/outputs/apk/release/app-release-unsigned.apk"
if [[ ! -f "$UNSIGNED_APK" ]]; then
  echo "未找到 release APK：$UNSIGNED_APK" >&2
  exit 1
fi

ZIPALIGN="$ANDROID_HOME/build-tools/34.0.0/zipalign"
APKSIGNER="$ANDROID_HOME/build-tools/34.0.0/apksigner"
ALIGNED_APK="$BUILD_ROOT/app-release-aligned.apk"
SIGNED_APK="$BUILD_ROOT/$APK_NAME"

"$ZIPALIGN" -f 4 "$UNSIGNED_APK" "$ALIGNED_APK"
JAVA_HOME="$JAVA_HOME" "$APKSIGNER" sign \
  --ks "$KEYSTORE" \
  --ks-key-alias "$KEY_ALIAS" \
  --ks-pass "pass:$STORE_PASSWORD" \
  --key-pass "pass:$KEY_PASSWORD" \
  --out "$SIGNED_APK" \
  "$ALIGNED_APK"

JAVA_HOME="$JAVA_HOME" "$APKSIGNER" verify --verbose "$SIGNED_APK"
cp "$SIGNED_APK" "$RELEASE_DIR/$APK_NAME"
chmod 644 "$RELEASE_DIR/$APK_NAME"
sha256sum "$RELEASE_DIR/$APK_NAME" > "$RELEASE_DIR/$APK_NAME.sha256"
echo "Android APK created: $RELEASE_DIR/$APK_NAME"
