from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .db import call_db_api, get_connection, use_api_mode

JST = ZoneInfo("Asia/Tokyo")


def _find_chat_scroll_container(driver):
    selectors = [
        "#messages-container-v2",
        ".chat-area", ".chat-body", ".message-body",
        "div[data-role='message-container']",
    ]
    for sel in selectors:
        try:
            return driver.find_element(By.CSS_SELECTOR, sel)
        except Exception:
            continue
    return None


def _wait_messages_drawn(driver, timeout=15):
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#messages-container-v2 > div"))
        )
    except TimeoutException:
        pass
    time.sleep(0.5)


def _extract_oldest_loaded_date(driver) -> date | None:
    soup = BeautifulSoup(driver.page_source, "html.parser")
    date_headers = soup.select("#messages-container-v2 .time-center")
    for header in date_headers:
        raw = header.get_text(strip=True)
        m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw)
        if not m:
            continue
        y, mo, d = map(int, m.groups())
        return date(y, mo, d)
    return None


def scroll_chat_to_top(driver, max_loops=20, stable_rounds=3, sleep_per_loop=0.5, stop_before_date: date | None = None):
    container = _find_chat_scroll_container(driver)

    def _get_count():
        try:
            return driver.execute_script("return document.querySelectorAll('#messages-container-v2 > div').length;")
        except Exception:
            return len(driver.find_elements(By.CSS_SELECTOR, "#messages-container-v2 > div"))

    _wait_messages_drawn(driver)

    same_count_streak = 0
    last_count = _get_count()

    for _ in range(max_loops):
        try:
            if container:
                driver.execute_script("arguments[0].scrollTop = 0;", container)
            else:
                driver.execute_script("window.scrollTo(0, 0);")
            driver.execute_script("window.dispatchEvent(new Event('scroll'));")
        except StaleElementReferenceException:
            container = _find_chat_scroll_container(driver)

        time.sleep(sleep_per_loop)

        count = _get_count()
        if count == last_count:
            same_count_streak += 1
        else:
            same_count_streak = 0
            last_count = count

        if stop_before_date:
            oldest_loaded_date = _extract_oldest_loaded_date(driver)
            if oldest_loaded_date and oldest_loaded_date < stop_before_date:
                return oldest_loaded_date
            
        if same_count_streak >= stable_rounds:
            break

    return None

def normalize_time_sent(current_date: str | None, time_sent_raw: str):
    if not time_sent_raw:
        return None

    raw = time_sent_raw.strip()
    m_full = re.search(r"(\d{4})-(\d{2})-(\d{2}).*?(\d{1,2}):(\d{2})", raw)
    if m_full:
        y, mo, d, hh, mm = map(int, m_full.groups())
        return f"{y:04d}-{mo:02d}-{d:02d} {hh:02d}:{mm:02d}:00"

    m_time = re.search(r"(\d{1,2}):(\d{2})", raw)
    if not m_time or not current_date:
        return None

    hh = int(m_time.group(1))
    mm = int(m_time.group(2))
    return f"{current_date} {hh:02d}:{mm:02d}:00"


def _to_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None
    
def _extract_sender_name_from_block(block):
    cand = block.select_one(".tooltip-container.staff_name_show span.underline.cursor-pointer")
    if cand:
        txt = cand.get_text(strip=True)
        if txt:
            return txt

    for sel in [".sender-name", ".name", ".user-name", ".member-name", "[data-role='sender-name']"]:
        elem = block.select_one(sel)
        if elem:
            txt = elem.get_text(strip=True)
            if txt:
                return txt

    return None


def _save_message(cur, user_id: int, sender: str, sender_name: str | None, message: str, time_sent: str):
    cur.execute(
        """
        INSERT INTO lme_messages (user_id, sender_name, sender, message, time_sent)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user_id, sender_name, sender, message, time_sent),
    )


def scrape_messages(driver, base_url="https://step.lme.jp"):
    target_date = (datetime.now(JST) - timedelta(days=1)).strftime("%Y-%m-%d")
    target_date_obj = _to_date(target_date)
    print(f"🗓 取得対象日(JST): {target_date}")

    api_mode = use_api_mode()

    users = None
    if api_mode:
        users = call_db_api("list_users").get("data", [])
    else:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, href FROM lme_users ORDER BY id ASC")
                users = cur.fetchall()

    if api_mode:
        for user in users:
            user_id, href = user["id"], user["href"]
            print(f"🟡 ユーザーID {user_id} のチャットを取得中…")

            driver.get(base_url + href)
            chat_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn-sns-line-my-page"))
            )
            chat_button.click()
            time.sleep(3)

            oldest_loaded_date = scroll_chat_to_top(driver, stop_before_date=target_date_obj)
            if oldest_loaded_date:
                print(f"⏭ 古い日付({oldest_loaded_date.strftime('%Y-%m-%d')})に到達したため、ユーザーID {user_id} のスクロールを早期終了")

            soup = BeautifulSoup(driver.page_source, "html.parser")
            message_blocks = soup.select("#messages-container-v2 > div")

            current_date = None
            for block in message_blocks:
                date_header = block.select_one(".time-center")
                if date_header:
                    raw = date_header.get_text(strip=True)
                    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw)
                    if m:
                        y, mo, d = map(int, m.groups())
                        current_date = f"{y:04d}-{mo:02d}-{d:02d}"
                        current_date_obj = _to_date(current_date)
                        if target_date_obj and current_date_obj and current_date_obj < target_date_obj:
                            print(f"⏭ 古い日付({current_date})に到達したため、ユーザーID {user_id} の走査を早期終了")
                            break

                sender = "you" if block.select_one(".you") else "me" if block.select_one(".me") else None
                if not sender:
                    continue

                msg_div = block.select_one(".message")
                time_div = block.select_one(".time-send")
                if not (msg_div and time_div):
                    continue

                time_sent = normalize_time_sent(current_date, time_div.get_text(strip=True))
                if not time_sent or time_sent[:10] != target_date:
                    continue

                sender_name = _extract_sender_name_from_block(block)
                text = msg_div.get_text(separator="\n").strip()
                call_db_api(
                    "insert_message",
                    {
                        "user_id": user_id,
                        "sender": sender,
                        "sender_name": sender_name,
                        "message": text,
                        "time_sent": time_sent,
                    },
                )
    else:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for user in users:
                    user_id, href = user["id"], user["href"]
                    print(f"🟡 ユーザーID {user_id} のチャットを取得中…")

                    driver.get(base_url + href)
                    chat_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn-sns-line-my-page"))
                    )
                    chat_button.click()
                    time.sleep(3)

                    oldest_loaded_date = scroll_chat_to_top(driver, stop_before_date=target_date_obj)
                    if oldest_loaded_date:
                        print(f"⏭ 古い日付({oldest_loaded_date.strftime('%Y-%m-%d')})に到達したため、ユーザーID {user_id} のスクロールを早期終了")
                        
                    soup = BeautifulSoup(driver.page_source, "html.parser")
                    message_blocks = soup.select("#messages-container-v2 > div")

                    current_date = None
                    for block in message_blocks:
                        date_header = block.select_one(".time-center")
                        if date_header:
                            raw = date_header.get_text(strip=True)
                            m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw)
                            if m:
                                y, mo, d = map(int, m.groups())
                                current_date = f"{y:04d}-{mo:02d}-{d:02d}"
                                current_date_obj = _to_date(current_date)
                                if target_date_obj and current_date_obj and current_date_obj < target_date_obj:
                                    print(f"⏭ 古い日付({current_date})に到達したため、ユーザーID {user_id} の走査を早期終了")
                                    break

                        sender = "you" if block.select_one(".you") else "me" if block.select_one(".me") else None
                        if not sender:
                            continue

                        msg_div = block.select_one(".message")
                        time_div = block.select_one(".time-send")
                        if not (msg_div and time_div):
                            continue

                        time_sent = normalize_time_sent(current_date, time_div.get_text(strip=True))
                        if not time_sent or time_sent[:10] != target_date:
                            continue

                        sender_name = _extract_sender_name_from_block(block)
                        text = msg_div.get_text(separator="\n").strip()
                        _save_message(cur, user_id, sender, sender_name, text, time_sent)
                        
            conn.commit()

    print("🎉 前日分メッセージ取得が完了しました！")
