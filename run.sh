#!/usr/bin/env bash
# Chay GIF Pet tren Linux/macOS.
# Tu dong tao virtualenv va cai dependency neu chua co.
#
#   ./run.sh            chay app
#   ./run.sh --test     chay test (khong can man hinh)
#   ./run.sh --accept   kiem tra tung tieu chi nghiem thu
#   ./run.sh --phase3   kiem tra vong doi pet (Giai doan 3)
#   ./run.sh --headless chay app o che do khong man hinh (kiem tra khoi dong)
#
# Gioi han an toan (dat 0 de tat):
#   GIFPET_MAX_RAM_MB=700  tran RAM cua tien trinh pet
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
MODE="run"

case "${1:-}" in
    --test)     MODE="test" ;;
    --accept)   MODE="accept" ;;
    --phase3)   MODE="phase3" ;;
    --headless) MODE="headless" ;;
    --help|-h)
        sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
        exit 0
        ;;
    "") ;;
    *)
        echo "[error] Tham so khong hop le: $1 (dung --help)" >&2
        exit 2
        ;;
esac

if [ ! -d "$VENV_DIR" ]; then
    echo "[setup] Tao virtualenv tai $VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# Cai dependency neu PyQt5 chua co trong venv.
if ! "$VENV_DIR/bin/python" -c "import PyQt5" >/dev/null 2>&1; then
    echo "[setup] Cai dependency tu requirements.txt"
    "$VENV_DIR/bin/pip" install --upgrade pip >/dev/null
    "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
fi

if [ "$MODE" = "test" ]; then
    # Chay tat ca file test_*.py trong tests/.
    status=0
    for test_file in "$SCRIPT_DIR"/tests/test_*.py; do
        name="$(basename "$test_file")"
        echo "=== $name ==="
        if ! env QT_QPA_PLATFORM=offscreen "$VENV_DIR/bin/python" "$test_file"; then
            status=1
        fi
    done
    exit $status
fi

if [ "$MODE" = "accept" ]; then
    exec env QT_QPA_PLATFORM=offscreen \
        "$VENV_DIR/bin/python" "$SCRIPT_DIR/tests/test_acceptance.py"
fi

if [ "$MODE" = "phase3" ]; then
    exec env QT_QPA_PLATFORM=offscreen \
        "$VENV_DIR/bin/python" "$SCRIPT_DIR/tests/test_phase3_flow.py"
fi

if [ "$MODE" = "headless" ]; then
    export QT_QPA_PLATFORM=offscreen
    exec "$VENV_DIR/bin/python" -m gifpet
fi

# App can moi truong do hoa that de hien thi GIF.
if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    echo "[error] Khong tim thay DISPLAY/WAYLAND_DISPLAY." >&2
    echo "        App nay can moi truong do hoa that de hien thi GIF." >&2
    echo "        Neu chi muon kiem tra code chay duoc:" >&2
    echo "          ./run.sh --headless" >&2
    exit 1
fi

# Gioi han tai nguyen phong khi co loi: app khong bao gio duoc phep keo ca may
# xuong. Dat 0 de tat gioi han.
#   GIFPET_MAX_RAM_MB (mac dinh 700) : vuot thi tien trinh bi kernel dung
MAX_RAM_MB="${GIFPET_MAX_RAM_MB:-700}"

apply_limits() {
    if [ "$MAX_RAM_MB" != "0" ] && command -v prlimit >/dev/null 2>&1; then
        # Chi dat tran RAM (khong dat tran CPU) de khong giet app bat ngo.
        prlimit --as=$((MAX_RAM_MB * 1024 * 1024)) -- "$@" 2>/dev/null && return 0
    fi
    # Khong co prlimit: dung ulimit cua shell.
    if [ "$MAX_RAM_MB" != "0" ]; then
        ulimit -v $((MAX_RAM_MB * 1024)) 2>/dev/null || true
    fi
    exec "$@"
}

if [ "$MAX_RAM_MB" != "0" ]; then
    echo "[giới hạn] RAM tối đa ${MAX_RAM_MB} MB (đặt GIFPET_MAX_RAM_MB=0 để tắt)"
fi

apply_limits "$VENV_DIR/bin/python" -m gifpet "$@"
