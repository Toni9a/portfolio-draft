import yt_dlp

url = "https://www.tiktok.com/@tonzownz/video/7402847503652879616"  # Replace with one of your TikTok URLs

try:
    with yt_dlp.YoutubeDL({
        "quiet": False,
        "writeautosub": True,
        "subtitlesformat": "srt",
        "outtmpl": "/tmp/test_%(id)s",
    }) as ydl:
        info = ydl.extract_info(url, download=True)
        print("\n=== VIDEO INFO ===")
        print(f"ID: {info.get('id')}")
        print(f"Title: {info.get('title')}")
        print(f"Has subtitles: {bool(info.get('subtitles'))}")
        if info.get('subtitles'):
            print(f"Subtitle langs: {list(info['subtitles'].keys())}")
        print(f"Auto captions: {bool(info.get('automatic_captions'))}")
        if info.get('automatic_captions'):
            print(f"Auto caption langs: {list(info['automatic_captions'].keys())}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
