"""
convert_mac.py
يشتغل على Mac — يحوّل WebM VP9 Alpha إلى MOV HEVC Alpha
باستخدام hevc_videotoolbox (خاص بـ Apple)
"""

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

INPUT_DIR  = Path("webm_3")
OUTPUT_DIR = Path("mov_output")
MAX_WORKERS = 1  # واحد فقط — VideoToolbox يعلق مع التوازي على GitHub runners


def convert_file(input_path: Path) -> tuple[str, bool, float, str]:
    rel = input_path.relative_to(INPUT_DIR)
    output_path = OUTPUT_DIR / rel.with_suffix(".mov")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # تخطي الملف إذا كان موجوداً مسبقاً
    if output_path.exists() and output_path.stat().st_size > 0:
        return (str(rel), True, 0.0, "skipped")

    cmd = [
        "ffmpeg", "-y",
        "-vcodec", "libvpx-vp9",
        "-r", "20",
        "-i", str(input_path),
        "-fps_mode", "cfr",
        "-c:v", "hevc_videotoolbox",
        "-allow_sw", "1",
        "-alpha_quality", "0.75",
        "-b:v", "360k",
        "-tag:v", "hvc1",
        "-c:a", "aac",
        "-b:a", "64k",
        "-movflags", "+faststart",
        str(output_path),
    ]

    t0 = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        elapsed = time.time() - t0
        if result.returncode != 0:
            err_lines = [l for l in result.stderr.splitlines() if l.strip()]
            err_msg = err_lines[-1] if err_lines else "unknown error"
            return (str(rel), False, elapsed, err_msg)
        return (str(rel), True, elapsed, "")
    except subprocess.TimeoutExpired:
        return (str(rel), False, time.time() - t0, "TIMEOUT (>900s)")
    except Exception as e:
        return (str(rel), False, time.time() - t0, str(e))


def main():
    files = sorted(INPUT_DIR.glob("**/*.webm"))
    if not files:
        print(f"[!] لا توجد ملفات .webm في {INPUT_DIR}")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total, done, failed = len(files), 0, []
    t_start = time.time()

    print(f"[*] تحويل {total} ملف | workers={MAX_WORKERS}")
    print("-" * 60)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(convert_file, f): f for f in files}
        for future in as_completed(futures):
            name, ok, elapsed, err = future.result()
            done += 1
            if err == "skipped":
                print(f"[{done:>3}/{total}] SKIP {name}")
            else:
                status = "OK  " if ok else "FAIL"
                print(f"[{done:>3}/{total}] {status} {name}  ({elapsed:.1f}s)")
            if not ok and err != "skipped":
                failed.append((name, err))

    print("-" * 60)
    print(f"[*] انتهى في {time.time()-t_start:.1f}s | نجح: {total-len(failed)} | فشل: {len(failed)}")

    if failed:
        print("\n[!] الملفات الفاشلة:")
        for name, err in failed:
            print(f"    {name}: {err}")
        # لا نوقف التنفيذ — الملفات الناجحة تُرفع كـ artifact
        print("\n[*] الملفات الناجحة سيتم رفعها كـ artifact")


if __name__ == "__main__":
    main()
