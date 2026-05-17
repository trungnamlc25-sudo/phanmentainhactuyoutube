# YouTube Downloader - Phần mềm tải nhạc từ YouTube

Ứng dụng web cho phép tải nhạc và video từ YouTube với định dạng MP3 hoặc MP4.

## Tính năng

- 🎵 Tải nhạc YouTube sang **MP3** (192kbps)
- 🎬 Tải video YouTube sang **MP4** (chất lượng cao)
- 🔍 Xem trước thông tin video trước khi tải
- 📊 Hiển thị tiến trình tải xuống
- 🎨 Giao diện tiếng Việt đẹp mắt, hỗ trợ mobile

## Yêu cầu

- Python 3.8+
- FFmpeg (để chuyển đổi định dạng)

## Cài đặt

### 1. Cài đặt FFmpeg

**Ubuntu/Debian:**
```bash
sudo apt-get install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Tải từ [ffmpeg.org](https://ffmpeg.org/download.html) và thêm vào PATH.

### 2. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### 3. Chạy ứng dụng

```bash
python app.py
```

Mở trình duyệt và truy cập: **http://localhost:5000**

## Hướng dẫn sử dụng

1. Mở ứng dụng tại `http://localhost:5000`
2. Dán link YouTube vào ô tìm kiếm
3. Nhấn **Tìm kiếm** để xem thông tin video
4. Chọn định dạng **MP3** (âm thanh) hoặc **MP4** (video)
5. Nhấn **Tải xuống** và chờ hoàn thành

## Cấu trúc dự án

```
phanmentainhactuyoutube/
├── app.py              # Flask backend
├── templates/
│   └── index.html      # Giao diện web
├── downloads/          # Thư mục chứa file tải (tự động tạo)
├── requirements.txt    # Dependencies
├── .gitignore
└── README.md
```

## Lưu ý

- File tải xuống sẽ tự động bị xóa sau 1 giờ
- Cần có kết nối internet để tải video
- Ứng dụng sử dụng `yt-dlp` - công cụ tải video mã nguồn mở
