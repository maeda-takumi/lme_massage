import re
from pathlib import Path
from typing import Dict, Any

import pymysql


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.php"


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
