"""
convert_webm_to_mov.py
WebM VP9 Alpha → MOV ProRes 4444 XQ (with Alpha)

ملاحظة: libx265 في هذا البناء لا يدعم Alpha encoding،
لذا نستخدم ProRes 4444 XQ وهو الصيغة الاحترافية القياسية
للحفاظ على قناة الألفا في MOV (مدعوم في After Effects / Final Cut / DaVinci).

الفيديوهات الأصلية: VP9 crf=56, 20fps
"""

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ─── إعدادات ───────────────────────────────────────────────────────────────
INPUT_DIR   = Path("webm_3")
OUTPUT_DIR  = Path("mov_output")

# q:v للـ ProRes: 0=أعلى جودة (أكبر حجم) ← 31=أقل جودة (أصغر حجم)
# 9-13 = جودة عالية جداً مع حجم معقول
PRORES_Q    = 11

# عدد العمليات المتوازية
MAX_WORKERS = max(1, os.cpu_count() - 1)
# ───────────────────────────────────────────────────────────────────────────


def build_ffmpeg_cmd(input_path: Path, output_path: Path) -> list[str]:
    return [
        "ffmpeg", "-y",
        "-vcodec", "libvpx-vp9",       # فرض decoder VP9 لاستخراج قناة الألفا
        "-i", str(input_path),
        "-c:v", "prores_ks",
        "-profile:v", "4444xq",        # ProRes 4444 XQ: يدعم Alpha + أعلى جودة
        "-pix_fmt", "yuva444p10le",    # 10-bit YUVA مع قناة الألفا
        "-q:v", str(PRORES_Q),
        "-vendor", "apl0",             # توافق Apple QuickTime
        "-c:a", "aac",
        "-b:a", "64k",
        "-movflags", "+faststart",
        str(output_path),
    ]


def convert_file(input_path: Path) -> tuple[str, bool, float, str]:
    rel = input_path.relative_to(INPUT_DIR)
    output_path = OUTPUT_DIR / rel.with_suffix(".mov")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = build_ffmpeg_cmd(input_path, output_path)
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        elapsed = time.time() - t0
        if result.returncode != 0:
            err_lines = [l for l in result.stderr.splitlines() if l.strip()]
            err_msg = err_lines[-1] if err_lines else "unknown error"
            return (str(rel), False, elapsed, err_msg)
        return (str(rel), True, elapsed, "")
    except Exception as e:
        return (str(rel), False, time.time() - t0, str(e))


def main():
    files = sorted(INPUT_DIR.glob("**/*.webm"))
    if not files:
        print(f"[!] لا توجد ملفات .webm في {INPUT_DIR}")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total   = len(files)
    done    = 0
    failed  = []
    t_start = time.time()

    print(f"[*] تحويل {total} ملف | workers={MAX_WORKERS} | ProRes 4444 XQ q={PRORES_Q}")
    print("-" * 60)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(convert_file, f): f for f in files}
        for future in as_completed(futures):
            name, ok, elapsed, err = future.result()
            done += 1
            status = "OK" if ok else "FAIL"
            print(f"[{done:>3}/{total}] {status}  {name}  ({elapsed:.1f}s)")
            if not ok:
                failed.append((name, err))

    total_time = time.time() - t_start
    print("-" * 60)
    print(f"[*] انتهى في {total_time:.1f}s | نجح: {total - len(failed)} | فشل: {len(failed)}")

    if failed:
        print("\n[!] الملفات الفاشلة:")
        for name, err in failed:
            print(f"    {name}: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
