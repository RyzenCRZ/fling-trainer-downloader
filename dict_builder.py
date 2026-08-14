"""词典构建模块 — 聚合 5 个数据源构建中英游戏名词典

数据源：
1. 风灵月影官网（英文名，需翻译）
2. Metacritic PC 榜单（英文名，需翻译）
3. 3DM Game 单机库（中英对照）
4. 游民星空 PC 单机区（中英对照）
5. IGN 中国评测（中英对照）

主流程：gather_raw → merge_entries → translate_missing → save
"""
import json
import re
import time
from pathlib import Path

import requests
import cloudscraper
from bs4 import BeautifulSoup

from utils import get_logger

logger = get_logger()

# 浏览器 UA
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 数据源名称常量（用于可信度排序）
SOURCE_FLING = "fling"
SOURCE_METACRITIC = "metacritic"
SOURCE_3DM = "3dm"
SOURCE_GAMERSKY = "gamersky"
SOURCE_IGN = "ign"

# 来源可信度（数值越大越可信，影响 merge 时同英文名多条中文的取舍）
SOURCE_TRUST = {
    SOURCE_IGN: 5,
    SOURCE_GAMERSKY: 4,
    SOURCE_3DM: 3,
    SOURCE_METACRITIC: 2,
    SOURCE_FLING: 1,
}

# 词典保存路径：用户目录
USER_DICT_PATH = Path.home() / ".fling_trainer" / "game_dict.json"


# ============================================================
# HTTP 工具
# ============================================================

def _fetch_html(url: str, use_cloudscraper: bool = True, timeout: int = 15) -> str | None:
    """获取页面 HTML，失败返回 None"""
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 403 and use_cloudscraper:
            logger.info(f"403 触发 cloudscraper: {url}")
            scraper = cloudscraper.create_scraper()
            resp = scraper.get(url, timeout=timeout)
        if resp.status_code == 200:
            # 优先使用响应头声明的编码，避免中文乱码
            if resp.encoding and resp.encoding.lower() == 'iso-8859-1':
                resp.encoding = resp.apparent_encoding
            return resp.text
        logger.warning(f"HTTP {resp.status_code}: {url}")
        return None
    except Exception as e:
        logger.warning(f"请求失败 {url}: {e}")
        return None


def _safe_text(node) -> str:
    """BeautifulSoup 节点安全取文本"""
    return node.get_text(strip=True) if node else ""


# ============================================================
# 数据源 1：风灵月影官网（复用 scraper）
# ============================================================

def fetch_fling() -> list[tuple[str, str | None, str]]:
    """抓取风灵月影官网修改器列表，返回 [(en, cn, source), ...]

    仅英文名，cn=None 待翻译。
    """
    try:
        import scraper
        mods = scraper.fetch_and_parse()
        result = [(m["name_en"], None, SOURCE_FLING) for m in mods if m.get("name_en")]
        logger.info(f"[fling] 抓取 {len(result)} 条")
        return result
    except Exception as e:
        logger.warning(f"[fling] 抓取失败: {e}")
        return []


# ============================================================
# 数据源 2：Metacritic PC 游戏列表
# ============================================================

def fetch_metacritic(max_pages: int = 30) -> list[tuple[str, str | None, str]]:
    """抓取 Metacritic PC 游戏榜单，返回 [(en, cn, source), ...]

    仅英文名，cn=None 待翻译。
    每页约 10 条（其余 JS 动态渲染，requests 拿不到）。
    """
    result = []
    url_template = "https://www.metacritic.com/browse/game/pc/all/all-time/metascore/?sort=desc&page={n}"
    try:
        scraper = cloudscraper.create_scraper()
    except Exception as e:
        logger.warning(f"[metacritic] cloudscraper 初始化失败: {e}")
        return []

    for page in range(0, max_pages):
        url = url_template.format(n=page)
        try:
            resp = scraper.get(url, timeout=20)
            if resp.status_code != 200:
                logger.warning(f"[metacritic] 第 {page} 页 HTTP {resp.status_code}")
                continue
            resp.encoding = 'utf-8'
            html = resp.text
        except Exception as e:
            logger.warning(f"[metacritic] 第 {page} 页请求失败: {e}")
            continue

        soup = BeautifulSoup(html, "html.parser")
        count_before = len(result)
        seen_slugs = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            # 严格匹配 /game/<slug>/ 形式，排除导航和附属页
            if not href.startswith("/game/"):
                continue
            # 排除单独 /game/ 导航
            slug = href[len("/game/"):].strip("/")
            if not slug or "/" in slug or "?" in slug:
                continue
            if slug in seen_slugs:
                continue
            title = _safe_text(a)
            if not title or len(title) < 2 or title.isdigit():
                continue
            seen_slugs.add(slug)
            result.append((title, None, SOURCE_METACRITIC))

        logger.info(f"[metacritic] 第 {page} 页抓取 {len(result) - count_before} 条")
        time.sleep(0.5)  # 礼貌限速

    # 去重（同源内按英文名）
    seen = set()
    dedup = []
    for en, cn, src in result:
        key = en.lower()
        if key not in seen:
            seen.add(key)
            dedup.append((en, cn, src))
    logger.info(f"[metacritic] 共抓取 {len(dedup)} 条（去重后）")
    return dedup


# ============================================================
# 数据源 3：3DM Game 单机游戏库
# ============================================================

# 《中文名》后缀变体正则
_3DM_TITLE_RE = re.compile(r"《(.+?)》")
# 详情页中常见英文名模式
_3DM_EN_RE = re.compile(r"英文名(?:称)?[:：]\s*([A-Za-z0-9\s\-'’:.,&!]+)", re.IGNORECASE)


def fetch_3dm(max_pages: int = 50) -> list[tuple[str, str | None, str]]:
    """抓取 3DM 单机游戏库（移动端标签页），返回 [(en, cn, source), ...]

    3DM 移动端有 50 个标签页（jingdian_3 ~ jingdian_50），每页约 60 款游戏。
    仅中文名，英文为 None 待反向翻译。
    使用 cloudscraper 绕过反爬。
    """
    result = []
    # 移动端标签页 URL 模板
    url_template = "https://m.3dmgame.com/tag/jingdian_{n}/"

    # 创建 cloudscraper 实例（3DM 反爬较强，必须用）
    try:
        scraper = cloudscraper.create_scraper()
    except Exception as e:
        logger.warning(f"[3dm] cloudscraper 初始化失败: {e}")
        return []

    # 标签 ID 范围：3-50
    tag_ids = list(range(3, 51))[:max_pages]

    for tid in tag_ids:
        url = url_template.format(n=tid)
        try:
            resp = scraper.get(url, timeout=20)
            if resp.status_code != 200:
                logger.warning(f"[3dm] 标签 {tid} HTTP {resp.status_code}")
                continue
            resp.encoding = 'utf-8'
            html = resp.text
        except Exception as e:
            logger.warning(f"[3dm] 标签 {tid} 请求失败: {e}")
            continue

        soup = BeautifulSoup(html, "html.parser")
        count_before = len(result)
        seen_urls_this_page = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/dl/pc/" not in href:
                continue
            # 同一 URL 多个 <a>（图片链接 + 标题链接 + 下载按钮）
            # 优先取含《》的有效标题，文本为空或按钮文本时跳过但不锁 URL
            text = _safe_text(a)
            if not text or text in ("下载游戏", "下载"):
                continue
            m = _3DM_TITLE_RE.search(text)
            if not m:
                continue
            cn_name = m.group(1).strip()
            if not cn_name or len(cn_name) < 2:
                continue
            if href in seen_urls_this_page:
                continue
            seen_urls_this_page.add(href)
            result.append((None, cn_name, SOURCE_3DM))

        logger.info(f"[3dm] 标签 {tid} 抓取 {len(result) - count_before} 条")
        time.sleep(0.4)  # 礼貌限速

    # 去重（同源内按中文名）
    seen = set()
    dedup = []
    for en, cn, src in result:
        key = (cn or "").lower()
        if key and key not in seen:
            seen.add(key)
            dedup.append((en, cn, src))
    logger.info(f"[3dm] 共抓取 {len(dedup)} 条（去重后）")
    return dedup


# ============================================================
# 数据源 4：游民星空 PC 单机区
# ============================================================

def fetch_gamersky() -> list[tuple[str, str | None, str]]:
    """抓游民星空 PC 单机区，返回 [(en, cn, source), ...]

    主入口页 https://www.gamersky.com/pcgame/ 含 /z/<slug>/ 形式链接，
    链接文本为中文名，slug 可反推英文名。
    """
    result = []
    urls = [
        "https://www.gamersky.com/pcgame/",
        "https://www.gamersky.com/AreaIndex/n/",
        "https://www.gamersky.com/AreaIndex/f/",
    ]
    for url in urls:
        html = _fetch_html(url, use_cloudscraper=True)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # 匹配 /z/<slug>/ 形式
            m = re.search(r"/z/([a-z0-9\-]+)/?", href, re.IGNORECASE)
            if not m:
                continue
            slug = m.group(1)
            cn_name = _safe_text(a)
            if not cn_name or len(cn_name) < 2:
                continue
            # slug → 英文名：去连字符 + Title Case
            en_name = slug.replace("-", " ").replace("_", " ").strip()
            en_name = " ".join(w.capitalize() for w in en_name.split())
            # 过滤明显非游戏链接（如 news/article）
            if any(skip in slug.lower() for skip in ["news", "article", "feature"]):
                continue
            result.append((en_name or None, cn_name, SOURCE_GAMERSKY))
        time.sleep(0.3)

    # 去重
    seen = set()
    dedup = []
    for en, cn, src in result:
        key = (en or "").lower() or (cn or "").lower()
        if key and key not in seen:
            seen.add(key)
            dedup.append((en, cn, src))
    logger.info(f"[gamersky] 共抓取 {len(dedup)} 条")
    return dedup


# ============================================================
# 数据源 5：IGN 中国
# ============================================================

def fetch_ign_china() -> list[tuple[str, str | None, str]]:
    """抓 IGN 中国评测列表，返回 [(en, cn, source), ...]

    反爬较强，失败则返回空列表（不影响主流程）。
    """
    result = []
    urls = [
        "https://www.ign.com/cn/games",
        "https://www.ign.com/cn/reviews/games",
    ]
    for url in urls:
        html = _fetch_html(url, use_cloudscraper=True, timeout=20)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        # IGN 列表页通常是 article 卡片，标题含中文名，URL 含英文 slug
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # 匹配 /cn/<game-slug> 或 /articles/<slug>
            m = re.search(r"/cn/([a-z0-9\-]+)/?", href, re.IGNORECASE)
            if not m:
                continue
            slug = m.group(1)
            cn_name = _safe_text(a)
            if not cn_name or len(cn_name) < 2:
                continue
            en_name = slug.replace("-", " ").title()
            if any(skip in slug.lower() for skip in ["news", "video", "article"]):
                continue
            result.append((en_name or None, cn_name, SOURCE_IGN))
        time.sleep(0.3)

    seen = set()
    dedup = []
    for en, cn, src in result:
        key = (en or "").lower() or (cn or "").lower()
        if key and key not in seen:
            seen.add(key)
            dedup.append((en, cn, src))
    logger.info(f"[ign] 共抓取 {len(dedup)} 条")
    return dedup


# ============================================================
# 合并去重
# ============================================================

def _normalize_en(name: str) -> str:
    """英文名归一化：去首尾空格，多个空格合并"""
    if not name:
        return ""
    return re.sub(r"\s+", " ", name.strip())


def merge_entries(entries: list[tuple[str, str | None, str]]) -> dict[str, str | None]:
    """合并多源条目，返回 {英文名: 中文名 or None}

    规则：
    1. 英文名归一化（去空格）
    2. 同一英文名有多条中文时，按来源可信度取最高
    3. 仅中文（英文为 None）的项暂存到反向表，待 translate_missing 反向翻译
    """
    # 第一阶段：按英文名聚合
    en_to_cn: dict[str, tuple[str | None, int]] = {}  # en -> (cn, trust)
    # 仅中文的条目（英文为 None）
    cn_only: dict[str, int] = {}  # cn_lower -> trust

    for en, cn, src in entries:
        trust = SOURCE_TRUST.get(src, 0)
        if en:
            en_norm = _normalize_en(en)
            if not en_norm:
                continue
            key = en_norm.lower()
            if key in en_to_cn:
                old_cn, old_trust = en_to_cn[key]
                # 取可信度更高的中文
                if cn and (not old_cn or trust > old_trust):
                    en_to_cn[key] = (cn, trust)
                elif cn and old_cn and trust > old_trust:
                    en_to_cn[key] = (cn, trust)
            else:
                en_to_cn[key] = (cn, trust)
        elif cn:
            # 仅中文条目
            cn_lower = cn.lower()
            if cn_lower not in cn_only or trust > cn_only[cn_lower]:
                cn_only[cn_lower] = trust

    # 第二阶段：构建结果（使用原始英文名大小写，取首个出现的）
    result: dict[str, str | None] = {}
    en_canonical: dict[str, str] = {}  # en_lower -> en_original
    for en, cn, src in entries:
        if not en:
            continue
        en_norm = _normalize_en(en)
        en_lower = en_norm.lower()
        if en_lower not in en_canonical:
            en_canonical[en_lower] = en_norm

    for en_lower, (cn, _) in en_to_cn.items():
        original = en_canonical.get(en_lower, en_lower)
        result[original] = cn

    # 第三阶段：仅中文条目（待反向翻译补英文，存为特殊标记 None key 无法表达）
    # 这里返回 result，仅中文条目通过另一接口暴露
    return result


def get_cn_only_entries(entries: list[tuple[str, str | None, str]]) -> list[tuple[str, int]]:
    """从原始 entries 中提取仅中文条目，返回 [(cn, trust), ...]"""
    seen = {}
    for en, cn, src in entries:
        if en or not cn:
            continue
        trust = SOURCE_TRUST.get(src, 0)
        cn_lower = cn.lower()
        if cn_lower not in seen or trust > seen[cn_lower][1]:
            seen[cn_lower] = (cn, trust)
    return list(seen.values())


# ============================================================
# 自动翻译补全
# ============================================================

def translate_missing(en_to_cn: dict[str, str | None],
                      cn_only: list[tuple[str, int]],
                      progress_cb=None) -> dict[str, str]:
    """翻译补全：en→zh（缺失中文的） + zh→en（仅中文条目）

    返回完整的 {英文名: 中文名} 词典。
    """
    import translator

    final: dict[str, str] = {}
    # 已有中英对照的直接加入
    for en, cn in en_to_cn.items():
        if cn:
            final[en] = cn

    # 待翻译项：英文名缺中文
    pending_en = [(en, cn) for en, cn in en_to_cn.items() if not cn]
    total_pending = len(pending_en) + len(cn_only)
    done = 0

    # 翻译 en → zh
    for en, _ in pending_en:
        try:
            cn = translator.translate(en, target='zh')
            if cn and cn != en:  # 翻译失败时返回原文，过滤
                final[en] = cn
        except Exception as e:
            logger.debug(f"翻译失败 {en}: {e}")
        done += 1
        if progress_cb and done % 10 == 0:
            progress_cb("翻译 en→zh", done, total_pending)

    # 翻译 zh → en（仅中文条目）
    for cn, _ in cn_only:
        try:
            en = translator.translate(cn, target='en')
            if en and en != cn:
                final[en] = cn
        except Exception as e:
            logger.debug(f"翻译失败 {cn}: {e}")
        done += 1
        if progress_cb and done % 10 == 0:
            progress_cb("翻译 zh→en", done, total_pending)

    if progress_cb:
        progress_cb("翻译完成", total_pending, total_pending)

    return final


# ============================================================
# 主类：DictBuilder
# ============================================================

class DictBuilder:
    """多源词典构建器"""

    # 数据源注册表
    SOURCES = {
        SOURCE_FLING: fetch_fling,
        SOURCE_METACRITIC: fetch_metacritic,
        SOURCE_3DM: fetch_3dm,
        SOURCE_GAMERSKY: fetch_gamersky,
        SOURCE_IGN: fetch_ign_china,
    }

    def __init__(self, progress_cb=None):
        self.progress_cb = progress_cb or (lambda s, c, t: None)

    def _emit(self, stage: str, current: int, total: int):
        try:
            self.progress_cb(stage, current, total)
        except Exception:
            pass

    def gather_raw(self, skip: list[str] | None = None) -> list[tuple[str, str | None, str]]:
        """聚合所有数据源，返回原始条目列表"""
        skip = skip or []
        all_entries: list[tuple[str, str | None, str]] = []
        sources = [(name, fn) for name, fn in self.SOURCES.items() if name not in skip]
        total_sources = len(sources)

        for i, (name, fn) in enumerate(sources):
            self._emit(f"抓取 {name}", i, total_sources)
            try:
                entries = fn()
                all_entries.extend(entries)
                logger.info(f"源 {name} 完成：{len(entries)} 条")
            except Exception as e:
                logger.warning(f"源 {name} 异常: {e}")

        self._emit("抓取完成", total_sources, total_sources)
        return all_entries

    def build(self, skip: list[str] | None = None) -> dict[str, str]:
        """主流程：抓取 → 合并 → 翻译 → 返回词典"""
        # 1. 抓取
        raw = self.gather_raw(skip)
        logger.info(f"原始条目总数：{len(raw)}")

        # 2. 合并
        en_to_cn = merge_entries(raw)
        cn_only = get_cn_only_entries(raw)
        logger.info(f"合并后：{len(en_to_cn)} 条英文条目，{len(cn_only)} 条仅中文")

        # 3. 翻译补全
        self._emit("开始翻译", 0, len(en_to_cn) + len(cn_only))
        final = translate_missing(
            en_to_cn, cn_only,
            progress_cb=lambda s, c, t: self._emit(s, c, t)
        )
        logger.info(f"最终词典：{len(final)} 条")

        return final

    def save(self, dict_data: dict, path: Path = None):
        """保存词典到 JSON"""
        target = path or USER_DICT_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(dict_data, f, ensure_ascii=False, indent=2)
        logger.info(f"词典已保存：{target}（{len(dict_data)} 条）")

    def load_merged(self) -> dict:
        """加载用户目录词典 + 打包内置词典的合并结果（用户优先）"""
        import sys
        merged = {}
        # 用户目录
        if USER_DICT_PATH.exists():
            try:
                with open(USER_DICT_PATH, "r", encoding="utf-8") as f:
                    merged.update(json.load(f))
            except Exception:
                pass
        # 打包内置 / 项目根
        if getattr(sys, 'frozen', False):
            builtin = Path(sys._MEIPASS) / "game_dict.json"
        else:
            builtin = Path(__file__).parent / "game_dict.json"
        if builtin.exists():
            try:
                with open(builtin, "r", encoding="utf-8") as f:
                    tmp = json.load(f)
                # 用户目录优先：仅补充内置词典中独有的键
                for k, v in tmp.items():
                    if k not in merged:
                        merged[k] = v
            except Exception:
                pass
        return merged
