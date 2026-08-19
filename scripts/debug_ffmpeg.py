"""
debug_ffmpeg.py — isolates the ffprobe/audio-extraction failure with full verbose output.
Run: python3 scripts/debug_ffmpeg.py
"""
import shutil
import subprocess
from pathlib import Path

import yt_dlp

print("=== yt-dlp version ===")
print(yt_dlp.version.__version__)

print("\n=== ffmpeg/ffprobe resolution ===")
ffmpeg_which = shutil.which("ffmpeg")
ffprobe_which = shutil.which("ffprobe")
print(f"shutil.which('ffmpeg'):  {ffmpeg_which}")
print(f"shutil.which('ffprobe'): {ffprobe_which}")

for candidate in ["/opt/homebrew/bin/ffmpeg", "/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffmpeg", "/usr/local/bin/ffprobe"]:
    print(f"exists({candidate}): {Path(candidate).exists()}")

print("\n=== Direct subprocess calls ===")
for exe in ["ffmpeg", "/opt/homebrew/bin/ffmpeg", "ffprobe", "/opt/homebrew/bin/ffprobe"]:
    try:
        result = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=5)
        print(f"{exe} -version -> rc={result.returncode}, first line: {result.stdout.splitlines()[0] if result.stdout else result.stderr.splitlines()[0]}")
    except Exception as e:
        print(f"{exe} -version -> FAILED: {e}")

print("\n=== yt-dlp verbose audio extraction test (real saved URLs) ===")
urls = [
    "https://vm.tiktok.com/ZN88eAHoY/",
    "https://vm.tiktok.com/ZN8L15oaj",
    "https://vm.tiktok.com/ZN889jY9W",
]

ffmpeg_location = str(Path(ffmpeg_which).parent) if ffmpeg_which else "/opt/homebrew/bin"
print(f"Using ffmpeg_location: {ffmpeg_location}")

for i, url in enumerate(urls):
    print(f"\n--- URL {i+1}: {url} ---")
    work_dir = Path(f"/tmp/debug_ffmpeg_test_{i}")
    work_dir.mkdir(exist_ok=True)
    try:
        with yt_dlp.YoutubeDL({
            "quiet": False,
            "verbose": True,
            "no_warnings": False,
            "format": "bestaudio/best",
            "outtmpl": str(work_dir / "audio.%(ext)s"),
            "ffmpeg_location": ffmpeg_location,
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}],
        }) as ydl:
            ydl.download([url])
        print(f"Files produced for URL {i+1}:")
        for f in work_dir.glob("*"):
            print(f"  {f} ({f.stat().st_size} bytes)")
    except Exception as e:
        print(f"CAUGHT EXCEPTION for URL {i+1}: {e}")
