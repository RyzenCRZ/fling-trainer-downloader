"""从 Steam 官方中文名扩充中英游戏词典

数据源：store.steampowered.com 搜索页（category1=998 单人游戏，l=schinese）。
每页 HTML 含 appid + 官方中文标题 + 英文 slug，无需调用被墙的 api.steampowered.com。

特性：
- 429 限流自动退避重试（指数退避 + 尊重 Retry-After）
- 每页解析后立即落盘，支持断点续跑
- 只保留「中文标题 + 英文 slug」的有效映射，不覆盖已有条目

用法：
    python scripts/expand_dict_steam.py [max_items] [max_pages] [delay]
    例：python scripts/expand_dict_steam.py 8000 80 2.0
"""
import json
import re
import sys
import time
from pathlib import Path

import requests

SEARCH_URL = "https://store.steampowered.com/search/results/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': 'https://store.steampowered.com/',
}

ROOT = Path(__file__).resolve().parent.parent
DICT_PATH = ROOT / 'game_dict.json'

CJK_RE = re.compile(r'[\u4e00-\u9fff]')
TITLE_RE = re.compile(r'<span class="title">([^<]+)</span>')
# 逐行（<a> 块）解析，避免 index 对齐错位导致 slug 抓错
ROW_RE = re.compile(
    r'<a\s+href="[^"]*?/app/(\d+)/([^/"?]+)[^"]*?"\s+data-ds-appid="\d+"[^>]*?>(.*?)</a>',
    re.DOTALL,
)

MAX_RETRY = 6
BASE_BACKOFF = 5.0


def fetch_page(start: int, count: int = 100, delay: float = 2.0) -> str:
    """抓取一页，429 时指数退避重试。"""
    last_err = None
    for attempt in range(MAX_RETRY):
        try:
            r = requests.get(
                SEARCH_URL,
                params={
                    'query': '', 'start': start, 'count': count,
                    'l': 'schinese', 'cc': 'US', 'category1': 998,
                },
                headers=HEADERS,
                timeout=30,
            )
        except requests.RequestException as e:
            last_err = e
            time.sleep(BASE_BACKOFF * (2 ** attempt))
            continue

        if r.status_code == 200:
            return r.text
        if r.status_code == 429:
            wait = float(r.headers.get('Retry-After', 0) or 0)
            wait = wait or BASE_BACKOFF * (2 ** attempt)
            print(f"      429 限流，等待 {wait:.0f}s 后重试（第 {attempt + 1} 次）...")
            time.sleep(wait)
            last_err = RuntimeError('429 Too Many Requests')
            continue
        last_err = RuntimeError(f'HTTP {r.status_code}')
        time.sleep(BASE_BACKOFF * (2 ** attempt))

    raise last_err if last_err else RuntimeError('fetch failed')


def parse_page(html: str) -> list[tuple[str, str, str]]:
    """解析一页，返回 [(appid, 显示标题, 英文slug), ...]（按行块解析）"""
    items = []
    for m in ROW_RE.finditer(html):
        appid = m.group(1)
        slug = m.group(2)
        body = m.group(3)
        t = TITLE_RE.search(body)
        title = t.group(1).strip() if t else ''
        items.append((appid, title, slug))
    return items


def clean_cn(title: str) -> str:
    """从标题中提取中文名：'Palworld / 幻兽帕鲁' -> '幻兽帕鲁'"""
    if '/' in title:
        parts = [p.strip() for p in title.split('/')]
        for p in parts:
            if CJK_RE.search(p):
                return p
    return title.strip()


def slug_to_en(slug: str) -> str:
    """slug 转英文名：'CounterStrike_2' -> 'CounterStrike 2'"""
    s = (slug or '').replace('_', ' ').strip()
    return s if s and s.lower() != 'app' else ''


def load_existing() -> dict:
    if DICT_PATH.exists():
        try:
            return json.loads(DICT_PATH.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}


def save(existing: dict):
    DICT_PATH.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def main():
    max_items = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    delay = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
    page_size = 100

    print(f"[1/3] 分页抓取单人游戏（目标新增 {max_items} 条，delay={delay}s）...")
    existing = load_existing()
    base_count = len(existing)
    en_to_cn: dict[str, str] = {}
    skipped_no_slug = 0
    start = 0

    for page in range(1, max_pages + 1):
        try:
            html = fetch_page(start, page_size, delay)
        except Exception as e:
            print(f"      第 {page} 页（start={start}）最终失败: {e}，停止。")
            print(f"      可调整延迟后从 start={start} 继续（脚本会去重）。")
            break

        items = parse_page(html)
        if not items:
            print(f"      第 {page} 页无结果，停止")
            break

        for _appid, title, slug in items:
            if not CJK_RE.search(title):
                continue
            en = slug_to_en(slug)
            if not en:
                skipped_no_slug += 1
                continue
            cn = clean_cn(title)
            if CJK_RE.search(cn) and en.lower() != cn.lower():
                en_to_cn.setdefault(en, cn)

        # 立即合并落盘（去重）
        added_this_page = 0
        for en, cn in en_to_cn.items():
            if en not in existing:
                existing[en] = cn
                added_this_page += 1
        save(existing)

        print(f"      第 {page} 页：{len(items)} 项，新增 {added_this_page}，"
              f"累计 {len(existing)} 条（start={start}）")

        if len(existing) - base_count >= max_items:
            break

        start += page_size
        if delay > 0:
            time.sleep(delay)

    print(f"[2/3] 本次解析有效映射 {len(en_to_cn)} 条（无英文 slug 跳过 {skipped_no_slug} 项）")
    print(f"[3/3] 完成：词典从 {base_count} -> {len(existing)} 条，写入 {DICT_PATH}")


if __name__ == '__main__':
    main()
