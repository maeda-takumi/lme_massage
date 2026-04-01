from __future__ import annotations

import re
import time
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .db import get_connection

BASE_URL = "https://step.lme.jp/"
DT_RE = re.compile(r"(\d{4}[./-]\d{2}[./-]\d{2})\s+(\d{2}:\d{2})(?::\d{2})?")


def _clean_display_name(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    cleaned = raw.replace('"', "").strip()
    return cleaned or None


def fetch_user_detail_info(driver, href, timeout=12):
    detail_url = urljoin(BASE_URL, href)
    original_handle = driver.current_window_handle
    before_handles = set(driver.window_handles)

    driver.execute_script("window.open(arguments[0], '_blank');", detail_url)

    WebDriverWait(driver, timeout).until(
        lambda d: len(set(d.window_handles) - before_handles) == 1
    )
    new_handle = list(set(driver.window_handles) - before_handles)[0]
    driver.switch_to.window(new_handle)

    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.tbl_info_df"))
        )

        raw = None
        display_name = None

        display_name_elem = driver.find_elements(By.CSS_SELECTOR, "#show_real_info_custom div.title-bg")
        if display_name_elem:
            display_name = _clean_display_name(display_name_elem[0].text)

        els = driver.find_elements(
            By.XPATH,
            "//table[contains(@class,'tbl_info_df')]"
            "//td[contains(normalize-space(.),'友だち追加')]/following-sibling::td[1]",
        )
        if els:
            raw = els[0].text.strip()

        if not raw:
            return {"friend_registered_at": None, "display_name": display_name}

        m = DT_RE.search(raw)
        if not m:
            return {"friend_registered_at": None, "display_name": display_name}

        date_part = m.group(1).replace(".", "-").replace("/", "-")
        time_part = m.group(2)
        return {
            "friend_registered_at": f"{date_part} {time_part}",
            "display_name": display_name,
        }
    finally:
        driver.close()
        driver.switch_to.window(original_handle)


def save_user(name, href, friend_registered_at=None, support=None, display_name=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM lme_users WHERE href = %s ORDER BY id ASC LIMIT 1", (href,))
            row = cur.fetchone()

            if row:
                cur.execute(
                    """
                    UPDATE lme_users
                    SET line_name=%s, href=%s, friend_registered_at=%s, support=%s, display_name=%s
                    WHERE id=%s
                    """,
                    (name, href, friend_registered_at, support, display_name, row["id"]),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO lme_users (line_name, href, friend_registered_at, support, display_name)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (name, href, friend_registered_at, support, display_name),
                )
        conn.commit()


def clear_tables():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM lme_users")
            cur.execute("DELETE FROM lme_messages")
        conn.commit()


def scrape_current_page(driver):
    soup = BeautifulSoup(driver.page_source, "html.parser")
    rows = soup.select("table tr")

    for row in rows:
        name_tag = row.select_one("a[href*='/basic/friendlist/my_page/']")
        if not name_tag:
            continue

        href = name_tag.get("href", "")
        name = name_tag.get_text(strip=True)
        friend_registered_at = None
        display_name = None
        if href:
            detail = fetch_user_detail_info(driver, href)
            friend_registered_at = detail.get("friend_registered_at")
            display_name = detail.get("display_name")

        print(f"{name}: {href} / friend_registered_at={friend_registered_at} / display_name={display_name}")
        save_user(name, href, friend_registered_at=friend_registered_at, display_name=display_name)
        time.sleep(0.2)


def has_next_page(driver):
    try:
        next_button = driver.find_element(By.CSS_SELECTOR, ".glyphicon.glyphicon-menu-right")
        parent_li = next_button.find_element(By.XPATH, "./ancestor::li")
        return "disabled" not in (parent_li.get_attribute("class") or "")
    except Exception:
        return False


def go_to_next_page(driver):
    driver.find_element(By.CSS_SELECTOR, ".glyphicon.glyphicon-menu-right").click()
    time.sleep(2)


def scrape_user_list(driver):
    while True:
        scrape_current_page(driver)
        if has_next_page(driver):
            go_to_next_page(driver)
        else:
            break
    print("✅ 全ページのデータ取得が完了しました。")
