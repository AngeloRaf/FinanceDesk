"""
FinanceDesk v1.1 — main.py
"""

import sys
import os
import webview
from pathlib import Path

BASE_DIR   = Path(__file__).parent
UI_DIR     = BASE_DIR / "ui"
LOGIN_HTML = UI_DIR / "login.html"
APP_HTML   = UI_DIR / "FinanceDesk_v1_1.html"

sys.path.insert(0, str(BASE_DIR))
from ui.api_bridge import ApiBridge
from core.db_manager import init_db
from core.security import is_password_set


def chemin_vers_url(path: Path) -> str:
    """Convertit un chemin Windows en URL file:// compatible PyWebView."""
    resolved = path.resolve()
    url = resolved.as_posix()
    return f"file:///{url}"


def main():
    init_db()
    api = ApiBridge()

    html_path = LOGIN_HTML if is_password_set() else APP_HTML
    start_url = chemin_vers_url(html_path)

    window = webview.create_window(
        title       = "FinanceDesk v1.1",
        url         = start_url,
        js_api      = api,
        width       = 1280,
        height      = 820,
        min_size    = (1024, 640),
        resizable   = True,
        text_select = False,
    )

    webview.start(debug=False)


if __name__ == "__main__":
    main()