import os
import re
import shutil
import uuid
import threading
import time

from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp

app = Flask(__name__)

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

download_tasks = {}

BROWSER_PRIORITY = ["chrome", "edge", "firefox", "opera", "brave", "chromium"]

HAS_FFMPEG = shutil.which("ffmpeg") is not None

_cached_browser = None


def detect_browser():
    """Detect which browser is available for cookie extraction."""
    for browser in BROWSER_PRIORITY:
        try:
            yt_dlp.cookies.extract_cookies_from_browser(browser)
            return browser
        except Exception:
            continue
    return None


def get_cookie_opts():
    """Get yt-dlp options for cookie authentication."""
    global _cached_browser
    if _cached_browser is None:
        _cached_browser = detect_browser() or ""
    if _cached_browser:
        return {"cookiesfrombrowser": (_cached_browser,)}
    return {}


def clean_url(url):
    """Remove playlist parameters from URL to download single video only."""
    url = url.strip()
    url = re.sub(r'[&?](list|index|start_radio)=[^&]*', '', url)
    if '?' not in url and '&' in url:
        url = url.replace('&', '?', 1)
    return url


def clean_old_files():
    """Remove downloaded files older than 1 hour."""
    now = time.time()
    for filename in os.listdir(DOWNLOAD_DIR):
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.isfile(filepath) and now - os.path.getmtime(filepath) > 3600:
            os.remove(filepath)


def get_video_info(url):
    """Get video info without downloading."""
    url = clean_url(url)
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "noplaylist": True,
        **get_cookie_opts(),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

        formats = info.get("formats", [])
        best_video_height = 0
        best_audio_abr = 0
        for f in formats:
            h = f.get("height") or 0
            if h > best_video_height:
                best_video_height = h
            abr = f.get("abr") or 0
            if abr > best_audio_abr:
                best_audio_abr = abr

        return {
            "title": info.get("title", "Unknown"),
            "thumbnail": info.get("thumbnail", ""),
            "duration": info.get("duration", 0),
            "channel": info.get("channel", info.get("uploader", "Unknown")),
            "best_video_height": best_video_height,
            "best_audio_abr": int(best_audio_abr),
        }


def download_video(task_id, url, format_type):
    """Download video in background thread."""
    task = download_tasks[task_id]
    task["status"] = "downloading"
    task["progress"] = 0

    unique_name = f"{task_id}"

    def progress_hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                task["progress"] = int((downloaded / total) * 100)
            task["status"] = "downloading"
        elif d["status"] == "finished":
            task["status"] = "converting"
            task["progress"] = 100

    url = clean_url(url)
    cookie_opts = get_cookie_opts()

    if format_type == "mp3":
        if HAS_FFMPEG:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(DOWNLOAD_DIR, f"{unique_name}.%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "320",
                    }
                ],
                "progress_hooks": [progress_hook],
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                **cookie_opts,
            }
        else:
            ydl_opts = {
                "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
                "outtmpl": os.path.join(DOWNLOAD_DIR, f"{unique_name}.%(ext)s"),
                "progress_hooks": [progress_hook],
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                **cookie_opts,
            }
    else:
        if HAS_FFMPEG:
            ydl_opts = {
                "format": "bestvideo[ext=mp4][height<=2160]+bestaudio[ext=m4a]/bestvideo[height<=2160]+bestaudio/best[ext=mp4]/best",
                "outtmpl": os.path.join(DOWNLOAD_DIR, f"{unique_name}.%(ext)s"),
                "merge_output_format": "mp4",
                "progress_hooks": [progress_hook],
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                **cookie_opts,
            }
        else:
            ydl_opts = {
                "format": "best[ext=mp4][height<=2160]/best",
                "outtmpl": os.path.join(DOWNLOAD_DIR, f"{unique_name}.%(ext)s"),
                "progress_hooks": [progress_hook],
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                **cookie_opts,
            }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        ext = format_type if format_type == "mp3" and HAS_FFMPEG else None
        if ext is None:
            for f in os.listdir(DOWNLOAD_DIR):
                if f.startswith(unique_name):
                    ext = f.split('.')[-1]
                    break
        filepath = os.path.join(DOWNLOAD_DIR, f"{unique_name}.{ext}")

        if os.path.exists(filepath):
            task["status"] = "completed"
            task["filepath"] = filepath
            task["filename"] = f"{task.get('title', 'video')}.{ext}"
        else:
            for f in os.listdir(DOWNLOAD_DIR):
                if f.startswith(unique_name):
                    filepath = os.path.join(DOWNLOAD_DIR, f)
                    task["status"] = "completed"
                    task["filepath"] = filepath
                    task["filename"] = f"{task.get('title', 'video')}.{f.split('.')[-1]}"
                    break
            else:
                task["status"] = "error"
                task["error"] = "Không tìm thấy file đã tải"
    except Exception as e:
        error_msg = str(e)
        if "Sign in" in error_msg or "bot" in error_msg:
            task["error"] = (
                "YouTube yêu cầu xác thực. Hãy đảm bảo bạn đã đăng nhập YouTube "
                "trên trình duyệt (Chrome/Edge/Firefox) rồi thử lại."
            )
        elif "Video unavailable" in error_msg:
            task["error"] = "Video không khả dụng hoặc bị giới hạn khu vực."
        elif "ffmpeg" in error_msg.lower():
            task["error"] = (
                "Cần cài FFmpeg để chuyển đổi định dạng. "
                "Tải tại: https://www.gyan.dev/ffmpeg/builds/"
            )
        else:
            task["error"] = error_msg
        task["status"] = "error"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/info", methods=["POST"])
def video_info():
    data = request.get_json()
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"error": "Vui lòng nhập URL"}), 400

    try:
        info = get_video_info(url)
        info["has_ffmpeg"] = HAS_FFMPEG
        return jsonify(info)
    except Exception as e:
        error_msg = str(e)
        if "Sign in" in error_msg or "bot" in error_msg:
            return jsonify({
                "error": "YouTube yêu cầu xác thực. Hãy đăng nhập YouTube "
                         "trên trình duyệt (Chrome/Edge/Firefox) rồi thử lại."
            }), 400
        return jsonify({"error": f"Không thể lấy thông tin video: {error_msg}"}), 400


@app.route("/api/download", methods=["POST"])
def start_download():
    data = request.get_json()
    url = data.get("url", "").strip()
    format_type = data.get("format", "mp3")

    if not url:
        return jsonify({"error": "Vui lòng nhập URL"}), 400

    if format_type not in ("mp3", "mp4"):
        return jsonify({"error": "Định dạng không hợp lệ"}), 400

    clean_old_files()

    task_id = str(uuid.uuid4())[:8]

    try:
        info = get_video_info(url)
        title = info.get("title", "video")
    except Exception:
        title = "video"

    download_tasks[task_id] = {
        "status": "starting",
        "progress": 0,
        "title": title,
        "format": format_type,
    }

    thread = threading.Thread(
        target=download_video, args=(task_id, url, format_type), daemon=True
    )
    thread.start()

    return jsonify({"task_id": task_id, "title": title})


@app.route("/api/status/<task_id>")
def task_status(task_id):
    task = download_tasks.get(task_id)
    if not task:
        return jsonify({"error": "Không tìm thấy task"}), 404

    return jsonify(
        {
            "status": task["status"],
            "progress": task.get("progress", 0),
            "error": task.get("error"),
        }
    )


@app.route("/api/file/<task_id>")
def download_file(task_id):
    task = download_tasks.get(task_id)
    if not task or task["status"] != "completed":
        return jsonify({"error": "File chưa sẵn sàng"}), 404

    filepath = task.get("filepath")
    if not filepath or not os.path.exists(filepath):
        return jsonify({"error": "File không tồn tại"}), 404

    return send_file(
        filepath,
        as_attachment=True,
        download_name=task.get("filename", "download"),
    )


if __name__ == "__main__":
    if not HAS_FFMPEG:
        print("WARNING: FFmpeg chua duoc cai dat!")
        print("  MP3: se tai am thanh goc (m4a/webm) thay vi chuyen doi sang mp3")
        print("  MP4: se tai video don (khong ghep video+audio rieng)")
        print("  De co chat luong tot nhat, hay cai FFmpeg:")
        print("  https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip")
        print()
    app.run(debug=True, host="0.0.0.0", port=5000)
