"""不送出模型請求的 Gradio 瀏覽器煙霧測試。"""

from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "ui"
SHOWCASE_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "assets"
    / "gradio-showcase.png"
)
BASE_URL = os.getenv("UI_SMOKE_URL", "http://127.0.0.1:7860")
TEST_CONVERSATION = os.getenv("UI_SMOKE_TEST_CONVERSATION") == "1"
TEST_APPROVAL = os.getenv("UI_SMOKE_TEST_APPROVAL") == "1"
PUBLISH_SHOWCASE = os.getenv("UI_SMOKE_PUBLISH_SHOWCASE") == "1"


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    requested_urls: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1050})
        page.on("request", lambda request: requested_urls.append(request.url))
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        # Gradio 6 會維持 SSR / queue 連線，頁面可能永遠達不到 networkidle；
        # 以 DOM 完成後的產品標題作為可互動就緒條件。
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60_000)
        heading = page.get_by_role("heading", name="長照 2.0 資格與補助初步試算")
        heading.wait_for(timeout=60_000)
        assert not page.get_by_text(
            "用對話補齊必要資料；資格與金額由確定性工具計算，報告發布前由你確認。",
            exact=True,
        ).is_visible()
        assert page.locator(".trust-item").count() == 0
        assert page.locator(".how-to").get_by_text(
            "照這 4 步操作", exact=True
        ).is_visible()
        assert page.get_by_text("一次選一位家人", exact=False).is_visible()
        assert page.get_by_text("在下方欄位打字", exact=False).is_visible()
        assert page.get_by_text("按「開始資格初篩」", exact=False).is_visible()
        assert page.get_by_text("檢查試算報告", exact=False).is_visible()
        advanced_settings = page.get_by_text(
            "進階設定（一般不用調整）", exact=True
        )
        assert advanced_settings.is_visible()
        assert float(
            advanced_settings.evaluate(
                "el => getComputedStyle(el).fontSize.slice(0, -2)"
            )
        ) >= 19
        assert not page.get_by_label("模型模式").is_visible()
        situation_input = page.get_by_label("先描述這位家人的情況")
        assert situation_input.is_visible()
        followup_input = page.get_by_label("輸入回答")
        assert not followup_input.is_visible()
        assert page.locator("#onboarding-section").is_visible()
        assert page.get_by_role("button", name="開始資格初篩").is_visible()
        assert not page.get_by_role("button", name="送出回答").is_visible()
        assert not page.get_by_role("button", name="重新評估另一位家人").is_visible()
        assert not page.locator("#conversation-section").is_visible()
        assert not page.locator("#report-section").is_visible()
        assert not page.get_by_text("請先說明家人的年齡", exact=False).is_visible()
        assert not page.get_by_text("可稽核", exact=True).is_visible()
        assert float(heading.evaluate("el => getComputedStyle(el).fontSize.slice(0, -2)")) >= 32
        assert float(
            situation_input.evaluate(
                "el => getComputedStyle(el).fontSize.slice(0, -2)"
            )
        ) >= 19
        advanced_settings.click()
        provider_input = page.get_by_label("模型模式")
        provider_input.wait_for(state="visible")
        assert page.locator("#advanced-settings").evaluate(
            "el => getComputedStyle(el).overflowX"
        ) not in {"auto", "scroll"}
        legacy_toggle = page.get_by_label("同時顯示 2022 舊制")
        legacy_toggle.check()
        assert legacy_toggle.is_checked()
        assert legacy_toggle.bounding_box()["width"] >= 20
        assert legacy_toggle.bounding_box()["height"] >= 20
        assert legacy_toggle.bounding_box()["height"] <= 24
        legacy_text = page.locator("#legacy-toggle").get_by_text(
            "同時顯示 2022 舊制", exact=True
        ).last
        assert legacy_text.is_visible()
        assert float(
            legacy_text.evaluate(
                "el => getComputedStyle(el).fontSize.slice(0, -2)"
            )
        ) >= 20
        assert float(
            legacy_text.evaluate("el => getComputedStyle(el).fontWeight")
        ) >= 700
        assert float(
            provider_input.evaluate("el => getComputedStyle(el).fontSize.slice(0, -2)")
        ) >= 19
        page.locator("#provider-select").click()
        provider_options = page.locator('[role="option"]')
        provider_options.first.wait_for()
        assert provider_options.count() >= 3
        assert all(
            float(size) >= 19
            for size in provider_options.evaluate_all(
                "items => items.map(el => getComputedStyle(el).fontSize.slice(0, -2))"
            )
        )
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)
        page.screenshot(
            path=ARTIFACT_DIR / "gradio-settings.png", full_page=True
        )
        legacy_toggle.uncheck()
        advanced_settings.click()
        heading.click()
        header_box = page.locator(".app-header").bounding_box()
        page_text = page.locator("body").inner_text()
        assert page.locator("#rule-audit-status").count() == 0
        assert "法規快照 2026-07-23.1 已核准" not in page_text
        assert "最後成功稽核" not in page_text
        assert "4/4 官方來源一致" not in page_text
        assert "sha256" not in page_text.lower()
        assert "semantic_fingerprint" not in page_text.lower()
        assert "extractor" not in page_text.lower()
        how_to_box = page.locator(".how-to").bounding_box()
        assert header_box is not None and how_to_box is not None
        header_to_how_to_gap = how_to_box["y"] - (
            header_box["y"] + header_box["height"]
        )
        assert 0 <= header_to_how_to_gap <= 32, (
            f"how-to is detached from header: {header_to_how_to_gap}px"
        )
        assert not any("law.moj.gov.tw" in url for url in requested_urls)
        main_box = page.locator(".main-surface").bounding_box()
        assert main_box is not None and main_box["height"] <= 600
        page.screenshot(path=ARTIFACT_DIR / "gradio-desktop.png", full_page=True)

        page.set_viewport_size({"width": 390, "height": 844})
        heading.wait_for()
        assert float(heading.evaluate("el => getComputedStyle(el).fontSize.slice(0, -2)")) >= 28
        assert page.evaluate(
            "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
        )
        assert situation_input.is_visible()
        assert not page.locator("#conversation-section").is_visible()
        assert not page.locator("#report-section").is_visible()
        page.screenshot(path=ARTIFACT_DIR / "gradio-mobile.png", full_page=True)

        if TEST_APPROVAL:
            page.set_viewport_size({"width": 1440, "height": 1050})
            situation_input.fill("家人 75 歲，已有正式 CMS 第 4 級，屬一般戶。")
            page.get_by_role("button", name="開始資格初篩").click()
            report = page.locator("#report-preview")
            report.get_by_text("長照服務資格與補助初步建議書", exact=True).wait_for()
            approve_button = page.get_by_role("button", name="核准並發布")
            reject_button = page.get_by_role("button", name="拒絕並繼續修正")
            assert approve_button.is_visible()
            assert reject_button.is_visible()
            approve_button.click()
            approved_status = page.get_by_text(
                "報告已核准；發布內容與校閱草稿逐字一致。", exact=True
            )
            approved_status.wait_for()
            published_button = page.get_by_role("button", name="已核准並發布")
            assert published_button.is_visible()
            assert published_button.is_disabled()
            assert not reject_button.is_visible()
            assert report.get_by_text("NT$ 15,120", exact=False).is_visible()
            assert report.get_by_text("NT$ 2,880", exact=False).is_visible()
            assert page.get_by_text("common.error", exact=True).count() == 0
            page.screenshot(
                path=ARTIFACT_DIR / "gradio-approved.png", full_page=True
            )
        elif TEST_CONVERSATION:
            page.set_viewport_size({"width": 1440, "height": 1050})
            situation_input.fill(
                "我阿公84歲，太老了不能騎機車，只能騎腳踏車，有攝護腺癌"
            )
            page.get_by_role("button", name="開始資格初篩").click()
            conversation = page.locator("#conversation")
            conversation.wait_for(state="visible")
            reply = conversation.get_by_text(
                "收到，已記下這位家人 84 歲", exact=False
            )
            reply.wait_for()
            assert conversation.get_by_text(
                "我阿公84歲，太老了不能騎機車", exact=False
            ).is_visible()
            assert conversation.get_by_text("年齡或疾病名稱", exact=False).is_visible()
            assert not conversation.get_by_text(
                "先選其中一位", exact=False
            ).is_visible()
            assert conversation.locator(".message").count() >= 2
            assert not page.locator("#onboarding-section").is_visible()
            assert not situation_input.is_visible()
            assert not page.get_by_role("button", name="開始資格初篩").is_visible()
            conversation_guide = page.locator("#conversation-guide")
            assert conversation_guide.is_visible()
            assert conversation_guide.get_by_text(
                "照這 4 步操作", exact=True
            ).is_visible()
            assert conversation_guide.get_by_text(
                "看最新問題", exact=True
            ).is_visible()
            assert conversation_guide.get_by_text(
                "在下方回答", exact=True
            ).is_visible()
            assert conversation_guide.get_by_text(
                "不知道就說「不知道」", exact=True
            ).is_visible()
            assert conversation_guide.get_by_text(
                "資料齊全後確認報告", exact=True
            ).is_visible()
            desktop_guide_box = conversation_guide.bounding_box()
            assert desktop_guide_box is not None
            assert desktop_guide_box["height"] <= 120
            restart_button = page.get_by_role(
                "button", name="重新評估另一位家人"
            )
            assert restart_button.is_visible()
            assert float(
                restart_button.evaluate(
                    "el => getComputedStyle(el).borderTopWidth.slice(0, -2)"
                )
            ) >= 2
            assert followup_input.is_visible()
            followup_action = page.locator("#followup-action")
            assert followup_action.is_visible()
            assert followup_action.get_by_text(
                "繼續對話", exact=False
            ).is_visible()
            assert followup_action.get_by_text(
                "不知道的項目可以回答", exact=False
            ).is_visible()
            assert "**" not in (followup_action.text_content() or "")
            page.wait_for_function(
                "document.querySelector('#followup-input textarea') === "
                "document.activeElement"
            )
            followup_button = page.get_by_role("button", name="送出回答")
            assert followup_button.is_visible()
            conversation_box = conversation.bounding_box()
            followup_box = followup_action.bounding_box()
            assert conversation_box is not None and followup_box is not None
            followup_gap = followup_box["y"] - (
                conversation_box["y"] + conversation_box["height"]
            )
            assert 0 <= followup_gap <= 24, (
                f"follow-up composer is detached from the chat: {followup_gap}px"
            )
            assert not page.locator(".status-strip").is_visible()
            followup_input.fill("洗澡和穿衣需要協助，已經 8 個月，其他都可以自己來")
            followup_button.click()
            page.wait_for_timeout(3000)
            next_question = conversation.get_by_text("原住民", exact=False)
            next_question.wait_for()
            assert conversation.get_by_text("住宿式機構", exact=False).is_visible()
            assert conversation.get_by_text(
                "洗澡和穿衣需要協助", exact=False
            ).is_visible()
            assert followup_input.is_visible()
            assert followup_input.input_value() == ""
            page.wait_for_function(
                "document.querySelector('#followup-input textarea') === "
                "document.activeElement"
            )
            assert followup_button.is_visible()
            assert conversation.is_visible()
            if PUBLISH_SHOWCASE:
                SHOWCASE_PATH.parent.mkdir(parents=True, exist_ok=True)
                page.set_viewport_size({"width": 1440, "height": 760})
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(250)
                page.screenshot(path=SHOWCASE_PATH, full_page=False)
            page.screenshot(
                path=ARTIFACT_DIR / "gradio-conversation.png", full_page=True
            )
            page.set_viewport_size({"width": 390, "height": 844})
            assert conversation.is_visible()
            assert followup_input.is_visible()
            assert conversation_guide.is_visible()
            mobile_guide_box = conversation_guide.bounding_box()
            assert mobile_guide_box is not None
            assert mobile_guide_box["height"] <= 190
            assert page.evaluate(
                "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
            )
            page.screenshot(
                path=ARTIFACT_DIR / "gradio-conversation-mobile.png",
                full_page=True,
            )
        browser.close()
    if console_errors:
        raise AssertionError(f"browser console errors: {console_errors}")
    print("UI_SMOKE_OK")
    print(ARTIFACT_DIR / "gradio-desktop.png")
    print(ARTIFACT_DIR / "gradio-mobile.png")
    print(ARTIFACT_DIR / "gradio-settings.png")
    if TEST_CONVERSATION:
        print(ARTIFACT_DIR / "gradio-conversation.png")
        print(ARTIFACT_DIR / "gradio-conversation-mobile.png")
        if PUBLISH_SHOWCASE:
            print(SHOWCASE_PATH)
    if TEST_APPROVAL:
        print(ARTIFACT_DIR / "gradio-approved.png")


if __name__ == "__main__":
    main()
