# new_scraper

`sample` を変更せずに作成した新スクレイピング処理です。

- ユーザー取得フローは sample 相当
- チャットは **JST基準で実行日の前日分のみ** 保存
- 保存先は MySQL（`../config.php` の接続情報を参照）
- テーブル名は `lme_users`, `lme_messages`

## 実行

```bash
python -m new_scraper.main
```

## 事前準備

```bash
mysql -u <user> -p <db> < sql/create_lme_tables.sql
```

または `main.py` 実行時に `initialize_tables()` で作成されます。
