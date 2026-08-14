"""下载器模块 — 基于 PyQt5 QThread 的断点续传下载器。

支持断点续传：若目标文件已存在部分内容，通过 Range 请求头续传。
使用 cloudscraper 绕过 Cloudflare 反爬保护。
下载完成后自动识别文件类型（PE/ZIP/7Z），解压压缩包并组织到游戏名文件夹。
提供进度、完成、错误三个信号供主线程更新 UI。
"""
import os
import shutil
import struct
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

import cloudscraper
import requests
from PyQt5.QtCore import QThread, pyqtSignal

from utils import format_speed, format_time, get_logger

# 单次读取块大小：1KB
CHUNK_SIZE = 1024

# 压缩包扩展名
ARCHIVE_EXTENSIONS = {'.zip', '.7z', '.rar'}

# 7z.exe 路径（打包内置或开发态项目目录）
def _get_7z_path() -> str | None:
    """获取 7z.exe 路径，不存在返回 None"""
    import sys
    if getattr(sys, 'frozen', False):
        p = Path(sys._MEIPASS) / 'dependency' / '7z.exe'
    else:
        p = Path(__file__).parent / 'dependency' / '7z.exe'
    return str(p) if p.exists() else None


def extract_archive(archive_path: str, dest_dir: str) -> bool:
    """解压压缩包到目标目录

    支持 .zip（内置 zipfile）和 .7z/.rar（需 7z.exe）。
    """
    archive_path = Path(archive_path)
    ext = archive_path.suffix.lower()

    if ext == '.zip':
        try:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(dest_dir)
            return True
        except Exception as e:
            get_logger().warning(f"zipfile 解压失败: {e}")
            # 尝试用 7z

    # 尝试用 7z.exe
    sevenz = _get_7z_path()
    if sevenz:
        try:
            result = subprocess.run(
                [sevenz, 'x', '-y', str(archive_path), f'-o{dest_dir}'],
                capture_output=True, timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            if result.returncode == 0:
                return True
            get_logger().warning(f"7z 解压失败: {result.stderr.decode(errors='replace')}")
        except Exception as e:
            get_logger().warning(f"7z 调用异常: {e}")

    return False


def find_trainer_exe(directory: str) -> str | None:
    """在目录中查找修改器 .exe 文件

    优先返回文件名包含 'trainer' 的 .exe。
    """
    directory = Path(directory)
    if not directory.is_dir():
        return None

    # 优先找包含 "trainer" 的 .exe
    for f in directory.rglob('*.exe'):
        if 'trainer' in f.name.lower():
            return str(f)

    # 其次找任何 .exe（排除常见系统文件）
    for f in directory.rglob('*.exe'):
        name = f.name.lower()
        if not any(skip in name for skip in ['unins', 'setup', 'update']):
            return str(f)

    return None


def _detect_file_type(filepath: str) -> str:
    """检测文件实际类型，返回扩展名（.exe/.zip/.7z/.rar）或空字符串"""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(16)
        if header[:2] == b'MZ':
            return '.exe'
        if header[:4] == b'PK\x03\x04':
            return '.zip'
        if header[:6] == b'\x37\x7a\xbc\xaf\x27\x1c':
            return '.7z'
        if header[:3] == b'Rar':
            return '.rar'
        return ''
    except Exception:
        return ''


def _get_filename_from_response(resp, default_name: str) -> str:
    """从 HTTP 响应的 Content-Disposition 解析真实文件名"""
    cd = resp.headers.get('content-disposition', '')
    if not cd:
        return default_name

    # 尝试提取 filename*=UTF-8''xxx 或 filename="xxx"
    import re
    # 优先处理 RFC 5987: filename*=UTF-8''filename.ext
    match = re.search(r"filename\*=UTF-8''([^;]+)", cd, re.IGNORECASE)
    if match:
        from urllib.parse import unquote
        decoded = unquote(match.group(1))
        return decoded

    # 处理 filename="filename.ext"
    match = re.search(r'filename="([^"]+)"', cd)
    if match:
        return match.group(1)

    # 处理 filename=filename.ext
    match = re.search(r'filename=([^;]+)', cd)
    if match:
        name = match.group(1).strip()
        if name.startswith('"') and name.endswith('"'):
            name = name[1:-1]
        return name

    return default_name


def organize_trainer(downloaded_path: str, dest_dir: str, game_name: str) -> str:
    """整理下载的修改器：识别文件类型、解压、组织到以游戏名命名的文件夹

    :param downloaded_path: 下载的文件路径
    :param dest_dir: 下载根目录
    :param game_name: 游戏名称（用于命名文件夹）
    :return: 最终修改器文件路径
    """
    logger = get_logger()
    downloaded_path = Path(downloaded_path)

    # 1. 检测真实文件类型（从 magic bytes）
    detected_ext = _detect_file_type(str(downloaded_path))
    current_ext = downloaded_path.suffix.lower()

    # 2. 如果没有扩展名或扩展名不匹配真实类型，重命名
    if detected_ext and detected_ext != current_ext:
        new_path = downloaded_path.with_suffix(detected_ext)
        downloaded_path.rename(new_path)
        logger.info(f"文件类型检测: {current_ext or '无'} → {detected_ext}，重命名为 {new_path.name}")
        downloaded_path = new_path
        current_ext = detected_ext

    # 3. PE/EXE 文件：直接组织到游戏文件夹
    if current_ext == '.exe':
        logger.info(f"检测到 PE/EXE 文件，直接组织")
        return _move_to_game_folder(str(downloaded_path), dest_dir, game_name)

    # 4. 压缩包：解压后组织
    if current_ext in ARCHIVE_EXTENSIONS:
        logger.info(f"检测到压缩包 {current_ext}，开始解压")
        return _extract_and_organize(str(downloaded_path), dest_dir, game_name)

    # 5. 其他类型：原样返回
    logger.info(f"未知文件类型 ({current_ext})，原样返回: {downloaded_path.name}")
    return str(downloaded_path)


def _move_to_game_folder(filepath: str, dest_dir: str, game_name: str) -> str:
    """将 PE/EXE 文件移动到游戏名文件夹"""
    logger = get_logger()
    src = Path(filepath)
    safe_name = _sanitize_filename(game_name)
    game_folder = Path(dest_dir) / safe_name
    game_folder.mkdir(parents=True, exist_ok=True)

    final_path = game_folder / src.name
    if final_path.exists():
        final_path.unlink()
    shutil.move(str(src), str(final_path))
    logger.info(f"修改器已组织到: {final_path}")
    return str(final_path)


def _extract_and_organize(archive_path: str, dest_dir: str, game_name: str) -> str:
    """解压压缩包并组织到游戏名文件夹"""
    logger = get_logger()
    archive = Path(archive_path)
    temp_dir = Path(tempfile.gettempdir()) / 'fling_trainer_extract'
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"正在解压: {archive.name}")
    if not extract_archive(str(archive), str(temp_dir)):
        logger.warning(f"解压失败，保留原始压缩包: {archive}")
        return str(archive)

    trainer_exe = find_trainer_exe(str(temp_dir))
    if not trainer_exe:
        logger.warning("未在压缩包中找到修改器 .exe，保留原始压缩包")
        return str(archive)

    return _move_to_game_folder(trainer_exe, dest_dir, game_name)


def _sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符"""
    for ch in '<>:"/\\|?*':
        name = name.replace(ch, '_')
    return name.strip()


class DownloadWorker(QThread):
    """断点续传下载线程。

    信号：
        progress(int, str, str) — percent, speed_str, remaining_str
        finished(str)           — file_path（解压组织后的最终路径）
        error(str)              — error_message
    """

    # 进度信号：百分比、速度字符串、剩余时间字符串
    progress = pyqtSignal(int, str, str)
    # 完成信号：文件路径
    finished = pyqtSignal(str)
    # 错误信号：错误信息
    error = pyqtSignal(str)

    def __init__(self, url, dest_dir, file_name, game_name='', referer_url=''):
        """初始化下载任务。

        :param url: 下载地址
        :param dest_dir: 目标目录
        :param file_name: 文件名
        :param game_name: 游戏名称（用于解压后创建文件夹，可选）
        :param referer_url: 来源页面 URL（用于绕过 Cloudflare 检测）
        """
        super().__init__()
        self.url = url
        self.dest_dir = dest_dir
        self.file_name = file_name
        self.game_name = game_name or Path(file_name).stem
        self.referer_url = referer_url
        self._cancelled = False

    def run(self):
        """执行下载（支持断点续传）+ 解压组织。"""
        logger = get_logger()
        try:
            # 1. 构建请求头
            headers = {
                'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/120.0.0.0 Safari/537.36'),
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            if self.referer_url:
                headers['Referer'] = self.referer_url

            # 2. 使用 cloudscraper 发起请求（绕过 Cloudflare）
            scraper = cloudscraper.create_scraper()

            # 下载前先通过 HEAD 请求确认文件总大小（解决 chunked 无 content-length 的问题）
            total_probe = 0
            try:
                head_resp = scraper.head(self.url, headers=headers, timeout=30)
                total_probe = int(head_resp.headers.get('content-length', 0) or 0)
            except Exception:
                total_probe = 0

            resp = scraper.get(self.url, stream=True, headers=headers, timeout=60)

            # 3. 从响应解析真实文件名（Content-Disposition 包含 .exe 扩展名）
            real_filename = _get_filename_from_response(resp, self.file_name)
            dest_path = Path(self.dest_dir) / real_filename

            # 如果真实文件名与请求的不同，删除旧文件
            if real_filename != self.file_name:
                old_path = Path(self.dest_dir) / self.file_name
                if old_path.exists():
                    old_path.unlink()

            # 4. 已下载字节数（支持断点续传）
            existing_size = dest_path.stat().st_size if dest_path.exists() else 0
            if existing_size > 0:
                headers['Range'] = f'bytes={existing_size}-'
                # 重发请求带 Range 头
                resp = scraper.get(self.url, stream=True, headers=headers, timeout=60)

            # 5. 206：断点续传
            if resp.status_code == 206:
                mode = 'ab'
                content_range = resp.headers.get('content-range', '')
                total = int(content_range.split('/')[-1]) if '/' in content_range else 0
            # 6. 200：完整下载
            elif resp.status_code == 200:
                mode = 'wb'
                existing_size = 0
                total = int(resp.headers.get('content-length', 0) or 0)
            else:
                self.error.emit(f"下载失败，HTTP 状态码: {resp.status_code}")
                return

            # 兜底1：若 total 仍未知，优先用 HEAD 请求拿到的总大小
            if total <= 0 and total_probe > 0:
                total = total_probe

            # 兜底2：若仍未知，尝试从底层 raw 响应获取剩余长度
            if total <= 0:
                try:
                    raw_len = getattr(resp.raw, 'length_remaining', 0)
                    if raw_len and raw_len > 0:
                        total = int(raw_len)
                except Exception:
                    pass

            downloaded = 0
            start_time = time.time()
            last_emit = time.time()

            # 7. 流式写入
            with open(dest_path, mode) as f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    # 取消检查
                    if self._cancelled:
                        logger.info(f"下载已取消: {self.file_name}")
                        break
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)

                    # 按时间间隔（0.1s）或下载完成时更新进度，保证进度条平滑上涨
                    now = time.time()
                    if total > 0:
                        done_downloading = (downloaded + existing_size) >= total
                        percent = int((downloaded + existing_size) / total * 100)
                    else:
                        # 未知总大小：用 -1 表示不确定进度，由 UI 降级显示
                        done_downloading = False
                        percent = -1

                    if now - last_emit >= 0.1 or done_downloading:
                        elapsed = now - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        if done_downloading:
                            percent = 100
                        remaining = (total - downloaded - existing_size) / speed if (speed > 0 and total > 0) else 0
                        self.progress.emit(
                            percent,
                            format_speed(speed),
                            format_time(remaining)
                        )
                        last_emit = now

            # 8. 完成后处理：解压并组织文件
            if not self._cancelled:
                final_path = str(dest_path)
                try:
                    final_path = organize_trainer(
                        str(dest_path), self.dest_dir, self.game_name
                    )
                except Exception as e:
                    logger.warning(f"解压组织失败，使用原始文件: {e}")
                self.finished.emit(final_path)
        except Exception as e:
            # 9. 异常时发射错误信号
            logger.error(f"下载异常: {e}")
            self.error.emit(str(e))

    def cancel(self):
        """取消下载：设置取消标志，写入循环中检测到后 break。"""
        self._cancelled = True
