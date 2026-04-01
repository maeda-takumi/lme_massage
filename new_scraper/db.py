import re
import json
import os
from urllib import request
from urllib.error import HTTPError
from pathlib import Path
from typing import Dict, Any

import pymysql


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.php"
DEFAULT_DB_API_URL = "http://totalappworks.com/lme/db_bridge.php"


class ConfigError(Exception):
    pass


def _parse_php_define(text: str, key: str) -> str:
    pattern = rf"define\(\s*['\"]{re.escape(key)}['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)"
    m = re.search(pattern, text)
    if not m:
        raise ConfigError(f"{key} が config.php で見つかりません")
    return m.group(1)


def load_db_config(config_path: Path = CONFIG_PATH) -> Dict[str, Any]:
    if not config_path.exists():
        raise ConfigError(f"config.php が見つかりません: {config_path}")

    raw = config_path.read_text(encoding="utf-8")
    return {
        "host": _parse_php_define(raw, "DB_HOST"),
        "database": _parse_php_define(raw, "DB_NAME"),
        "user": _parse_php_define(raw, "DB_USER"),
        "password": _parse_php_define(raw, "DB_PASS"),
        "charset": _parse_php_define(raw, "DB_CHARSET"),
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": False,
    }


def get_connection():
    conf = load_db_config()
    return pymysql.connect(**conf)

def get_api_url() -> str | None:
    """環境変数で指定された場合のみ PHP 経由モードを利用する。"""
    return os.getenv("LME_DB_API_URL") or os.getenv("LME_USE_DB_API") and DEFAULT_DB_API_URL


def use_api_mode() -> bool:
    return bool(get_api_url())


def call_db_api(action: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    api_url = get_api_url()
    if not api_url:
        raise ConfigError("LME_DB_API_URL が未設定です")

    body = json.dumps({"action": action, "payload": payload or {}}, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        api_url,
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as res:
            raw = res.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(
            f"DB API 呼び出し失敗: HTTP {exc.code} {exc.reason}. "
            f"URL={api_url}. Response={detail}"
        ) from exc

    parsed = json.loads(raw)
    if not parsed.get("ok"):
        raise RuntimeError(f"DB API エラー: {parsed.get('error', 'unknown error')}")
    return parsed