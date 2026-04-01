import re
import json
from urllib import request
from urllib.error import HTTPError
from pathlib import Path
from typing import Dict, Any

import pymysql


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.php"
DEFAULT_DB_API_URL = "https://totalappworks.com/lme/db_bridge.php"
USE_DB_API_BY_DEFAULT = True


class ConfigError(Exception):
    pass


def _parse_php_define(text: str, key: str) -> str:
    pattern = rf"define\(\s*['\"]{re.escape(key)}['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)"
    m = re.search(pattern, text)
    if not m:
        raise ConfigError(f"{key} が config.php で見つかりません")
    return m.group(1)

def _parse_php_define_optional(text: str, key: str) -> str | None:
    pattern = rf"define\(\s*['\"]{re.escape(key)}['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)"
    m = re.search(pattern, text)
    return m.group(1) if m else None

def load_db_config(config_path: Path = CONFIG_PATH) -> Dict[str, Any]:
    if not config_path.exists():
        raise ConfigError(f"config.php が見つかりません: {config_path}")

    raw = config_path.read_text(encoding="utf-8")
    conf = {
        "host": _parse_php_define(raw, "DB_HOST"),
        "database": _parse_php_define(raw, "DB_NAME"),
        "user": _parse_php_define(raw, "DB_USER"),
        "password": _parse_php_define(raw, "DB_PASS"),
        "charset": _parse_php_define(raw, "DB_CHARSET"),
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": False,
    }

    db_port = _parse_php_define_optional(raw, "DB_PORT")
    if db_port:
        conf["port"] = int(db_port)
    return conf

def get_connection():
    conf = load_db_config()
    try:
        return pymysql.connect(**conf)
    except pymysql.err.OperationalError as exc:
        host = conf.get("host", "unknown")
        port = conf.get("port", 3306)
        raise RuntimeError(
            "MySQL に接続できませんでした。"
            f"接続先: {host}:{port}。"
            "MySQL サービスが起動中か、config.php の接続情報（DB_HOST / DB_PORT）を確認してください。"
            "ローカルから直接接続できない環境では、LME_DB_API_URL を設定して PHP API 経由モードを利用してください。"
        ) from exc

def get_api_url() -> str | None:
    """固定 URL で PHP API 経由モードを利用する。"""
    if USE_DB_API_BY_DEFAULT:
        return DEFAULT_DB_API_URL
    return None


def use_api_mode() -> bool:
    return bool(get_api_url())


def call_db_api(action: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    api_url = get_api_url()
    if not api_url:
        raise ConfigError("DB API URL が未設定です（db.py の DEFAULT_DB_API_URL を確認してください）")

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