"""数据库模块 — SQLite 数据层，管理修改器、翻译缓存、下载记录。

数据库路径：~/.fling_trainer/fling_data.db
所有 SQLite 操作均通过 threading.Lock 保护，支持多线程访问。
"""
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

import re

from rapidfuzz import fuzz

import config
from utils import get_logger

# 数据库路径：用户主目录下的 .fling_trainer
APP_DIR = Path.home() / ".fling_trainer"
DB_PATH = APP_DIR / "fling_data.db"

# 线程锁，保护所有 SQLite 操作
_db_lock = threading.Lock()


def _normalize_key(s: str) -> str:
    """文本归一化：去空格/标点、转小写、保留字母数字与中文。

    用于让 "wolong" 能命中 "Wo Long: Fallen Dynasty"（归一化后为 wolongfallendynasty）。
    """
    return re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', (s or '').lower())


def get_conn() -> sqlite3.Connection:
    """获取数据库连接（check_same_thread=False，允许跨线程使用）"""
    APP_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    # 支持按列名访问行数据
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库，建表 IF NOT EXISTS，并迁移旧 translations 表"""
    with _db_lock:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            # 修改器表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mods (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name_en TEXT NOT NULL,
                    name_cn TEXT,
                    detail_url TEXT NOT NULL UNIQUE,
                    version TEXT,
                    options_count TEXT,
                    last_updated TEXT,
                    fetched_at TEXT
                )
            """)

            # 翻译缓存表（新结构：含 source_lang 字段）
            # 先尝试创建新表（全新安装走此分支）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS translations (
                    source_text TEXT,
                    source_lang TEXT,
                    target_lang TEXT,
                    result TEXT,
                    PRIMARY KEY(source_text, source_lang, target_lang)
                )
            """)

            # 检测旧表结构，若缺 source_lang 列则迁移
            cursor.execute("PRAGMA table_info(translations)")
            columns = [row[1] for row in cursor.fetchall()]
            if columns and 'source_lang' not in columns:
                # 旧表存在且缺 source_lang，执行迁移：
                # 1. 创建新表（translations_new）
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS translations_new (
                        source_text TEXT,
                        source_lang TEXT,
                        target_lang TEXT,
                        result TEXT,
                        PRIMARY KEY(source_text, source_lang, target_lang)
                    )
                """)
                # 2. 复制旧数据，source_lang 默认 'auto'
                cursor.execute("""
                    INSERT OR IGNORE INTO translations_new (source_text, source_lang, target_lang, result)
                    SELECT source_text, 'auto', target_lang, result FROM translations
                """)
                # 3. 替换旧表
                cursor.execute("DROP TABLE translations")
                cursor.execute("ALTER TABLE translations_new RENAME TO translations")
                get_logger().info("translations 表已迁移：新增 source_lang 字段")

            # 下载记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY,
                    mod_id INTEGER,
                    file_name TEXT,
                    file_path TEXT,
                    file_size TEXT,
                    downloaded_at TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()


def upsert_mods(mods: list[dict]):
    """批量插入或更新修改器记录（INSERT OR REPLACE）。

    mods 每项含：name_en, detail_url, version, options_count, last_updated
    fetched_at 自动设置为当前时间。
    """
    if not mods:
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _db_lock:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            for mod in mods:
                cursor.execute("""
                    INSERT OR REPLACE INTO mods
                        (name_en, detail_url, version, options_count, last_updated, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    mod.get("name_en", ""),
                    mod.get("detail_url", ""),
                    mod.get("version", ""),
                    mod.get("options_count", ""),
                    mod.get("last_updated", ""),
                    now,
                ))
            conn.commit()
        except Exception as e:
            get_logger().error(f"批量插入修改器失败: {e}")
        finally:
            conn.close()


def get_all_mods() -> list[dict]:
    """返回所有修改器记录（id, name_en, name_cn, detail_url, version, options_count, last_updated）"""
    with _db_lock:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name_en, name_cn, detail_url, version, options_count, last_updated
                FROM mods
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()


def search_mods(query: str, threshold=90, limit=50) -> list[dict]:
    """模糊搜索修改器。

    使用 rapidfuzz fuzz.partial_ratio 对 name_en 匹配，
    返回匹配度 >= threshold 的结果，按匹配度降序。
    每项含：id, name_en, name_cn, detail_url, match_score
    """
    # 先加锁读取所有候选记录
    with _db_lock:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name_en, name_cn, detail_url FROM mods")
            rows = cursor.fetchall()
        finally:
            conn.close()

    # 模糊匹配（不涉及数据库，无需持锁）
    results = []
    query_lower = query.lower()
    query_norm = _normalize_key(query)
    for row in rows:
        name_en = row["name_en"] or ""
        score = fuzz.partial_ratio(query_lower, name_en.lower())
        # 归一化（去空格/标点）后再匹配一次，取较高分，容忍 "wolong" vs "Wo Long"
        if query_norm:
            score = max(score, fuzz.partial_ratio(query_norm, _normalize_key(name_en)))
        if score >= threshold:
            results.append({
                "id": row["id"],
                "name_en": row["name_en"],
                "name_cn": row["name_cn"],
                "detail_url": row["detail_url"],
                "match_score": score,
            })
    # 按匹配度降序排序
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results[:limit]


def search_mods_substring(query: str, limit=50) -> list[dict]:
    """子串搜索 — 对 name_en/name_cn 做大小写不敏感包含匹配 + 归一化匹配

    归一化匹配让 "wolong" 能命中 "Wo Long: Fallen Dynasty"（去空格/标点后做严格包含）。
    """
    keyword = f'%{query.lower()}%'
    with _db_lock:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM mods WHERE LOWER(name_en) LIKE ? OR LOWER(COALESCE(name_cn, '')) LIKE ?",
                (keyword, keyword)
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

    results = []
    seen = set()
    for row in rows:
        d = dict(row)
        d['match_score'] = 95.0
        results.append(d)
        seen.add(d['detail_url'])

    # 归一化子串匹配：去空格/标点后做严格包含匹配（确定性匹配，不引入幻觉）
    q_norm = _normalize_key(query)
    if q_norm:
        with _db_lock:
            conn = get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM mods")
                all_rows = cursor.fetchall()
            finally:
                conn.close()
        for row in all_rows:
            if row['detail_url'] in seen:
                continue
            name_norm = _normalize_key(row['name_en'])
            cn_norm = _normalize_key(row['name_cn'])
            if q_norm in name_norm or (cn_norm and q_norm in cn_norm):
                d = dict(row)
                d['match_score'] = 95.0
                results.append(d)
                seen.add(d['detail_url'])

    return results[:limit]


def search_mods_by_cn(query: str, limit=50) -> list[dict]:
    """按中文名搜索修改器 — 子串匹配 + 模糊匹配。

    用于中文查询直接命中已缓存的中文名（name_cn），
    弥补 game_dict.json 覆盖不全导致的搜索不到问题。
    每项含：id, name_en, name_cn, detail_url, match_score
    """
    query = (query or "").strip()
    if not query:
        return []

    keyword = f'%{query.lower()}%'
    with _db_lock:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name_en, name_cn, detail_url FROM mods "
                "WHERE LOWER(COALESCE(name_cn, '')) LIKE ?",
                (keyword,)
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

    results = []
    seen = set()
    for row in rows:
        d = dict(row)
        d['match_score'] = 95.0
        if d['detail_url'] not in seen:
            seen.add(d['detail_url'])
            results.append(d)

    # 模糊匹配兜底（对 name_cn 非空的记录）
    with _db_lock:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name_en, name_cn, detail_url FROM mods")
            rows = cursor.fetchall()
        finally:
            conn.close()

    q_lower = query.lower()
    fuzzy = []
    for row in rows:
        cn = (row["name_cn"] or "").strip()
        if not cn:
            continue
        if row["detail_url"] in seen:
            continue
        score = fuzz.partial_ratio(q_lower, cn.lower())
        if score >= 80:
            d = dict(row)
            d['match_score'] = float(score)
            fuzzy.append(d)

    fuzzy.sort(key=lambda x: x['match_score'], reverse=True)
    results.extend(fuzzy)

    return results[:limit]


def get_mod_by_id(mod_id: int) -> dict | None:
    """根据 ID 获取修改器记录，不存在返回 None"""
    with _db_lock:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM mods WHERE id = ?", (mod_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def get_mod_by_name(name_en: str) -> dict | None:
    """根据英文名精确查找修改器记录，不存在返回 None"""
    with _db_lock:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM mods WHERE name_en = ?", (name_en,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def update_mod_cn_name(mod_id: int, name_cn: str):
    """更新修改器的中文名称"""
    with _db_lock:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE mods SET name_cn = ? WHERE id = ?",
                (name_cn, mod_id)
            )
            conn.commit()
        finally:
            conn.close()


def get_translation(source: str, target: str, source_lang: str = 'auto') -> str | None:
    """查询翻译缓存，未命中返回 None。

    优先匹配精确 source_lang，其次匹配 'auto'。
    """
    with _db_lock:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            # 优先精确匹配 source_lang
            cursor.execute(
                "SELECT result FROM translations WHERE source_text = ? AND target_lang = ? AND source_lang = ?",
                (source, target, source_lang)
            )
            row = cursor.fetchone()
            if row:
                return row["result"]
            # 其次匹配 source_lang='auto'（兼容旧数据）
            cursor.execute(
                "SELECT result FROM translations WHERE source_text = ? AND target_lang = ? AND source_lang = 'auto'",
                (source, target)
            )
            row = cursor.fetchone()
            return row["result"] if row else None
        finally:
            conn.close()


def set_translation(source: str, target: str, result: str, source_lang: str = 'auto'):
    """写入翻译缓存"""
    with _db_lock:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO translations (source_text, source_lang, target_lang, result)
                VALUES (?, ?, ?, ?)
            """, (source, source_lang, target, result))
            conn.commit()
        finally:
            conn.close()


def add_download(mod_id, file_name, file_path, file_size):
    """添加一条下载记录"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _db_lock:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO downloads (mod_id, file_name, file_path, file_size, downloaded_at)
                VALUES (?, ?, ?, ?, ?)
            """, (mod_id, file_name, file_path, file_size, now))
            conn.commit()
        finally:
            conn.close()


def is_data_stale(hours=24) -> bool:
    """检查数据是否过期：fetched_at 最大值是否超过 hours 小时"""
    with _db_lock:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(fetched_at) FROM mods")
            row = cursor.fetchone()
            last = row[0]
        finally:
            conn.close()

    # 无数据视为过期
    if not last:
        return True
    try:
        last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
        return datetime.now() - last_dt > timedelta(hours=hours)
    except (ValueError, TypeError):
        return True


def get_last_update() -> str | None:
    """返回最近一次 fetched_at，无数据返回 None"""
    with _db_lock:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(fetched_at) FROM mods")
            row = cursor.fetchone()
            return row[0]
        finally:
            conn.close()


def get_mod_count() -> int:
    """返回修改器总数"""
    with _db_lock:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM mods")
            return cursor.fetchone()[0]
        finally:
            conn.close()


def set_last_update(time_str: str):
    """将 last_update 字段写入 config.json（调用 config.save_config）"""
    cfg = config.load_config()
    cfg["last_update"] = time_str
    config.save_config(cfg)
