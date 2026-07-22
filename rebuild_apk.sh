#!/usr/bin/env bash
# 三一 APK 一键重打包脚本
# 用法: bash rebuild_apk.sh
set -e

cd "$(dirname "$0")/frontend"

export JAVA_HOME="C:/Program Files/Microsoft/jdk-21.0.11.10-hotspot"
export ANDROID_HOME="D:/Android"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$PATH"

echo "📦 1/3  构建 Vue 前端..."
npm run build

echo ""
echo "🔄 2/3  同步到 Capacitor..."
npx cap sync android

echo ""
echo "🤖 3/3  编译 APK..."
cd android
./gradlew assembleDebug 2>&1 | tail -3

echo ""
APK="app/build/outputs/apk/debug/app-debug.apk"
# 复制到桌面，带日期戳
DESKTOP="/c/Users/24368/Desktop"
NAME="三一_$(date +%Y%m%d_%H%M).apk"
cp "$APK" "$DESKTOP/$NAME"
echo "✅ 完成！"
ls -lh "$DESKTOP/$NAME"
echo ""
echo "📱 桌面文件: $DESKTOP/$NAME"
