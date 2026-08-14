"""多策略游戏搜索模块 — 支持中文、拼音、缩写、模糊匹配

参考 Game Cheats Manager 的 search_index.py，简化实现核心拼音搜索。

搜索策略（按优先级）：
1. 直接匹配 — 中英文完全/子串匹配
2. 缩写匹配 — "DS3" → "Dark Souls III"
3. 拼音匹配 — "zhilang" → "只狼" → "Sekiro"
4. 模糊匹配 — rapidfuzz WRatio
"""
import re
from typing import Optional

from rapidfuzz import fuzz, process

from utils import get_logger

logger = get_logger()

# 尝试导入拼音库
try:
    from pypinyin import Style, lazy_pinyin
    _PYPINYIN_AVAILABLE = True
except ImportError:
    _PYPINYIN_AVAILABLE = False
    logger.warning("pypinyin 未安装，拼音搜索功能不可用。请运行 pip install pypinyin")

# 尝试导入 zhon（中文标点/字符检测）
try:
    import zhon.cedict as _zhon_cedict
    _ZHON_AVAILABLE = True
except ImportError:
    _ZHON_AVAILABLE = False

# CJK Unicode 范围（zhon 不可用时的后备）
_CJK_RANGES = [
    (0x4e00, 0x9fff),    # CJK Unified Ideographs
    (0x3400, 0x4dbf),    # CJK Extension A
    (0xf900, 0xfaff),    # CJK Compatibility Ideographs
]

# 匹配阈值
STRING_THRESHOLD = 80       # 模糊字符串匹配阈值
PINYIN_THRESHOLD = 85       # 拼音匹配阈值
FUZZY_THRESHOLD = 75        # 通用模糊匹配阈值
MIN_QUERY_LEN = 2           # 最小查询长度
MIN_PINYIN_LEN = 3          # 最小拼音匹配长度


def is_chinese(text: str) -> bool:
    """检测文本是否包含中文字符"""
    if not text:
        return False
    if _ZHON_AVAILABLE:
        return any(ch in _zhon_cedict.all for ch in text)
    # 后备：Unicode 范围检测
    for ch in text:
        cp = ord(ch)
        for lo, hi in _CJK_RANGES:
            if lo <= cp <= hi:
                return True
    return False


def to_pinyin(text: str) -> tuple[str, str]:
    """中文转拼音，返回 (连写形式, 空格分音节形式)

    例: "只狼" → ("zhilang", "zhi lang")
    非中文字符原样保留（小写）。
    """
    if not _PYPINYIN_AVAILABLE or not text:
        return "", ""
    syllables = []
    for token in lazy_pinyin(text, style=Style.NORMAL):
        token = re.sub(r'[^a-z]', '', token.lower())
        if token:
            syllables.append(token)
    return ''.join(syllables), ' '.join(syllables)


def _sanitize(text: str) -> str:
    """文本归一化：去标点空格、转小写、数字保留"""
    if not text:
        return ""
    # 移除标点和空格，保留字母数字
    return re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', text.lower())


def _acronym(text: str) -> str:
    """提取缩写：取每个英文单词首字母，数字保留

    例: "Dark Souls III" → "dsi", "Resident Evil 4" → "re4"
    """
    words = re.findall(r'[A-Za-z0-9]+', text)
    return ''.join(w[0] for w in words).lower() if words else ""


def _fuzzy_collapse(s: str) -> str:
    """模糊音归并：zh→z, ch→c, sh→s, ng→n"""
    s = s.replace('zh', 'z').replace('ch', 'c').replace('sh', 's')
    return s.replace('ng', 'n')


def _fuzzy_collapse_tokens(tokens: str) -> str:
    """对分音节拼音逐音节做模糊音归并，返回连写形式。

    逐音节归并可避免跨音节误伤：
    如 "ac hei qi re" → "acheiqire"（保留 hei 的 h），
    而全局 replace 会把 "c"+"hei" 误当作 "ch" 归并成 "ceiqi"。
    """
    return ''.join(_fuzzy_collapse(syl) for syl in tokens.split() if syl)


def _initials_from_tokens(tokens: str) -> str:
    """从分音节拼音提取首字母缩写：'zhi lang' → 'zl'"""
    return ''.join(s[0] for s in tokens.split() if s)


class GameSearcher:
    """多策略游戏搜索器

    基于 game_dict（{英文名: 中文名}）构建搜索索引，
    支持中英文、拼音、缩写、模糊匹配。
    """

    def __init__(self, game_dict: dict):
        """初始化搜索器

        :param game_dict: {英文名: 中文名} 词典
        """
        self.en_to_cn = dict(game_dict)
        self.cn_to_en = {}
        for en, cn in game_dict.items():
            if cn and cn not in self.cn_to_en:
                self.cn_to_en[cn] = en

        # 预计算索引
        # 英文名归一化列表：[(sanitized_en, cn_name, original_en), ...]
        self._en_index = []
        # 中文名归一化列表：[(sanitized_cn, en_name, original_cn), ...]
        self._cn_index = []
        # 拼音索引：[(pinyin_concat, pinyin_tokens, en_name, cn_name), ...]
        self._pinyin_index = []

        for en, cn in game_dict.items():
            se = _sanitize(en)
            if se:
                self._en_index.append((se, cn or en, en))
            if cn:
                sc = _sanitize(cn)
                if sc:
                    self._cn_index.append((sc, en, cn))
                # 拼音索引
                if _PYPINYIN_AVAILABLE and is_chinese(cn):
                    concat, tokens = to_pinyin(cn)
                    if concat:
                        self._pinyin_index.append((
                            _fuzzy_collapse_tokens(tokens),
                            tokens,
                            en,
                            cn
                        ))

        # 提取英文名列表供 fuzzy extractOne 使用
        self._en_keys = [item[0] for item in self._en_index]
        self._cn_keys = [item[0] for item in self._cn_index]
        self._pinyin_keys = [item[0] for item in self._pinyin_index]

        logger.info(f"GameSearcher 初始化：{len(self.en_to_cn)} 条词典，"
                     f"{len(self._pinyin_index)} 条拼音索引")

    def search(self, query: str, limit: int = 50) -> list[dict]:
        """搜索游戏

        :param query: 搜索关键词（中文/英文/拼音/缩写）
        :param limit: 最大返回数
        :return: [{"en": str, "cn": str, "score": int}, ...] 按分数降序
        """
        if not query or len(query.strip()) < MIN_QUERY_LEN:
            return []

        query = query.strip()
        results = {}  # en_name -> (cn_name, score)

        # 1. 直接匹配
        self._direct_match(query, results)

        # 2. 缩写匹配
        self._acronym_match(query, results)

        # 3. 拼音匹配
        self._pinyin_match(query, results)

        # 4. 模糊匹配
        self._fuzzy_match(query, results)

        # 排序并截取
        sorted_results = sorted(
            results.items(), key=lambda x: -x[1][1]
        )[:limit]

        return [
            {"en": en, "cn": cn, "score": score}
            for en, (cn, score) in sorted_results
        ]

    def _direct_match(self, query: str, results: dict):
        """直接字符串匹配（中英文）"""
        q_lower = query.lower()
        q_sanitize = _sanitize(query)

        # 英文名匹配（仅非中文查询）
        if not is_chinese(query):
            for se, cn, en in self._en_index:
                score = 0
                if se == q_sanitize:
                    score = 100
                elif q_sanitize in se:
                    score = 95
                elif se in q_sanitize and len(se) >= 3 and len(q_sanitize) >= 4:
                    score = 90
                if score > 0:
                    self._add_result(results, en, cn, score)

        # 中文名匹配（中文查询）
        if is_chinese(query):
            for sc, en, cn in self._cn_index:
                score = 0
                if query == cn:
                    score = 100
                elif query in cn:
                    score = 95
                if score > 0:
                    self._add_result(results, en, cn, score)

    def _acronym_match(self, query: str, results: dict):
        """缩写匹配：DS3 → Dark Souls III"""
        q_lower = query.lower()
        # 纯字母数字的短查询才尝试缩写
        if not re.match(r'^[a-z0-9]+$', q_lower):
            return
        if len(q_lower) < 2:
            return

        for se, cn, en in self._en_index:
            acr = _acronym(en)
            if not acr:
                continue
            if q_lower == acr:
                self._add_result(results, en, cn, 90)
            elif len(q_lower) >= 3 and acr.startswith(q_lower):
                self._add_result(results, en, cn, 85)

    def _pinyin_match(self, query: str, results: dict):
        """拼音匹配：zhilang → 只狼 → Sekiro

        中文查询与拼音查询统一走「转拼音 + 确定性字符串匹配」，
        实现拼音/汉语同等匹配，且不引入模糊幻觉。
        """
        if not _PYPINYIN_AVAILABLE or not self._pinyin_index:
            return

        # 1. 统一得到查询的拼音形式（连写 + 首字母缩写）
        if is_chinese(query):
            q_concat, q_tokens = to_pinyin(query)
            q_collapsed = _fuzzy_collapse_tokens(q_tokens)
            # 中文查询不参与首字母缩写匹配：中文总能转出完整拼音，
            # 若降级到缩写会误匹配（如"卡赞"→kz 误命中"控制"kong zhi）。
            q_initials = ""
        else:
            q_alnum = re.sub(r'[^a-z0-9]', '', query.lower())
            if len(q_alnum) < 2:
                return
            q_collapsed = _fuzzy_collapse(q_alnum)
            q_initials = q_alnum  # 拼音查询本身可能是首字母缩写（如 zl）

        if not q_collapsed:
            return

        # 2. 对每个拼音索引项做多级确定性匹配
        for pinyin_concat, pinyin_tokens, en, cn in self._pinyin_index:
            # 索引值已在构建时用 _fuzzy_collapse_tokens 归并，这里直接使用，
            # 避免再次全局 replace 造成跨音节误伤（如 "acheiqire" 被误归并成 "aceiqire"）。
            pinyin_collapsed = pinyin_concat
            initials = _initials_from_tokens(pinyin_tokens)
            score = 0
            if q_collapsed == pinyin_collapsed:
                score = 100          # 完整拼音精确（含模糊音 zh→z 等）
            elif pinyin_collapsed.startswith(q_collapsed) and len(q_collapsed) >= MIN_PINYIN_LEN:
                score = 95           # 完整拼音前缀
            elif q_collapsed in pinyin_collapsed and len(q_collapsed) >= MIN_PINYIN_LEN:
                score = 90           # 完整拼音包含
            elif q_initials and initials and q_initials == initials:
                score = 88           # 首字母缩写精确（zl → 只狼）
            elif (q_initials and initials and len(q_initials) >= 2
                  and initials.startswith(q_initials)):
                score = 85           # 首字母缩写前缀
            if score > 0:
                self._add_result(results, en, cn, score)

    def _fuzzy_match(self, query: str, results: dict):
        """模糊匹配兜底：仅用于英文/拼音查询，中文查询不走此路径"""
        q_sanitize = _sanitize(query)
        if not q_sanitize or len(q_sanitize) < MIN_QUERY_LEN:
            return

        # 中文查询只匹配中文名，不对英文名做模糊（避免假阳性）
        if is_chinese(query):
            if self._cn_keys:
                matches = process.extract(
                    query, self._cn_keys,
                    scorer=fuzz.WRatio,
                    score_cutoff=90,
                    limit=5
                )
                for m in matches:
                    key, score, idx = m
                    en = self._cn_index[idx][1]
                    cn = self._cn_index[idx][2]
                    self._add_result(results, en, cn, int(score))
            return

        # 英文名/拼音/缩写查询 → 对英文名做模糊
        if self._en_keys:
            matches = process.extract(
                q_sanitize, self._en_keys,
                scorer=fuzz.WRatio,
                score_cutoff=82,
                limit=8
            )
            for m in matches:
                key, score, idx = m
                # 过滤过短的英文名（如单字符 "i"/"Z"），避免对长查询产生假阳性
                if len(key) < 2:
                    continue
                en = self._en_index[idx][2]
                cn = self._en_index[idx][1]
                self._add_result(results, en, cn, int(score))

    @staticmethod
    def _add_result(results: dict, en: str, cn: str, score: int):
        """添加结果，保留最高分"""
        if en in results:
            if score > results[en][1]:
                results[en] = (cn, score)
        else:
            results[en] = (cn, score)

    def expand_query(self, query: str) -> list[str]:
        """扩展查询：将中文/拼音查询转换为英文关键词列表

        用于在数据库中搜索（数据库存储的是英文名）。

        :return: 英文关键词列表（包含原始查询和扩展结果）
        """
        if not query:
            return []

        results = self.search(query, limit=20)
        keywords = [query]  # 原始查询始终包含

        for r in results:
            if r['en'] and r['en'] not in keywords:
                keywords.append(r['en'])

        return keywords


# ============================================================
# 全局实例管理
# ============================================================

_searcher: Optional[GameSearcher] = None


def get_searcher() -> GameSearcher:
    """获取全局 GameSearcher 实例（懒加载）"""
    global _searcher
    if _searcher is not None:
        return _searcher

    # 加载游戏词典
    import translator
    game_dict = translator._load_game_dict()

    _searcher = GameSearcher(game_dict)
    return _searcher


def reload_searcher() -> GameSearcher:
    """强制重新加载搜索器（词典更新后调用）"""
    global _searcher
    _searcher = None
    # 同时清除 translator 的词典缓存
    import translator
    translator.reload_game_dict()
    return get_searcher()
