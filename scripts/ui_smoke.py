"""不送出模型請求的 Gradio 瀏覽器煙霧測試。"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright


ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "ui"


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1050})
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.goto("http://127.0.0.1:7860", wait_until="networkidle")
        page.get_by_role("heading", name="長照額度，算清楚再決定。").wait_for()
        assert page.get_by_text("Python 負責每一塊錢").is_visible()
        assert page.get_by_label("模型模式").is_visible()
        assert page.get_by_role("button", name="送出並檢查缺漏").is_visible()
        assert page.get_by_text("尚未產生報告草稿。").is_visible()
        page.get_by_label("並列 2022 舊制比較").check()
        assert page.get_by_label("並列 2022 舊制比較").is_checked()
        page.screenshot(path=ARTIFACT_DIR / "gradio-desktop.png", full_page=True)

        page.set_viewport_size({"width": 390, "height": 844})
        page.get_by_role("heading", name="長照額度，算清楚再決定。").wait_for()
        page.screenshot(path=ARTIFACT_DIR / "gradio-mobile.png", full_page=True)
        browser.close()
    if console_errors:
        raise AssertionError(f"browser console errors: {console_errors}")
    print("UI_SMOKE_OK")
    print(ARTIFACT_DIR / "gradio-desktop.png")
    print(ARTIFACT_DIR / "gradio-mobile.png")


if __name__ == "__main__":
    main()
