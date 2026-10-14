"""Doc thu vien nhan vat (pet pack).

Moi nhan vat la mot thu muc trong ``pets/`` gom cac file GIF dat ten theo
trang thai (``idle.gif``, ``walk.gif``, ``drag.gif``, ...) va mot file
``pet.json`` mo ta kich thuoc, toc do, hanh vi va tinh cach.

Nguyen tac quan trong: bo pet thieu trang thai van dung duoc. Trang thai nao
khong co GIF rieng thi lay ``fallback_animation`` (mac dinh ``idle.gif``).
"""

import json
import os

from gifpet.core import gif_library

# Cac trang thai ma pet co the co animation rieng.
STATES = ("idle", "walk", "drag", "fall", "sleep", "react", "talk")

DEFAULT_PACK_NAME = "default"

DEFAULT_BEHAVIOR = {
    "idle_to_sleep_ms": 120000,
    "react_duration_ms": 1500,
    "fall_speed_px_per_step": 14,
    "fall_step_interval_ms": 30,
}

DEFAULT_MOVEMENT = {
    "speed_px_per_step": 2,
    "step_interval_ms": 40,
    "pause_chance": 0.3,
    "min_pause_ms": 2000,
    "max_pause_ms": 8000,
}

DEFAULT_PERSONALITY = {
    "tone": "thân thiện",
    "likes": [],
    "dislikes": [],
    "max_reply_chars": 120,
}


class PetPack:
    """Mot nhan vat: thu muc GIF + file mo ta."""

    def __init__(self, directory, manifest=None):
        self.directory = directory
        self.name = os.path.basename(directory)
        raw = manifest if isinstance(manifest, dict) else {}

        self.display_name = raw.get("display_name") or self.name
        self.description = raw.get("description", "")
        self.animations = self._read_animations(raw)
        self.fallback_animation = raw.get("fallback_animation") or "idle.gif"
        self.size = raw.get("size") if isinstance(raw.get("size"), dict) else {}
        self.movement = {**DEFAULT_MOVEMENT, **_dict_or_empty(raw.get("movement"))}
        self.behavior = {**DEFAULT_BEHAVIOR, **_dict_or_empty(raw.get("behavior"))}
        self.personality = {**DEFAULT_PERSONALITY, **_dict_or_empty(raw.get("personality"))}

    def _read_animations(self, raw):
        animations = {}
        declared = raw.get("animations")
        if isinstance(declared, dict):
            for state, filename in declared.items():
                if isinstance(filename, str) and filename:
                    animations[state] = filename
        # Bo sung cac GIF co san nhung chua khai bao trong pet.json.
        for state in STATES:
            if state not in animations:
                candidate = f"{state}.gif"
                if os.path.isfile(os.path.join(self.directory, candidate)):
                    animations[state] = candidate
        return animations

    def animation_path(self, state):
        """Duong dan GIF cho trang thai, tu dong lui ve fallback neu thieu.

        Tra ve ``None`` neu ca trang thai lan fallback deu khong dung duoc.
        """
        for candidate in (state, None):
            filename = self.animations.get(candidate) if candidate else None
            if candidate is None:
                filename = self.fallback_animation
            if not filename:
                continue
            path = os.path.join(self.directory, filename)
            if gif_library.is_valid_gif(path):
                return path
        # Cuoi cung: bat ky GIF nao dung duoc trong thu muc.
        for filename in sorted(self.animations.values()):
            path = os.path.join(self.directory, filename)
            if gif_library.is_valid_gif(path):
                return path
        return None

    def has_state(self, state):
        """True neu trang thai co GIF rieng (khong tinh fallback)."""
        filename = self.animations.get(state)
        if not filename:
            return False
        return gif_library.is_valid_gif(os.path.join(self.directory, filename))

    def missing_states(self):
        """Cac trang thai chua co GIF rieng, se dung fallback."""
        return [state for state in STATES if not self.has_state(state)]

    def all_animation_paths(self):
        """Tat ca GIF dung duoc cua nhan vat nay."""
        paths = []
        for filename in sorted(set(self.animations.values())):
            path = os.path.join(self.directory, filename)
            if gif_library.is_valid_gif(path) and path not in paths:
                paths.append(path)
        return paths


def _dict_or_empty(value):
    return value if isinstance(value, dict) else {}


def load_pack(directory):
    """Doc mot thu muc nhan vat. Tra ve ``PetPack`` ke ca khi thieu pet.json."""
    manifest = {}
    manifest_path = os.path.join(directory, "pet.json")
    try:
        with open(manifest_path, encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            manifest = loaded
        else:
            print(f"Canh bao: {manifest_path} khong phai object JSON, dung mac dinh.")
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        print(f"Canh bao: khong doc duoc {manifest_path} ({exc}), dung mac dinh.")
    return PetPack(directory, manifest)


def discover_packs(pets_dir):
    """Tim tat ca nhan vat trong thu muc pets/.

    Thu tu uu tien: thu muc ``default`` truoc, sau do theo ten.
    """
    if not os.path.isdir(pets_dir):
        return []

    packs = []
    for entry in sorted(os.listdir(pets_dir)):
        directory = os.path.join(pets_dir, entry)
        if not os.path.isdir(directory):
            continue
        pack = load_pack(directory)
        if pack.all_animation_paths():
            packs.append(pack)
        else:
            print(f"Bo qua nhan vat '{entry}': khong co GIF nao dung duoc.")

    packs.sort(key=lambda pack: (pack.name != DEFAULT_PACK_NAME, pack.name))
    return packs


def load_default_pack(pets_dir):
    """Nhan vat mac dinh, hoac nhan vat dau tien tim duoc."""
    packs = discover_packs(pets_dir)
    if not packs:
        return None
    for pack in packs:
        if pack.name == DEFAULT_PACK_NAME:
            return pack
    return packs[0]
