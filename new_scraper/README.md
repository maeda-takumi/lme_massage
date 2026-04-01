# new_scraper

`sample` を変更せずに作成した新スクレイピング処理です。

- ユーザー取得フローは sample 相当
- チャットは **JST基準で実行日の前日分のみ** 保存
- 保存先は MySQL（`../config.php` の接続情報を参照）
- テーブル名は `lme_users`, `lme_messages`
- ローカルから DB 直結できない場合は PHP API 経由モードを利用可能

## 実行

```bash
python -m new_scraper.main
```
### PHP API 経由で実行する場合

1. サーバー上に `db_bridge.php` と `config.php` を配置する
2. API URL を環境変数 `LME_DB_API_URL` に設定して実行する

```bash
export LME_DB_API_URL="https://<your-domain>/db_bridge.php"
python -m new_scraper.main
```

`LME_DB_API_URL` が設定されている場合、`new_scraper` は MySQL へ直接接続せず、
HTTP POST(JSON) で DB 操作を行います。

## 事前準備

```bash
mysql -u <user> -p <db> < sql/create_lme_tables.sql
```

または `main.py` 実行時に `initialize_tables()` で作成されます。
