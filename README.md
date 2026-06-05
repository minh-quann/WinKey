# ⌨️ WinKey Input Switcher

**WinKey** là công cụ dành cho môi trường **GNOME Desktop** trên Linux, cho phép bạn **giữ phím Super (phím Windows)** để tạm thời chuyển sang bộ gõ tiếng Anh. Khi thả phím, bộ gõ sẽ tự động quay về ngôn ngữ trước đó.

## ✨ Tính năng chính

- 🔄 **Chuyển đổi bộ gõ tạm thời**: Giữ phím Super → chuyển sang tiếng Anh, thả ra → quay về bộ gõ cũ
- 🖥️ **Tự động phát hiện Terminal**: Khi bạn focus vào ứng dụng terminal (GNOME Terminal, Kitty, Alacritty, Wezterm, Ptyxis, Tilix, Terminator,...), WinKey tự động chuyển sang tiếng Anh
- 🔔 **Tray icon**: Hiển thị biểu tượng trên system tray để theo dõi trạng thái
- 🌐 **Đa ngôn ngữ**: Hỗ trợ giao diện tiếng Việt và tiếng Anh
- ⚙️ **Tùy chỉnh linh hoạt**: Chọn bộ gõ mục tiêu, bật/tắt tự khởi động, thông báo, tray icon,...
- 🔗 **Tích hợp D-Bus**: Extension và GUI app giao tiếp với nhau qua D-Bus để phát hiện cửa sổ focus trên Wayland

## 📦 Yêu cầu hệ thống

- **GNOME Shell** phiên bản **45, 46, 47, 48, 49** hoặc **50**
- **Python 3** với các thư viện: `gi` (PyGObject), GTK4, Libadwaita
- **IBus** (nếu sử dụng bộ gõ IBus)

## 🛠️ Cài đặt

> ⚠️ **QUAN TRỌNG**: WinKey gồm **2 phần** cần cài đặt **song song** để hoạt động đầy đủ:
> 1. **GNOME Shell Extension** — xử lý sự kiện phím Super và chuyển đổi bộ gõ ở cấp shell
> 2. **GUI Application** — ứng dụng đồ họa để cấu hình, phát hiện terminal, và chạy daemon nền
>
> Nếu chỉ cài Extension mà không cài GUI, tính năng phát hiện terminal trên Wayland sẽ không hoạt động. Nếu chỉ cài GUI mà không cài Extension, việc chuyển đổi bộ gõ bằng phím Super sẽ không hoạt động.

---

### Bước 1: Cài đặt GNOME Shell Extension

#### Cách 1: Cài từ trang GNOME Extensions (khuyến nghị)

1. Truy cập [GNOME Extensions](https://extensions.gnome.org/) trên trình duyệt
2. Tìm kiếm **"WinKey Input Switcher"**
3. Bấm nút **Install** để cài đặt
4. Bật extension trong ứng dụng **Extensions** của GNOME

#### Cách 2: Cài thủ công từ mã nguồn

```bash
# Clone repository
git clone https://github.com/minh-quann/WinKey.git
cd WinKey

# Đóng gói extension thành file .zip
cd extension
gnome-extensions pack --force --extra-source=prefs.js

# Cài đặt extension
gnome-extensions install --force winkey@minh-quann.github.io.shell-extension.zip
```

Sau khi cài đặt, bạn cần **đăng xuất và đăng nhập lại** (hoặc nhấn `Alt+F2` rồi gõ `r` trên X11) để GNOME Shell nhận diện extension mới.

Cuối cùng, bật extension:
```bash
gnome-extensions enable winkey@minh-quann.github.io
```

Bạn cũng có thể vào **Cài đặt Extension** để tùy chỉnh:
- **Enable WinKey**: Bật/tắt tính năng chuyển đổi bộ gõ
- **English Input Index**: Chỉ số của bộ gõ tiếng Anh (0 = bộ gõ đầu tiên, 1 = thứ hai,...)

---

### Bước 2: Cài đặt GUI Application

```bash
# Nếu chưa clone repository ở bước 1
git clone https://github.com/minh-quann/WinKey.git
cd WinKey

# Chạy script cài đặt
./install.sh
```

Script `install.sh` sẽ thực hiện:
- Cài icon vào `~/.local/share/icons/`
- Tạo file `.desktop` trong `~/.local/share/applications/` để bạn mở WinKey từ Application Menu
- Hỏi bạn có muốn **tự khởi động cùng hệ thống** không → nhấn `y` để bật

> 💡 **Khuyến nghị**: Nhấn `y` khi được hỏi `Enable auto-start on login?` để ứng dụng WinKey chạy nền tự động mỗi khi bạn đăng nhập.

---

## 🚀 Sử dụng

### Khởi động ứng dụng

Sau khi cài đặt, bạn có thể mở **WinKey** bằng một trong các cách:

```bash
# Mở giao diện đồ họa
python3 winkey.py

# Hoặc chạy nền (không hiện cửa sổ)
python3 winkey.py --background
```

Hoặc tìm **WinKey** trong Application Menu của GNOME.

### Cách hoạt động

| Hành động | Kết quả |
|---|---|
| **Giữ phím Super** | Tạm thời chuyển sang bộ gõ tiếng Anh |
| **Thả phím Super** | Quay về bộ gõ bạn đang dùng trước đó |
| **Focus vào Terminal** | Tự động chuyển sang tiếng Anh |
| **Rời khỏi Terminal** | Tự động quay về bộ gõ trước đó |

### Cấu hình trong GUI

Mở ứng dụng WinKey, bạn sẽ thấy các tùy chọn:

- **Bật/Tắt WinKey**: Công tắc bật/tắt toàn bộ tính năng
- **Chọn bộ gõ tiếng Anh**: Danh sách các bộ gõ đã cài, chọn bộ gõ tiếng Anh mục tiêu
- **Ngôn ngữ giao diện**: Chuyển đổi giữa tiếng Việt và tiếng Anh
- **Tự khởi động**: Bật/tắt khởi động cùng hệ thống
- **Thông báo**: Bật/tắt thông báo khi chuyển đổi
- **Tray icon**: Hiển thị/ẩn biểu tượng trên system tray

---

## 🗑️ Gỡ cài đặt

### Gỡ GUI Application

```bash
cd WinKey
./uninstall.sh
```

Script này sẽ xóa file `.desktop`, autostart entry và icon. Thư mục mã nguồn vẫn được giữ lại.

### Gỡ GNOME Shell Extension

```bash
gnome-extensions uninstall winkey@minh-quann.github.io
```

Hoặc vào ứng dụng **Extensions** của GNOME → tìm **WinKey Input Switcher** → bấm **Gỡ cài đặt**.

---

## 📁 Cấu trúc dự án

```
WinKey/
├── extension/                  # GNOME Shell Extension
│   ├── extension.js            # Logic chính của extension
│   ├── prefs.js                # Giao diện cài đặt extension
│   ├── metadata.json           # Thông tin extension (tên, phiên bản, shell version)
│   └── schemas/                # GSettings schema
├── src/                        # GUI Application (Python + GTK4)
│   ├── app.py                  # Entry point ứng dụng GTK
│   ├── window.py               # Giao diện cửa sổ chính
│   ├── daemon.py               # Daemon lắng nghe phím Super
│   ├── input_source.py         # Quản lý bộ gõ (IBus/XKB)
│   ├── terminal_detector.py    # Phát hiện cửa sổ terminal
│   ├── settings.py             # Quản lý cấu hình (JSON)
│   ├── tray.py                 # System tray icon
│   ├── i18n.py                 # Đa ngôn ngữ
│   └── ui/                     # UI components
├── data/
│   └── icons/                  # Icon ứng dụng (SVG)
├── winkey.py                   # Script khởi chạy chính
├── install.sh                  # Script cài đặt
└── uninstall.sh                # Script gỡ cài đặt
```

---

## 🐛 Xử lý sự cố

| Vấn đề | Giải pháp |
|---|---|
| Extension không hiển thị sau khi cài | Đăng xuất và đăng nhập lại, hoặc restart GNOME Shell |
| Phím Super không chuyển bộ gõ | Kiểm tra extension đã bật trong ứng dụng Extensions, và `English Input Index` đúng |
| Terminal không tự chuyển tiếng Anh | Đảm bảo GUI app đang chạy (kiểm tra tray icon hoặc chạy `python3 winkey.py --background`) |
| Lỗi D-Bus connection | Extension cần được bật trước, sau đó khởi động GUI app |

---

## 📄 Giấy phép

MIT License
