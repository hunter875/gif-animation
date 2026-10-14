#!/usr/bin/env bash
# Chay GIF Pet tren Linux/macOS.
# Tu dong tao virtualenv va cai dependency neu chua co.
#
#   ./run.sh            chay app
#   ./run.sh --test     chay test (khong can man hinh)
#   ./run.sh --accept   kiem tra tung tieu chi nghiem thu
#   ./run.sh --headless chay app o che do khong man hinh (kiem tra khoi dong)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
MODE="run"

case "${1:-}" in
    --test)     MODE="test" ;;
    --accept)   MODE="accept" ;;
    --headless) MODE="headless" ;;
    --help|-h)
        sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
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
    exec env QT_QPA_PLATFORM=offscreen \
        "$VENV_DIR/bin/python" "$SCRIPT_DIR/tests/test_pet.py"
fi

if [ "$MODE" = "accept" ]; then
    exec env QT_QPA_PLATFORM=offscreen \
        "$VENV_DIR/bin/python" "$SCRIPT_DIR/tests/acceptance_check.py"
fi

if [ "$MODE" = "headless" ]; then
    export QT_QPA_PLATFORM=offscreen
    exec "$VENV_DIR/bin/python" "$SCRIPT_DIR/main.py"
fi

# App can moi truong do hoa that de hien thi GIF.
if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    echo "[error] Khong tim thay DISPLAY/WAYLAND_DISPLAY." >&2
    echo "        App nay can moi truong do hoa that de hien thi GIF." >&2
    echo "        Neu chi muon kiem tra code chay duoc:" >&2
    echo "          ./run.sh --headless" >&2
    exit 1
fi

exec "$VENV_DIR/bin/python" "$SCRIPT_DIR/main.py" "$@"
