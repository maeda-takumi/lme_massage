from __future__ import annotations

import time

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from .db import call_db_api, get_connection, use_api_mode

def save_user(name, href, friend_registered_at=None, support=None, display_name=None):
    if use_api_mode():
        call_db_api(
            "upsert_user",
            {
                "line_name": name,
                "href": href,
                "friend_registered_at": friend_registered_at,
                "support": support,
                "display_name": display_name,
            },
        )
        return
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
    if use_api_mode():
        call_db_api("clear_tables")
        return
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
        print(f"{name}: {href}")
        save_user(name, href)
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
