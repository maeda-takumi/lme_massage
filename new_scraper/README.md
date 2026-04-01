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
2. `new_scraper/db.py` の `DEFAULT_DB_API_URL`（HTTPS）を利用する（必要なら固定値を書き換える）

```bash
python -m new_scraper.main
```

`USE_DB_API_BY_DEFAULT = True` の場合、`new_scraper` は MySQL へ直接接続せず、
HTTP POST(JSON) で DB 操作を行います。

## 事前準備

```bash
mysql -u <user> -p <db> < sql/create_lme_tables.sql
```

または `main.py` 実行時に `initialize_tables()` で作成されます。

## 接続トラブル時の確認

- `config.php` に `DB_PORT` がある場合は自動で読み取ります（未指定時は `3306`）。
- `Can't connect to MySQL server` が出る場合は、MySQL サービスの起動状態と `DB_HOST` / `DB_PORT` を確認してください。
- ローカルから DB へ直接接続できない場合は `LME_DB_API_URL` を設定して PHP API 経由モードを利用してください。