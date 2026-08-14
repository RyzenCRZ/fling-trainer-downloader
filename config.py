"""配置管理模块 — 读写 config.json，管理下载路径等配置"""
import json
from pathlib import Path

# 配置目录：用户主目录下的 .fling_trainer
APP_DIR = Path.home() / ".fling_trainer"
CONFIG_FILE = APP_DIR / "config.json"

# 默认配置
DEFAULT_CONFIG = {
    "download_path": "",
    "update_interval_hours": 24,
    "last_update": "",
    "sort_mode": "time",  # "time" 按下载时间，"name" 按首字母
    "starred_trainers": [],  # 加星白名单修改器路径列表（上限20）
}


def _ensure_dir():
    """确保配置目录存在"""
    APP_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """读取配置文件，不存在则返回默认配置"""
    _ensure_dir()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            # 合并默认值，确保新增字段有默认值
            for key, val in DEFAULT_CONFIG.items():
                config.setdefault(key, val)
            return config
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    """保存配置到文件"""
    _ensure_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_download_path() -> Path | None:
    """获取下载路径，无效则返回 None"""
    config = load_config()
    path_str = config.get("download_path", "")
    if not path_str:
        return None
    path = Path(path_str)
    if path.exists() and path.is_dir():
        return path
    return None


def set_download_path(path: str) -> Path:
    """设置下载路径并创建目录"""
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    config = load_config()
    config["download_path"] = str(target)
    save_config(config)
    return target


def get_available_drives() -> list[str]:
    """获取所有可用磁盘盘符列表"""
    import string
    import os
    drives = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            drives.append(f"{letter}:")
    return drives


STARRED_MAX = 20


def get_sort_mode() -> str:
    """获取当前排序模式：time | name"""
    return load_config().get("sort_mode", "time")


def set_sort_mode(mode: str):
    """设置排序模式"""
    if mode not in ("time", "name"):
        return
    cfg = load_config()
    cfg["sort_mode"] = mode
    save_config(cfg)


def get_starred_trainers() -> list[str]:
    """获取加星白名单列表（绝对路径列表）"""
    cfg = load_config()
    return list(cfg.get("starred_trainers", []))


def set_starred_trainers(paths: list[str]):
    """覆盖保存加星白名单"""
    cfg = load_config()
    cfg["starred_trainers"] = list(paths)[:STARRED_MAX]
    save_config(cfg)


def is_trainer_starred(path: str) -> bool:
    """检查路径是否在加星白名单"""
    return str(path) in get_starred_trainers()


def toggle_star_trainer(path: str) -> tuple[bool, str]:
    """切换加星状态。返回 (是否成功, 提示信息)"""
    starred = get_starred_trainers()
    p = str(path)
    if p in starred:
        starred.remove(p)
        set_starred_trainers(starred)
        return True, "已取消收藏"
    else:
        if len(starred) >= STARRED_MAX:
            return False, f"收藏数已达上限（{STARRED_MAX}个），请先取消部分收藏"
        starred.append(p)
        set_starred_trainers(starred)
        return True, "已添加到收藏"
