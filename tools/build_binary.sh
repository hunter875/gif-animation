#!/usr/bin/env bash
# Dong goi GIF Pet thanh binary chay doc lap (khong can cai Python).
#
# Dung Nuitka: compile Python -> C -> binary, kem san moi thu can thiet.
# Ket qua nam trong dist/gifpet.dist/ (che do standalone).
#
#   ./tools/build_binary.sh            build standalone (khuyen dung)
#   ./tools/build_binary.sh --onefile  build mot file duy nhat (can patchelf)
#   ./tools/build_binary.sh --clean    xoa ket qua cu roi build lai
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

VENV_DIR="$PROJECT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"

MODE="standalone"
CLEAN=0
for arg in "$@"; do
    case "$arg" in
        --onefile) MODE="onefile" ;;
        --standalone) MODE="standalone" ;;
        --clean) CLEAN=1 ;;
        --help|-h)
            sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "[error] Tham so khong hop le: $arg" >&2
            exit 2
            ;;
    esac
done

# Nuitka can cache o noi ghi duoc. Mac dinh no dung ~/.cache/Nuitka,
# tren mot so moi truong bi chan.
export NUITKA_CACHE_DIR="${NUITKA_CACHE_DIR:-/tmp/nuitka-cache}"
mkdir -p "$NUITKA_CACHE_DIR"

# Nuitka can mot compiler C.
if ! command -v gcc >/dev/null 2>&1 && ! command -v cc >/dev/null 2>&1; then
    echo "[error] Khong tim thay gcc/cc. Cai compiler C truoc." >&2
    exit 1
fi

# Bao dam Nuitka co trong venv.
if ! "$PYTHON" -c "import nuitka" >/dev/null 2>&1; then
    echo "[setup] Cai Nuitka vao venv"
    "$VENV_DIR/bin/pip" install --cache-dir /tmp/pipcache nuitka
fi

# Che do standalone tren Linux can patchelf. Goi y tu pip duoc,
# nen khong can quyen root.
if [ "$MODE" = "standalone" ] || [ "$MODE" = "onefile" ]; then
    if ! command -v patchelf >/dev/null 2>&1; then
        if [ -x "$VENV_DIR/bin/patchelf" ]; then
            export PATH="$VENV_DIR/bin:$PATH"
        else
            echo "[setup] Cai patchelf vao venv"
            "$VENV_DIR/bin/pip" install --cache-dir /tmp/pipcache patchelf
            export PATH="$VENV_DIR/bin:$PATH"
        fi
    fi
fi

if [ "$CLEAN" = "1" ]; then
    echo "[setup] Xoa ket qua cu"
    rm -rf dist build/nuitka
fi

echo "[build] Che do: $MODE"
echo "[build] Cache:  $NUITKA_CACHE_DIR"
echo

ARGS=(
    --assume-yes-for-downloads
    --output-dir=dist
    # Khong dat ten trung voi thu muc package gifpet/, Nuitka se bao loi.
    --output-filename=gif-pet
    --enable-plugin=pyqt5
    # Compile ca package: chi dinh thu muc 'gifpet', khong phai file __main__.py.
    --python-flag=-m
    # Du lieu kem theo: thu vien nhan vat va icon.
    --include-data-dir=pets=pets
    --include-data-file=gifpet/assets/app_icon.ico=gifpet/assets/app_icon.ico
    # Bo qua module khong dung cho gon.
    --nofollow-import-to=tkinter
    --nofollow-import-to=unittest
    --noinclude-pytest-mode=nofollow
)

if [ "$MODE" = "onefile" ]; then
    ARGS+=(--onefile)
else
    ARGS+=(--standalone)
fi

"$PYTHON" -m nuitka "${ARGS[@]}" gifpet

echo
echo "[done] Ket qua:"
if [ "$MODE" = "onefile" ]; then
    ls -lh dist/gif-pet 2>/dev/null || true
else
    du -sh dist/gif-pet.dist 2>/dev/null || true
    ls -lh dist/gif-pet.dist/gif-pet 2>/dev/null || true
fi
