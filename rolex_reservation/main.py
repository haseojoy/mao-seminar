"""
Rolex Boutique LEXIA - Reservation Auto-Submit System
Usage:
  python main.py                  -> Apply to all enabled stores
  python main.py --loc ginza      -> Apply to specified store only
  python main.py --dry-run        -> Fill form but skip submission
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError


SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def next_saturday() -> date:
    today = date.today()
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0:
        days_until_saturday = 7
    return today + timedelta(days=days_until_saturday)


async def screenshot(page: Page, name: str) -> None:
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    path = SCREENSHOT_DIR / f"{name}.png"
    await page.screenshot(path=str(path), full_page=True)
    print(f"  [screenshot] {path}")


async def wait_and_click(page: Page, selectors: list[str], description: str, timeout: int = 10000) -> bool:
    """Try multiple selectors; click the first one found."""
    for sel in selectors:
        try:
            locator = page.locator(sel).first
            await locator.wait_for(state="visible", timeout=timeout)
            await locator.click()
            print(f"  [click] {description} (selector: {sel})")
            return True
        except Exception:
            continue
    print(f"  [warning] Could not find element: {description}")
    return False


async def wait_and_fill(page: Page, selectors: list[str], value: str, description: str) -> bool:
    """Try multiple selectors; fill the first one found."""
    for sel in selectors:
        try:
            locator = page.locator(sel).first
            await locator.wait_for(state="visible", timeout=8000)
            await locator.fill(value)
            print(f"  [fill] {description} = {value}")
            return True
        except Exception:
            continue
    print(f"  [warning] Could not fill field: {description}")
    return False


async def select_option(page: Page, selectors: list[str], value: str, description: str) -> bool:
    """Try to select an option by value or label."""
    for sel in selectors:
        try:
            locator = page.locator(sel).first
            await locator.wait_for(state="visible", timeout=8000)
            try:
                await locator.select_option(value=value)
            except Exception:
                await locator.select_option(label=value)
            print(f"  [select] {description} = {value}")
            return True
        except Exception:
            continue
    print(f"  [warning] Could not select option: {description}")
    return False


async def navigate_calendar_to_month(page: Page, target_date: date) -> None:
    """Navigate calendar to the month containing target_date."""
    for _ in range(3):  # max 3 months forward
        # Read current month/year from calendar header
        month_texts = [
            ".calendar-header", ".calendar__header", ".fc-toolbar-title",
            "[class*='calendar'][class*='header']", "[class*='month'][class*='year']",
            "table caption", ".datepicker-header", ".ui-datepicker-title",
        ]
        current_month_text = ""
        for sel in month_texts:
            try:
                el = page.locator(sel).first
                current_month_text = await el.inner_text(timeout=3000)
                if current_month_text:
                    break
            except Exception:
                continue

        # Check if we need to advance
        target_month_jp = f"{target_date.month}月"
        target_year = str(target_date.year)
        if target_month_jp in current_month_text and target_year in current_month_text:
            break
        # Try English month names too
        import calendar as cal_mod
        english_months = [cal_mod.month_name[target_date.month], cal_mod.month_abbr[target_date.month]]
        if any(m in current_month_text for m in english_months) and target_year in current_month_text:
            break

        # Click "next" button
        next_btns = [
            "button:has-text('次へ')", "button:has-text('>')", "button:has-text('▶')",
            ".calendar-next", ".next-month", "[aria-label='Next month']",
            "[aria-label='next']", ".fc-next-button", ".datepicker-next",
            "button[class*='next']", "a[class*='next']",
        ]
        clicked = await wait_and_click(page, next_btns, "カレンダー次へ", timeout=5000)
        if not clicked:
            break
        await page.wait_for_timeout(500)


async def click_calendar_date(page: Page, target_date: date) -> bool:
    """Click the target date cell in a calendar."""
    await navigate_calendar_to_month(page, target_date)
    await page.wait_for_timeout(300)

    day = target_date.day
    month = target_date.month
    year = target_date.year

    # Try various selector strategies
    date_selectors = [
        # data-date attributes (YYYY-MM-DD or similar)
        f"[data-date='{target_date.isoformat()}']",
        f"[data-date='{year}-{month:02d}-{day:02d}']",
        f"[data-day='{day}']",
        f"[data-date*='{year}/{month:02d}/{day:02d}']",
        # text-based: find a cell with exact day number that is not disabled/past
        f"td:not(.disabled):not(.past):not([class*='disabled']):not([class*='past']) >> text='{day}'",
        f"button:not(:disabled) >> text='{day}'",
        f".day:not(.disabled):not(.past) >> text='{day}'",
        f"[class*='date']:not([class*='disabled']):not([class*='past']) >> text='{day}'",
    ]
    for sel in date_selectors:
        try:
            locator = page.locator(sel)
            count = await locator.count()
            if count == 0:
                continue
            # Pick the one that matches exactly (avoid clicking "1" when "11" or "21" exists)
            for i in range(count):
                item = locator.nth(i)
                text = (await item.inner_text(timeout=2000)).strip()
                if text == str(day):
                    await item.click()
                    print(f"  [click] カレンダー日付 {target_date} (selector: {sel})")
                    return True
        except Exception:
            continue

    # Fallback: aria-label containing the date
    aria_selectors = [
        f"[aria-label*='{year}年{month}月{day}日']",
        f"[aria-label*='{month}/{day}/{year}']",
        f"[aria-label*='{year}-{month:02d}-{day:02d}']",
    ]
    for sel in aria_selectors:
        try:
            await page.locator(sel).first.click(timeout=5000)
            print(f"  [click] カレンダー日付 {target_date} via aria-label")
            return True
        except Exception:
            continue

    print(f"  [warning] カレンダーで {target_date} が見つかりませんでした")
    return False


async def click_time_slot(page: Page, time_str: str = "11:00") -> bool:
    """Click the time slot matching time_str."""
    await page.wait_for_timeout(500)
    selectors = [
        f"text='{time_str}'",
        f"[data-time='{time_str}']",
        f"[data-time='{time_str}:00']",
        f"button:has-text('{time_str}')",
        f"td:has-text('{time_str}')",
        f"li:has-text('{time_str}')",
        f"[class*='time']:has-text('{time_str}')",
        f"[class*='slot']:has-text('{time_str}')",
    ]
    return await wait_and_click(page, selectors, f"時間帯 {time_str}", timeout=8000)


async def fill_personal_info(page: Page, info: dict) -> None:
    """Fill in personal information form fields."""
    await page.wait_for_timeout(500)

    # Last name
    await wait_and_fill(page, [
        "input[name*='last'][name*='name']", "input[name='sei']", "input[name='lastName']",
        "input[name='family_name']", "input[placeholder*='姓']", "input[placeholder*='苗字']",
        "input[placeholder*='セイ']",
        "//label[contains(text(),'姓')]/following-sibling::input",
        "//label[contains(text(),'姓')]/..//input",
    ], info["last_name"], "姓")

    # First name
    await wait_and_fill(page, [
        "input[name*='first'][name*='name']", "input[name='mei']", "input[name='firstName']",
        "input[name='given_name']", "input[placeholder*='名']", "input[placeholder*='メイ']",
        "//label[contains(text(),'名')]/following-sibling::input",
        "//label[contains(text(),'名')]/..//input",
    ], info["first_name"], "名")

    # Last name kana
    await wait_and_fill(page, [
        "input[name*='last'][name*='kana']", "input[name='sei_kana']", "input[name='lastNameKana']",
        "input[name='family_name_kana']", "input[placeholder*='セイ']", "input[placeholder*='カナ'][placeholder*='姓']",
        "//label[contains(text(),'セイ')]/..//input",
        "//label[contains(text(),'フリガナ')][contains(text(),'姓')]/..//input",
    ], info["last_name_kana"], "セイ（カナ）")

    # First name kana
    await wait_and_fill(page, [
        "input[name*='first'][name*='kana']", "input[name='mei_kana']", "input[name='firstNameKana']",
        "input[name='given_name_kana']", "input[placeholder*='メイ']", "input[placeholder*='カナ'][placeholder*='名']",
        "//label[contains(text(),'メイ')]/..//input",
        "//label[contains(text(),'フリガナ')][contains(text(),'名')]/..//input",
    ], info["first_name_kana"], "メイ（カナ）")

    # Email
    await wait_and_fill(page, [
        "input[type='email']", "input[name='email']", "input[name='mail']",
        "input[placeholder*='メール']", "input[placeholder*='mail']", "input[placeholder*='Mail']",
    ], info["email"], "メールアドレス")

    # Phone
    await wait_and_fill(page, [
        "input[type='tel']", "input[name='phone']", "input[name='tel']",
        "input[name='telephone']", "input[placeholder*='電話']", "input[placeholder*='tel']",
        "input[placeholder*='Tel']",
    ], info["phone"], "電話番号")

    # Gender
    gender_value = info.get("gender", "male")
    gender_map = {"male": ["male", "男性", "man", "1"], "female": ["female", "女性", "woman", "2"]}
    gender_values = gender_map.get(gender_value, [gender_value])

    gender_filled = False
    for val in gender_values:
        try:
            radio = page.locator(f"input[type='radio'][value='{val}']").first
            await radio.click(timeout=3000)
            print(f"  [click] 性別ラジオボタン = {val}")
            gender_filled = True
            break
        except Exception:
            continue

    if not gender_filled:
        # Try select dropdown
        select_tried = await select_option(page, [
            "select[name='gender']", "select[name='sex']",
        ], gender_values[0], "性別セレクト")
        if not select_tried:
            print("  [warning] 性別フィールドが見つかりませんでした")


async def apply_store(page: Page, store_key: str, store_cfg: dict, info: dict,
                      target_date: date, dry_run: bool) -> dict:
    """Run the full reservation flow for one store. Returns result dict."""
    result = {"store": store_cfg["name"], "status": "unknown", "error": None}
    prefix = f"{store_key}_{target_date}"

    try:
        print(f"\n{'='*60}")
        print(f"[{store_cfg['name']}] 申し込み開始")
        print(f"  URL: {store_cfg['url']}")
        print(f"  対象日: {target_date} 11:00")
        if dry_run:
            print("  *** DRY-RUN モード（送信しない） ***")

        # 1. Navigate
        await page.goto(store_cfg["url"], wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(1500)
        await screenshot(page, f"{prefix}_01_loaded")

        # 2. Omotesando: click "事前来店予約"
        if store_cfg.get("select_visit_reservation"):
            clicked = await wait_and_click(page, [
                "text='事前来店予約'",
                "button:has-text('事前来店予約')",
                "a:has-text('事前来店予約')",
                "[class*='reservation']:has-text('事前来店予約')",
            ], "事前来店予約ボタン", timeout=10000)
            if not clicked:
                raise RuntimeError("「事前来店予約」ボタンが見つかりませんでした")
            await page.wait_for_timeout(1000)
            await screenshot(page, f"{prefix}_02_visit_reservation_clicked")

        # 3. Calendar: select next Saturday
        calendar_found = await click_calendar_date(page, target_date)
        if not calendar_found:
            await screenshot(page, f"{prefix}_err_no_calendar")
            raise RuntimeError(f"カレンダーで {target_date} をクリックできませんでした")
        await page.wait_for_timeout(800)
        await screenshot(page, f"{prefix}_03_date_selected")

        # 4. Time slot: 11:00
        time_found = await click_time_slot(page, "11:00")
        if not time_found:
            await screenshot(page, f"{prefix}_err_no_timeslot")
            raise RuntimeError("11:00 の時間枠が見つかりませんでした")
        await page.wait_for_timeout(800)
        await screenshot(page, f"{prefix}_04_time_selected")

        # 5. Fill personal info
        await fill_personal_info(page, info)
        await page.wait_for_timeout(500)
        await screenshot(page, f"{prefix}_05_form_filled")

        # 6. Click "次へ" (confirmation page)
        next_clicked = await wait_and_click(page, [
            "button:has-text('次へ')", "input[type='submit'][value*='次へ']",
            "button:has-text('確認')", "button:has-text('入力内容確認')",
            "button[type='submit']:has-text('次')",
            "a:has-text('次へ')",
        ], "次へボタン", timeout=10000)
        if not next_clicked:
            await screenshot(page, f"{prefix}_err_no_next_btn")
            raise RuntimeError("「次へ」ボタンが見つかりませんでした")
        await page.wait_for_timeout(1500)
        await screenshot(page, f"{prefix}_06_confirmation_page")

        if dry_run:
            print(f"  [dry-run] 送信スキップ")
            result["status"] = "dry-run"
            return result

        # 7. Submit
        submit_clicked = await wait_and_click(page, [
            "button:has-text('送信')", "input[type='submit'][value*='送信']",
            "button:has-text('予約する')", "button:has-text('申し込む')",
            "button:has-text('申し込み')", "button[type='submit']:has-text('確定')",
            "button:has-text('完了')", "button[type='submit']",
        ], "送信ボタン", timeout=10000)
        if not submit_clicked:
            await screenshot(page, f"{prefix}_err_no_submit_btn")
            raise RuntimeError("送信ボタンが見つかりませんでした")
        await page.wait_for_timeout(2000)
        await screenshot(page, f"{prefix}_07_submitted")

        result["status"] = "success"
        print(f"  [OK] 送信完了")

    except PlaywrightTimeoutError as e:
        result["status"] = "error"
        result["error"] = f"タイムアウト: {e}"
        print(f"  [ERROR] タイムアウト: {e}")
        try:
            await screenshot(page, f"{prefix}_err_timeout")
        except Exception:
            pass

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        print(f"  [ERROR] {e}")
        try:
            await screenshot(page, f"{prefix}_err_exception")
        except Exception:
            pass

    return result


async def main_async(target_stores: Optional[list[str]], dry_run: bool) -> None:
    config = load_config()
    info = config["personal_info"]
    stores = config["stores"]
    target_date = next_saturday()

    print(f"次の土曜日: {target_date}")
    print(f"Dry-run: {dry_run}")

    # Filter stores
    if target_stores:
        stores = {k: v for k, v in stores.items() if k in target_stores}
    else:
        stores = {k: v for k, v in stores.items() if v.get("enabled", False)}

    if not stores:
        print("対象店舗がありません。config.json の enabled フラグを確認してください。")
        sys.exit(1)

    results = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="ja-JP",
        )

        for store_key, store_cfg in stores.items():
            page = await context.new_page()
            result = await apply_store(page, store_key, store_cfg, info, target_date, dry_run)
            results.append(result)
            await page.close()

        await browser.close()

    # Summary
    print(f"\n{'='*60}")
    print("結果サマリー")
    print(f"{'='*60}")
    for r in results:
        status_label = {"success": "✓ 成功", "dry-run": "○ ドライラン", "error": "✗ エラー"}.get(r["status"], r["status"])
        print(f"  {r['store']}: {status_label}")
        if r.get("error"):
            print(f"    └ {r['error']}")
    print(f"{'='*60}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rolex LEXIA 予約自動申し込みシステム")
    parser.add_argument(
        "--loc",
        metavar="STORE_KEY",
        help="対象店舗キー (shinjuku / ginza / omotesando / osaka_hilton / nagoya)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="フォーム入力まで行い送信はしない",
    )
    args = parser.parse_args()

    target_stores = [args.loc] if args.loc else None
    asyncio.run(main_async(target_stores, args.dry_run))


if __name__ == "__main__":
    main()
