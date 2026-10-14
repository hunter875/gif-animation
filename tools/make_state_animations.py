"""Tao animation cho cac trang thai con thieu tu GIF co san.

Bo GIF di kem repo chi co 4 file, chua du cho 7 trang thai cua Giai doan 3.
Script nay sinh them fall.gif, react.gif, talk.gif bang cach bien doi GIF goc,
de bo pet mau day du ngay ma khong can tim asset ben ngoai.

Chay: .venv/bin/python tools/make_state_animations.py

Hai bai hoc ve nen GIF (da do thuc te, xem comments trong code):

1. KHONG dung rotate. Xoay lam moi pixel thay doi, pha vo tinh lien tuc giua
   cac frame: idle.gif 1.1 MB -> 6.0 MB.
2. Pillow re-encode ton kem hon cong cu tao GIF goc: giu nguyen 20 frame van
   ton 2.2 MB du khong sua gi. Giam so frame (lay cach quang) moi ha duoc
   kich thuoc: 10 frame -> 1.1 MB.

Khi co animation that, chi can thay file trong pets/<ten>/ la xong.
"""

import math
import os
import sys

from PIL import Image, ImageSequence

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK_DIR = os.path.join(BASE, "pets", "default")

# Giam so frame de GIF khong phinh to khi re-encode bang Pillow.
MAX_FRAMES = 10


def load_frames(path):
    """Doc GIF, giu nguyen mode P de khong phai quantize lai."""
    image = Image.open(path)
    frames = []
    durations = []
    for frame in ImageSequence.Iterator(image):
        frames.append(frame.copy())
        durations.append(frame.info.get("duration", 80))
    return frames, durations


def subsample(frames, durations, max_frames=MAX_FRAMES):
    """Lay cach quang de giam so frame, giu tong thoi gian phat."""
    if len(frames) <= max_frames:
        return frames, durations
    step = max(1, len(frames) // max_frames)
    picked_frames = frames[::step]
    # Gop thoi luong cua cac frame bi bo qua vao frame giu lai.
    picked_durations = []
    for index in range(len(picked_frames)):
        start = index * step
        end = min(len(frames), start + step)
        picked_durations.append(sum(durations[start:end]))
    return picked_frames, picked_durations


def shift_frame(frame, dx=0, dy=0):
    """Dich chuyen mot frame, giu nguyen pixel goc.

    Copy chinh frame roi paste lech, KHONG tao canvas nen moi: tao canvas moi
    lam thay doi toan bo vung nen va ton them bytes.
    """
    if dx == 0 and dy == 0:
        return frame.copy()
    canvas = frame.copy()
    canvas.paste(frame, (dx, dy))
    return canvas


def save_gif(frames, durations, path):
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        disposal=2,
    )
    return path


def make_fall(source="drag.gif"):
    """Roi: lac qua lai theo phuong ngang, nhu mat thang bang giua khong trung."""
    frames, durations = load_frames(os.path.join(PACK_DIR, source))
    frames, durations = subsample(frames, durations)
    out = []
    out_durations = []
    for index, frame in enumerate(frames):
        phase = (index / max(1, len(frames))) * 2 * math.pi
        dx = int(8 * math.sin(phase * 2))
        out.append(shift_frame(frame, dx=dx))
        out_durations.append(max(40, durations[index] // 2))
    save_gif(out, out_durations, os.path.join(PACK_DIR, "fall.gif"))
    return len(out)


def make_react(source="idle.gif"):
    """Phan ung khi bi click: nhun len roi tat dan."""
    frames, durations = load_frames(os.path.join(PACK_DIR, source))
    frames, durations = subsample(frames, durations)
    out = []
    out_durations = []
    total = max(1, len(frames))
    for index, frame in enumerate(frames):
        decay = 1.0 - (index / total)
        dy = -int(14 * abs(math.sin(index * 0.9)) * decay)
        out.append(shift_frame(frame, dy=dy))
        out_durations.append(max(60, int(durations[index] * (0.5 + 0.5 * decay))))
    save_gif(out, out_durations, os.path.join(PACK_DIR, "react.gif"))
    return len(out)


def make_talk(source="idle.gif"):
    """Dang noi: nhun nhe deu dan, nhu dang gap giap."""
    frames, durations = load_frames(os.path.join(PACK_DIR, source))
    frames, durations = subsample(frames, durations)
    out = []
    out_durations = []
    offsets = (0, -4, -7, -4)
    for index, frame in enumerate(frames):
        out.append(shift_frame(frame, dy=offsets[index % len(offsets)]))
        out_durations.append(110)
    save_gif(out, out_durations, os.path.join(PACK_DIR, "talk.gif"))
    return len(out)


def main():
    if not os.path.isdir(PACK_DIR):
        print(f"Khong tim thay {PACK_DIR}", file=sys.stderr)
        return 1

    jobs = [
        ("fall.gif", make_fall, "drag.gif"),
        ("react.gif", make_react, "idle.gif"),
        ("talk.gif", make_talk, "idle.gif"),
    ]
    total = 0
    for filename, maker, source in jobs:
        if not os.path.isfile(os.path.join(PACK_DIR, source)):
            print(f"Thieu {source}, bo qua {filename}", file=sys.stderr)
            continue
        count = maker()
        path = os.path.join(PACK_DIR, filename)
        size_kb = os.path.getsize(path) // 1024
        total += size_kb
        print(f"  {filename:10s} {count:3d} frames  {size_kb:5d} KB  (tu {source})")
    print(f"  {'TONG':10s} {total:5d} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
