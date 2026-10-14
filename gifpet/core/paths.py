"""Cac duong dan goc cua ung dung.

Tap trung mot cho de khong bi lan man nhu truoc. Cau truc:

    <project>/                  <- PROJECT_ROOT
        gifpet/                 <- PACKAGE_DIR
            assets/             <- ASSETS_DIR (icon, am thanh)
        pets/                   <- PETS_DIR (thu vien nhan vat)
        *.gif                   <- GIF di kem, dung lam mac dinh
"""

import os

# gifpet/core/paths.py -> gifpet/core -> gifpet -> <project>
CORE_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_DIR = os.path.dirname(CORE_DIR)
PROJECT_ROOT = os.path.dirname(PACKAGE_DIR)

ASSETS_DIR = os.path.join(PACKAGE_DIR, "assets")
PETS_DIR = os.path.join(PROJECT_ROOT, "pets")

APP_ICON = os.path.join(ASSETS_DIR, "app_icon.ico")
