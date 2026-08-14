"""翻译模块 — 内置游戏词典翻译

翻译方案：
1. 内置游戏名词典（game_dict.json，主要）
2. 均失败返回原文
"""
import json
import sys
from pathlib import Path

import database
from utils import get_logger

logger = get_logger()

# 词典缓存（模块级，避免重复加载）
_dict_cache: dict | None = None


# ============================================================
# 词典加载
# ============================================================

def _get_dict_paths() -> list[Path]:
    """返回词典候选路径列表（用户目录优先，覆盖打包内置）"""
    paths = []
    # 1. 用户目录（运行时"更新词典"写入此处）
    user_path = Path.home() / ".fling_trainer" / "game_dict.json"
    if user_path.exists():
        paths.append(user_path)
    # 2. 打包内置 / 开发态项目目录
    if getattr(sys, 'frozen', False):
        builtin_path = Path(sys._MEIPASS) / 'game_dict.json'
    else:
        builtin_path = Path(__file__).parent / 'game_dict.json'
    if builtin_path.exists():
        paths.append(builtin_path)
    return paths


def _load_game_dict() -> dict:
    """加载并合并所有候选词典（用户目录覆盖内置）"""
    global _dict_cache
    if _dict_cache is not None:
        return _dict_cache
    merged = {}
    for path in _get_dict_paths():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            merged.update(data)
        except Exception as e:
            logger.warning(f"加载词典失败 {path}: {e}")
            continue
    _dict_cache = merged
    return _dict_cache


def reload_game_dict() -> dict:
    """强制重新加载词典（清缓存，用于"更新词典"后刷新）"""
    global _dict_cache
    _dict_cache = None
    return _load_game_dict()


# ============================================================
# 语言检测
# ============================================================

def detect_language(text: str) -> str:
    """检测文本语言，返回 'zh' 或 'en'（仅用于翻译缓存键）"""
    if not text:
        return "en"
    cjk_count = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
    return "zh" if cjk_count > 0 else "en"


# ============================================================
# 翻译引擎：内置词典
# ============================================================

def _translate_dict(text: str, target: str) -> str | None:
    """查询内置词典，支持完全匹配 + 包含匹配 + rapidfuzz 模糊匹配。

    :param target: 'en'（中文→英文）或 'zh'（英文→中文）
    :return: 译文或 None
    """
    try:
        game_dict = _load_game_dict()
        if not game_dict:
            return None

        if target == 'en':
            # 中文 → 英文
            text_lower = text.lower()
            # 1. 完全匹配（含大小写不敏感）
            for en_name, cn_name in game_dict.items():
                if cn_name and (cn_name == text or cn_name.lower() == text_lower):
                    return en_name
            # 2. 包含匹配（用户搜索带后缀，如"艾尔登法环 2"）
            for en_name, cn_name in game_dict.items():
                if cn_name and text in cn_name:
                    return en_name
            # 3. rapidfuzz 模糊匹配（阈值 85）
            try:
                from rapidfuzz import fuzz, process
                cn_items = [(en, cn) for en, cn in game_dict.items() if cn]
                if cn_items:
                    choices = {i: item[1] for i, item in enumerate(cn_items)}
                    result = process.extractOne(text, choices, scorer=fuzz.WRatio)
                    if result and result[1] >= 85:
                        return cn_items[result[2]][0]
            except ImportError:
                pass
        else:
            # 英文 → 中文
            if text in game_dict:
                return game_dict[text]
            text_lower = text.lower()
            for en_name, cn_name in game_dict.items():
                if en_name.lower() == text_lower:
                    return cn_name
            # rapidfuzz 模糊匹配
            try:
                from rapidfuzz import fuzz, process
                en_names = list(game_dict.keys())
                result = process.extractOne(text, en_names, scorer=fuzz.WRatio)
                if result and result[1] >= 85:
                    return game_dict[result[2]]
            except ImportError:
                pass
        return None
    except Exception as e:
        logger.warning(f"词典查询异常: {e}")
        return None


# ============================================================
# 主翻译接口
# ============================================================

def _truncate_for_log(text: str, max_len: int = 20) -> str:
    """脱敏：截断长文本用于日志"""
    if not text:
        return ""
    return text[:max_len] + ('...' if len(text) > max_len else '')


def translate(text: str, target='en') -> str:
    """翻译文本：查缓存 → 内置词典 → 原文

    :param text: 待翻译文本
    :param target: 目标语言 'en' 或 'zh'
    :return: 译文或原文
    """
    if not text or not text.strip():
        return text

    # 检测源语言（用于缓存键）
    src_lang = detect_language(text)

    # 1. 查缓存
    cached = database.get_translation(text, target, src_lang)
    if cached:
        return cached

    # 2. 内置词典查询
    result = _translate_dict(text, target)
    if result:
        database.set_translation(text, target, result, src_lang)
        logger.debug(f"词典翻译成功: {_truncate_for_log(text)} → {_truncate_for_log(result)}")
        return result

    # 3. 失败返回原文
    logger.warning(f"翻译失败，返回原文: {_truncate_for_log(text)}")
    return text


def translate_batch(texts: list[str], target='en') -> dict[str, str]:
    """批量翻译，返回 {原文: 译文} 映射"""
    result = {}
    for text in texts:
        try:
            result[text] = translate(text, target)
        except Exception as e:
            logger.warning(f"翻译失败 [{_truncate_for_log(text)}]: {e}")
            result[text] = text
    return result


# ============================================================
# 翻译引擎状态
# ============================================================

def get_translation_status() -> dict:
    """获取当前可用的翻译引擎状态，用于设置页显示"""
    loaded = _load_game_dict()
    return {
        'dict_loaded': bool(loaded),
        'dict_count': len(loaded) if loaded else 0,
    }
