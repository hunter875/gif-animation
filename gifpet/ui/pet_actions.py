"""Thuc thi hanh dong: tu AI, tu menu, hay tu phim tat - mot duong duy nhat.

Tach ra khoi ``pet_window`` de chi co **mot** cho trong toan app thuc hien
hanh dong co tac dung phu. Khi them hanh dong moi, chi phai sua file nay, va
con nguoi review cung chi can doc mot file de biet app lam duoc gi.

Rang buoc bao mat (docs/SECURITY.md):

- Khong co nhanh nao chay shell, doc file, hay ghi file.
- URL duoc kiem tra lai lan cuoi truoc khi mo, du Brain da kiem tra.
- Hanh dong co tac dung phu phai duoc nguoi dung dong y.
"""

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QMessageBox

from gifpet.ai import actions as ai_actions
from gifpet.core import state as state_module


# Cau bao loi theo ma tu Brain. Tach ra de sua loi hien thi khong phai dung vao
# logic thuc thi.
ERROR_MESSAGES = {
    "disabled": "Trợ lý AI đang tắt.",
    "no_key": "Chưa có API key. Vào Cài đặt để nhập.",
    "exhausted": "Hết lượt dùng AI hôm nay.",
    "rate_limited": "Chậm thôi, vừa hỏi xong mà.",
    "model_disabled": "Đang tắt gọi model.",
    "auth": "API key sai hoặc đã hết hạn.",
    "rate_limit": "Nhà cung cấp đang giới hạn tốc độ, thử lại sau.",
    "network": "Không kết nối được mạng.",
    "server": "Nhà cung cấp đang lỗi, thử lại sau.",
    "unexpected": "Có lỗi khi gọi AI.",
    "rejected_action": "Pet định làm gì đó không được phép, đã bỏ qua.",
    "bad_reply": "Pet trả lời không rõ, đã bỏ qua.",
    "empty_reply": "Pet không trả lời được.",
    "ignored_event": "",
}


def error_message(code):
    return ERROR_MESSAGES.get(code, "Có lỗi khi gọi AI.")


def handle_brain_result(window, result):
    """Hien ket qua tu Brain; hoi xac nhan neu hanh dong co tac dung phu.

    Moi hanh dong da duoc ``actions`` kiem tra truoc khi toi day.
    """
    if not result.ok:
        message = error_message(result.error)
        if message:
            window.announce(message, duration_ms=5000)
        return

    if result.text:
        window.announce(result.text, duration_ms=6000)

    if result.action is None:
        return

    if result.needs_confirmation:
        ask_confirmation(window, result.action, result.params)
    else:
        run_action(window, result.action, result.params)


def ask_confirmation(window, action, params):
    """Lop 3: hoi nguoi dung truoc khi lam viec co tac dung phu.

    Mac dinh la "Khong": bam Enter hay dong hop thoai deu khong thuc hien.
    """
    question = ai_actions.describe(action, params)
    answer = QMessageBox.question(
        window,
        "Pet muốn làm việc này",
        f"{question}\n\nCho phép?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    if answer == QMessageBox.Yes:
        run_action(window, action, params)
    else:
        window.announce("Đã bỏ qua.", duration_ms=3000)


def run_action(window, name, params):
    """Thuc hien hanh dong da qua kiem tra.

    Khong co nhanh nao chay shell, doc file hay ghi file: chi cac hanh dong
    liet ke trong ``ai_actions.ALLOWED_ACTIONS``.
    """
    if name == "say":
        window.announce(params.get("text", ""), duration_ms=6000)
    elif name == "react":
        window.set_state(state_module.REACT)
    elif name == "set_state":
        window.set_state(params.get("state", state_module.IDLE))
    elif name == "remind":
        minutes = int(params.get("in_minutes", 1))
        text = params.get("text", "")
        # Luu ra file: hen 30 phut roi tat app thi van con.
        if window.reminders.add(text, minutes * 60):
            window.announce(f"Nhắc sau {minutes} phút nhé.", duration_ms=3000)
        else:
            window.announce("Không lưu được lời nhắc.", duration_ms=3000)
    elif name == "open_url":
        open_url(window, params.get("url", ""))


def open_url(window, url):
    """Mo URL bang trinh duyet mac dinh.

    Kiem tra lai lan cuoi du ``actions`` da kiem tra: khong bao gio tin rang
    du lieu den tu duong khac da duoc lam sach.
    """
    if not ai_actions.is_allowed("open_url"):
        return
    try:
        ai_actions.validate("open_url", {"url": url})
    except ai_actions.ActionError:
        window.announce("Địa chỉ này không được phép mở.", duration_ms=4000)
        return
    QDesktopServices.openUrl(QUrl(url))
