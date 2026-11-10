#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ConvertCAD — build the macOS application (on a Mac, Apple Silicon or Intel:
# the build is for the architecture of the Mac it runs on).
#
#   ./scripts/build_macos.sh   ->  dist/ConvertCAD.app
#                                  dist/ConvertCAD-<version>-macos-<arch>.dmg
#                                  dist/ConvertCAD-<version>-macos-<arch>.zip
#
# The .dmg opens a window with ConvertCAD.app and a link to Applications
# (drag and drop to install). The .zip holds the same application.
# The console tool is inside the app:
#     /Applications/ConvertCAD.app/Contents/MacOS/ConvertCAD-cli
#
# Included automatically: GNU LibreDWG (DWG output, built here the first
# time, about 5 minutes), RapidOCR and its built-in OCR model.
#
# The app is signed "ad hoc" (no Apple Developer ID, not notarized): the
# first time, macOS asks to confirm. Right-click ConvertCAD.app > Open, or
# System Settings > Privacy & Security > Open Anyway.
#
# Needs: python3 (3.10+), Xcode command line tools (xcode-select --install).
# Skip the tests with CONVERTCAD_NO_TESTS=1.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
ARCH="$(uname -m)"                       # arm64 or x86_64
# oldest macOS supported (LibreDWG build; the Python wheels set their own)
export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-11.0}"

echo "[1/5] Python packages"
# exact versions of requirements-lock.txt (see CLAUDE.md, "Dependencies")
"$PY" -m pip install -r requirements-dev.txt -c requirements-lock.txt --quiet
"$PY" scripts/check_lock.py

echo "[2/5] DWG converter (GNU LibreDWG)"
if [ ! -x "vendor/libredwg/macos-$ARCH/dxf2dwg" ]; then
    bash scripts/build_libredwg.sh macos
else
    echo "    already built: vendor/libredwg/macos-$ARCH"
fi

echo "[3/5] Tests"
if [ "${CONVERTCAD_NO_TESTS:-0}" = "1" ]; then
    echo "    skipped (CONVERTCAD_NO_TESTS=1)"
else
    QT_QPA_PLATFORM=offscreen "$PY" -m pytest -q
fi

echo "[4/5] Building (2 to 5 minutes)"
"$PY" scripts/make_icon.py
# fixed hash seed: two builds of the same code give identical files
PYTHONHASHSEED=0 CONVERTCAD_ONEFILE=0 "$PY" -m PyInstaller --noconfirm --clean ConvertCAD.spec
APP=dist/ConvertCAD.app
# the bundled converter must be executable after PyInstaller's copy
find "$APP" \( -name dxf2dwg -o -name dwg2dxf \) -type f -exec chmod +x {} +
# PyInstaller signs the bundle ad hoc; Apple Silicon refuses to start an
# app whose signature is broken, so check it (and sign again if needed)
if ! codesign --verify --deep --strict "$APP" 2>/dev/null; then
    echo "    re-signing the app (ad hoc)"
    codesign --force --deep --sign - "$APP"
    codesign --verify --deep --strict "$APP"
fi
"$APP/Contents/MacOS/ConvertCAD-cli" --version

echo "[5/5] Disk image and zip"
VER=$("$PY" -c "import convertcad; print(convertcad.APP_VERSION)")
NAME="ConvertCAD-${VER}-macos-${ARCH}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cp README.md LICENSE THIRD_PARTY_NOTICES.md CHANGELOG.md PRIVACY.md "$STAGE/"
rm -f "dist/$NAME.dmg" "dist/$NAME.zip"
hdiutil create -volname "ConvertCAD $VER" -srcfolder "$STAGE" \
    -fs HFS+ -format UDZO -ov "dist/$NAME.dmg"
# ditto keeps the bundle's symbolic links and signature (zip -r does not)
ditto -c -k --sequesterRsrc --keepParent "$APP" "dist/$NAME.zip"
echo "SUCCESS: $APP  dist/$NAME.dmg  dist/$NAME.zip"
