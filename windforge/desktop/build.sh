#!/usr/bin/env bash
#
# WindForge Desktop Build Script
# Builds everything and produces a macOS .dmg
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
DESKTOP_DIR="$SCRIPT_DIR"
WEB_DIR="$ROOT_DIR/apps/web"
API_DIR="$ROOT_DIR/apps/api"
RESOURCES_DIR="$DESKTOP_DIR/resources"

echo "=== WindForge Desktop Build ==="
echo "Root:      $ROOT_DIR"
echo "Desktop:   $DESKTOP_DIR"
echo ""

# ─── Step 1: Build React frontend ──────────────────────────────────────────
echo ">>> Step 1: Building React frontend..."
cd "$WEB_DIR"
npm ci --silent
npm run build
echo "    Frontend built → $WEB_DIR/dist/"

# ─── Step 2: Bundle Python backend with PyInstaller ────────────────────────
echo ">>> Step 2: Building Python backend with PyInstaller..."
cd "$API_DIR"
pip install pyinstaller --quiet
pip install -e . --quiet
pyinstaller \
  --onefile \
  --name windforge-api \
  --hidden-import aiosqlite \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols \
  --hidden-import uvicorn.protocols.http \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan \
  --hidden-import uvicorn.lifespan.on \
  --hidden-import uvicorn.lifespan.off \
  --distpath "$RESOURCES_DIR/python" \
  app/run.py
echo "    Backend built → $RESOURCES_DIR/python/windforge-api"

# ─── Step 3: Copy simulation binaries ──────────────────────────────────────
echo ">>> Step 3: Copying simulation binaries..."
mkdir -p "$RESOURCES_DIR/bin"

# OpenFAST
OPENFAST_SRC="/opt/anaconda3/bin/openfast"
if [ -f "$OPENFAST_SRC" ]; then
  cp "$OPENFAST_SRC" "$RESOURCES_DIR/bin/"
  echo "    Copied openfast"
else
  echo "    WARNING: openfast not found at $OPENFAST_SRC"
fi

# TurbSim
TURBSIM_SRC="/opt/anaconda3/bin/turbsim"
if [ -f "$TURBSIM_SRC" ]; then
  cp "$TURBSIM_SRC" "$RESOURCES_DIR/bin/"
  echo "    Copied turbsim"
else
  echo "    WARNING: turbsim not found at $TURBSIM_SRC"
fi

# ROSCO DLL
ROSCO_SRC="/Users/vikram/2026_aldott_website/server/rosco_full/rosco/lib/libdiscon.dylib"
if [ -f "$ROSCO_SRC" ]; then
  cp "$ROSCO_SRC" "$RESOURCES_DIR/bin/"
  echo "    Copied libdiscon.dylib"
else
  echo "    WARNING: libdiscon.dylib not found at $ROSCO_SRC"
fi

# ─── Step 4: Strip macOS quarantine and set permissions ────────────────────
echo ">>> Step 4: Stripping quarantine attributes..."
xattr -cr "$RESOURCES_DIR/bin/" 2>/dev/null || true
chmod +x "$RESOURCES_DIR/bin/"* 2>/dev/null || true
chmod +x "$RESOURCES_DIR/python/windforge-api" 2>/dev/null || true
echo "    Done"

# ─── Step 5: Copy frontend build ──────────────────────────────────────────
echo ">>> Step 5: Copying frontend build..."
mkdir -p "$RESOURCES_DIR/app/dist"
cp -R "$WEB_DIR/dist/"* "$RESOURCES_DIR/app/dist/"
echo "    Frontend copied → $RESOURCES_DIR/app/dist/"

# ─── Step 6: Install Electron dependencies ─────────────────────────────────
echo ">>> Step 6: Installing Electron dependencies..."
cd "$DESKTOP_DIR"
npm ci --silent
echo "    Done"

# ─── Step 7: Build Electron app ───────────────────────────────────────────
echo ">>> Step 7: Building Electron .dmg..."
cd "$DESKTOP_DIR"
npx electron-builder --mac
echo "    Build complete!"

echo ""
echo "=== Build Output ==="
ls -lh "$DESKTOP_DIR/dist/"*.dmg 2>/dev/null || echo "    No .dmg found (check for errors above)"
echo ""
echo "Done! 🎉"
