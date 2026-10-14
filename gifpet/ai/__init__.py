"""Ket noi AI (Giai doan 4) - CHUA TRIEN KHAI.

Thiet ke du kien, theo dung yeu cau trong spec:

    provider.py   giao dien chung cho cac nha cung cap (Groq, Gemini, ...)
    actions.py    danh sach hanh dong duoc phep + kiem tra ten/tham so/tan suat
    memory.py     bo nho xem va xoa duoc; chi luu dieu nguoi dung cho phep
    quota.py      dem luot dung trong ngay, tran luot/ngay
    brain.py      gom su kien -> goi model -> tra ve (cau noi, hanh dong)

Nguyen tac bat buoc:

- Model CHI duoc de xuat hanh dong co trong danh sach cho phep. App kiem tra
  ten hanh dong, tham so va tan suat truoc khi thuc hien.
- Khong nhan lenh tuy y nhu chay shell hay mo file.
- Khong gui lai toan bo lich su moi lan; chi gui su kien da chon.
- Het quota hoac mat mang thi pet van hoat dong local binh thuong.
- Click lien tuc duoc gom thanh mot su kien; pet tu di, roi, ngu khong goi model.
"""
