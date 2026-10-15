#!/usr/bin/env bash
# Don gon thu muc binary sau khi Nuitka build.
#
# Nuitka keo vao moi Qt plugin, ke ca nhung thu pet khong dung (QML, Quick,
# media, in an, Wayland). Script nay loai bot de giam kich thuoc.
#
#   ./tools/slim_binary.sh [thu-muc-dist]
#
# Mac dinh: dist/gifpet.dist
#
# LUU Y: neu ban chay tren desktop Wayland, dung xoa cac thu muc wayland-*.
# Dat KEEP_WAYLAND=1 de giu lai.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TARGET="${1:-$PROJECT_DIR/dist/gifpet.dist}"

if [ ! -d "$TARGET" ]; then
    echo "[error] Khong tim thay: $TARGET" >&2
    echo "        Chay ./tools/build_binary.sh truoc." >&2
    exit 1
fi

cd "$TARGET"
BEFORE=$(du -sm . | cut -f1)

echo "[slim] Truoc: ${BEFORE} MB"

# --- Qt plugin khong dung ---
# mediaservice  : phat nhac/video, pet chi hien GIF
# printsupport  : in an
# qmltooling    : debug QML
# designer      : plugin thiet ke Qt
# sqldrivers    : co so du lieu (pet dung JSON)
# sensors, position, geoservices, texttospeech, webview: khong dung
PATTERNS=(
    "PyQt5/qt-plugins/mediaservice"
    "PyQt5/qt-plugins/printsupport"
    "PyQt5/qt-plugins/qmltooling"
    "PyQt5/qt-plugins/designer"
    "PyQt5/qt-plugins/sqldrivers"
    "PyQt5/qt-plugins/sensors"
    "PyQt5/qt-plugins/position"
    "PyQt5/qt-plugins/geoservices"
    "PyQt5/qt-plugins/texttospeech"
    "PyQt5/qt-plugins/webview"
    "PyQt5/qt-plugins/playlistformats"
    "PyQt5/qt-plugins/bearer"
    "PyQt5/qt-plugins/canbus"
    "PyQt5/qt-plugins/gamepads"
    "PyQt5/qt-plugins/virtualkeyboard"
)

# Wayland: chi xoa khi nguoi dung dong y (mac dinh giu de an toan).
if [ "${KEEP_WAYLAND:-1}" != "1" ]; then
    PATTERNS+=(
        "PyQt5/qt-plugins/wayland-shell-integration"
        "PyQt5/qt-plugins/wayland-graphics-integration-client"
        "PyQt5/qt-plugins/wayland-decoration-client"
    )
fi

for pattern in "${PATTERNS[@]}"; do
    if [ -e "$pattern" ]; then
        rm -rf "$pattern"
        echo "  - xoa $pattern"
    fi
done

# --- Thu vien Qt khong dung ---
# QML/Quick: pet khong dung giao dien QML
for lib in libQt5Quick.so* libQt5Qml.so* libQt5QmlModels.so* libQt5QuickWidgets.so*; do
    if [ -e "$lib" ]; then
        rm -f $lib
        echo "  - xoa $lib"
    fi
done

# --- Bo file build va bytecode ---
rm -rf *.build 2>/dev/null || true

AFTER=$(du -sm . | cut -f1)
SAVED=$((BEFORE - AFTER))
echo "[slim] Sau:  ${AFTER} MB  (giam ${SAVED} MB)"
