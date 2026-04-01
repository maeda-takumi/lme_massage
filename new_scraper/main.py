from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from .message_scraper import scrape_messages
from .schema import initialize_tables
from .user_scraper import clear_tables, scrape_user_list


if __name__ == "__main__":
    options = Options()
    options.add_experimental_option("detach", True)
    driver = webdriver.Chrome(options=options)

    driver.get("https://step.lme.jp/")
    input("ログインが完了したら Enter を押してください → ")

    print("🟡 テーブルを初期化中...")
    initialize_tables()

    print("🟡 既存データをクリア中...")
    clear_tables()

    print("🟡 一覧を取得中...")
    scrape_user_list(driver)

    print("🟡 メッセージを取得中（前日分/JSTのみ）...")
    scrape_messages(driver)

    print("🎉 全処理が完了しました！")
    driver.quit()
