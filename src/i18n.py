"""
Internationalization (i18n) module for WinKey.
Supports English and Vietnamese.
"""

from typing import TypedDict


class Translations(TypedDict):
    """All translatable strings."""
    # Window
    app_title: str
    app_subtitle: str

    # Status card
    status_title: str
    service: str
    running: str
    stopped: str
    times_switched: str
    reset_counter: str
    current_input: str
    detecting: str
    already_english: str

    # Sources card
    target_source_title: str
    target_source_desc: str
    no_sources: str
    no_sources_hint: str

    # Settings card
    options_title: str
    start_on_login: str
    start_on_login_desc: str
    show_notifications: str
    show_notifications_desc: str
    language: str
    language_desc: str

    # About
    about_comments: str

    # Errors
    error: str
    no_devices: str
    no_devices_hint: str
    open_devices_fail: str


LANG_EN: Translations = {
    "app_title": "WinKey",
    "app_subtitle": "Super Key Input Switcher",

    "status_title": "Status",
    "service": "Service",
    "running": "Running",
    "stopped": "Stopped",
    "times_switched": "Times switched",
    "reset_counter": "Reset counter",
    "current_input": "Current input",
    "detecting": "Detecting...",
    "already_english": "Already English",

    "target_source_title": "Target English Source",
    "target_source_desc": "Select which input source to switch to when holding Super",
    "no_sources": "No input sources found",
    "no_sources_hint": "Configure input sources in GNOME Settings",

    "options_title": "Options",
    "start_on_login": "Start on login",
    "start_on_login_desc": "Automatically start WinKey when you log in",
    "show_notifications": "Show notifications",
    "show_notifications_desc": "Notify when input source changes",
    "language": "Language",
    "language_desc": "Application display language",

    "about_comments": "Hold Super key to temporarily switch to English input.\nRelease to go back to your previous input source.",

    "error": "Error",
    "no_devices": "No keyboard devices found. Is user in 'input' group?",
    "no_devices_hint": "Run: sudo usermod -aG input $USER",
    "open_devices_fail": "Failed to open any keyboard devices.",
}


LANG_VI: Translations = {
    "app_title": "WinKey",
    "app_subtitle": "Chuyển Đổi Nguồn Nhập Bằng Phím Super",

    "status_title": "Trạng thái",
    "service": "Dịch vụ",
    "running": "Đang chạy",
    "stopped": "Đã dừng",
    "times_switched": "Số lần chuyển",
    "reset_counter": "Đặt lại bộ đếm",
    "current_input": "Nguồn nhập hiện tại",
    "detecting": "Đang phát hiện...",
    "already_english": "Đã là tiếng Anh",

    "target_source_title": "Nguồn nhập tiếng Anh",
    "target_source_desc": "Chọn nguồn nhập sẽ chuyển sang khi giữ phím Super",
    "no_sources": "Không tìm thấy nguồn nhập",
    "no_sources_hint": "Cấu hình nguồn nhập trong Cài đặt GNOME",

    "options_title": "Tùy chọn",
    "start_on_login": "Khởi động cùng hệ thống",
    "start_on_login_desc": "Tự động chạy WinKey khi đăng nhập",
    "show_notifications": "Hiện thông báo",
    "show_notifications_desc": "Thông báo khi nguồn nhập thay đổi",
    "language": "Ngôn ngữ",
    "language_desc": "Ngôn ngữ hiển thị của ứng dụng",

    "about_comments": "Giữ phím Super để tạm thời chuyển sang nhập tiếng Anh.\nNhả ra để quay về nguồn nhập trước đó.",

    "error": "Lỗi",
    "no_devices": "Không tìm thấy thiết bị bàn phím. Người dùng có trong nhóm 'input' không?",
    "no_devices_hint": "Chạy: sudo usermod -aG input $USER",
    "open_devices_fail": "Không thể mở bất kỳ thiết bị bàn phím nào.",
}


LANGUAGES: dict[str, Translations] = {
    "en": LANG_EN,
    "vi": LANG_VI,
}

LANGUAGE_DISPLAY_NAMES: dict[str, str] = {
    "en": "English",
    "vi": "Tiếng Việt",
}


def get_translations(lang_code: str) -> Translations:
    """Get translations for a language code. Falls back to English."""
    return LANGUAGES.get(lang_code, LANG_EN)
