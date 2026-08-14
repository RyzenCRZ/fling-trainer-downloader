"""Cheat Engine Loader — GUI 主程序"""
import sys
import os
from pathlib import Path
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem, QLabel,
    QStatusBar, QProgressBar, QDialog, QFormLayout, QSpinBox, QCheckBox,
    QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QTextEdit, QSplitter, QComboBox, QMenu
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QIcon, QPixmap, QPainter, QLinearGradient, QBrush, QPen

from version import APP_VERSION

# ============================================================
# 全局 QSS 深色主题样式表（Apple Design + Material Design 风格）
# ============================================================
MODERN_QSS = """
QWidget {
    background-color: #1E1E2E;
    color: #E0E0E0;
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
}
QMainWindow { background-color: #1E1E2E; }

QLineEdit {
    background-color: #2D2D3F;
    border: 1px solid #3D3D5C;
    border-radius: 8px;
    padding: 8px 12px;
    color: #E0E0E0;
    selection-background-color: #007AFF;
}
QLineEdit:focus { border: 2px solid #007AFF; }
QLineEdit::placeholder { color: #6D6D8D; }

QPushButton {
    background-color: #007AFF;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: 500;
}
QPushButton:hover { background-color: #0051D5; }
QPushButton:pressed { background-color: #0040A8; }
QPushButton:disabled { background-color: #3D3D5C; color: #6D6D8D; }

QListWidget {
    background-color: #2D2D3F;
    border: 1px solid #3D3D5C;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}
QListWidget::item { padding: 8px 12px; border-radius: 4px; }
QListWidget::item:hover { background-color: #3D3D5C; }
QListWidget::item:selected { background-color: #007AFF; color: white; }

QProgressBar {
    background-color: #2D2D3F;
    border: none;
    border-radius: 8px;
    text-align: center;
    color: #E0E0E0;
    min-height: 24px;
}
QProgressBar::chunk {
    background-color: #007AFF;
    border-radius: 8px;
}

QSplitter::handle { background-color: #3D3D5C; }
QSplitter::handle:hover { background-color: #007AFF; }

QTableWidget {
    background-color: #2D2D3F;
    border: 1px solid #3D3D5C;
    border-radius: 8px;
    gridline-color: #3D3D5C;
    outline: none;
}
QTableWidget::item { padding: 6px; }
QTableWidget::item:selected { background-color: #007AFF; color: white; }
QHeaderView::section {
    background-color: #353548;
    color: #E0E0E0;
    border: none;
    padding: 8px;
    font-weight: bold;
}

QStatusBar {
    background-color: #1A1A28;
    color: #8D8DA0;
    border-top: 1px solid #3D3D5C;
}

QGroupBox {
    border: 1px solid #3D3D5C;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 16px;
    color: #B0B0C0;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
}

QCheckBox { color: #E0E0E0; spacing: 8px; }
QCheckBox::indicator {
    width: 18px; height: 18px;
    border-radius: 4px;
    border: 2px solid #3D3D5C;
    background: #2D2D3F;
}
QCheckBox::indicator:checked { background: #007AFF; border-color: #007AFF; }

QMenuBar {
    background-color: #1A1A28;
    color: #E0E0E0;
    border-bottom: 1px solid #3D3D5C;
    padding: 2px;
}
QMenuBar::item { padding: 6px 12px; border-radius: 4px; }
QMenuBar::item:selected { background-color: #007AFF; }
QMenu {
    background-color: #2D2D3F;
    border: 1px solid #3D3D5C;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item { padding: 8px 24px; border-radius: 4px; }
QMenu::item:selected { background-color: #007AFF; }

QScrollBar:vertical {
    background: #1E1E2E;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #4D4D6C;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #007AFF; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #1E1E2E;
    height: 10px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: #4D4D6C;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background: #007AFF; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QLabel { color: #E0E0E0; }
QToolTip {
    background-color: #2D2D3F;
    color: #E0E0E0;
    border: 1px solid #3D3D5C;
    border-radius: 6px;
    padding: 4px 8px;
}
"""


# ============================================================
# 自定义组件：动画进度条
# ============================================================
class AnimatedProgressBar(QProgressBar):
    """带平滑动画和渐变色的进度条"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anim = None
        self.setTextVisible(True)

    def setValue(self, value):
        if self._anim:
            self._anim.stop()
        self._anim = QPropertyAnimation(self, b"value")
        self._anim.setDuration(300)
        self._anim.setStartValue(self.value())
        self._anim.setEndValue(value)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()

    def paintEvent(self, event):
        from PyQt5.QtWidgets import QStyle, QStyleOptionProgressBar
        opt = QStyleOptionProgressBar()
        self.initStyleOption(opt)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制背景
        bg_rect = self.rect().adjusted(0, 0, -1, -1)
        painter.setBrush(QColor("#2D2D3F"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(bg_rect, 8, 8)

        # 绘制 chunk（渐变色）
        if self.maximum() > 0 and self.value() > 0:
            chunk_width = int(bg_rect.width() * self.value() / self.maximum())
            chunk_rect = bg_rect.adjusted(0, 0, -(bg_rect.width() - chunk_width), 0)
            if chunk_width > 0:
                gradient = QLinearGradient(0, 0, chunk_rect.width(), 0)
                gradient.setColorAt(0.0, QColor("#007AFF"))
                gradient.setColorAt(1.0, QColor("#00C6FF"))
                painter.setBrush(QBrush(gradient))
                painter.drawRoundedRect(chunk_rect, 8, 8)

        # 绘制文字
        text = f"{self.value()}%"
        painter.setPen(QColor("#E0E0E0"))
        font = QFont("Microsoft YaHei UI", 9, QFont.Medium)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, text)


class ChargingProgressBar(AnimatedProgressBar):
    """绿色分段「充电格」进度条 — 用于下载场景，每 5% 绿一格实时更新"""

    def setValue(self, value):
        # 覆盖父类 300ms 动画，直接更新，保证格子随下载进度离散、即时跳变
        QProgressBar.setValue(self, value)

    def paintEvent(self, event):
        from PyQt5.QtWidgets import QStyle, QStyleOptionProgressBar
        opt = QStyleOptionProgressBar()
        self.initStyleOption(opt)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(0, 0, -1, -1)

        # 背景
        painter.setBrush(QColor("#2D2D3F"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 8, 8)

        # 分段格子（20 格，每格 5%）
        seg_count = 20
        gap = 2.0
        total_gap = gap * (seg_count - 1)
        avail_width = rect.width()
        seg_width = (avail_width - total_gap) / seg_count
        seg_height = rect.height() - 8
        seg_y = rect.y() + 4

        # 不确定模式（maximum==0）：全部灰色格子
        if self.maximum() <= 0:
            x = float(rect.x())
            for i in range(seg_count):
                w = (rect.x() + rect.width() - x) if i == seg_count - 1 else seg_width
                painter.setBrush(QColor("#3A3A4C"))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(
                    int(round(x)), int(seg_y), int(round(w)), int(seg_height), 3, 3
                )
                x += seg_width + gap
            painter.setPen(QColor("#FFFFFF"))
            font = QFont("Microsoft YaHei UI", 9, QFont.Medium)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, "下载中…")
            return

        ratio = self.value() / self.maximum()
        filled = int(round(seg_count * ratio))

        x = float(rect.x())
        for i in range(seg_count):
            # 最后一格补齐到右边界，避免浮点取整误差
            w = (rect.x() + rect.width() - x) if i == seg_count - 1 else seg_width
            color = QColor("#30D158") if i < filled else QColor("#3A3A4C")
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(
                int(round(x)), int(seg_y), int(round(w)), int(seg_height), 3, 3
            )
            x += seg_width + gap

        # 百分比文字
        text = f"{self.value()}%"
        painter.setPen(QColor("#FFFFFF"))
        font = QFont("Microsoft YaHei UI", 9, QFont.Medium)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, text)


# ============================================================
# 自定义组件：带动画的对话框基类
# ============================================================
class AnimatedDialog(QDialog):
    """带淡入缩放动画的对话框基类"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowOpacity(0.0)
        self._fade_anim = None
        self._closing = False

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(200)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_anim.start()

    def closeEvent(self, event):
        if self._closing:
            super().closeEvent(event)
            return
        self._closing = True
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(150)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.InCubic)
        self._fade_anim.finished.connect(self._force_close)
        self._fade_anim.start()
        event.ignore()

    def _force_close(self):
        self._closing = False
        # 用 done() 直接结束对话框，避免再次触发 closeEvent 造成淡出动画重复闪烁
        self.done(self.result())


import config
import database
import scraper
import translator
import downloader
import search as search_module
from utils import get_logger, format_size, format_speed, format_time

logger = get_logger()

# ============================================================
# 后台线程
# ============================================================

class UpdateWorker(QThread):
    """后台抓取修改器列表"""
    finished = pyqtSignal(int)   # 抓取到的条目数
    error = pyqtSignal(str)      # 错误信息

    def run(self):
        try:
            mods = scraper.fetch_and_parse()
            if mods:
                database.upsert_mods(mods)
                database.set_last_update(datetime.now().isoformat())
                self.finished.emit(len(mods))
            else:
                self.error.emit("未获取到数据，可能网络错误或被反爬拦截")
        except Exception as e:
            logger.error(f"更新数据失败: {e}", exc_info=True)
            self.error.emit(str(e))


class SearchWorker(QThread):
    """后台搜索 — 拼音/缩写/模糊多策略"""
    results = pyqtSignal(list)   # 结果列表 [{name_cn, name_en, detail_url, match_score, mod_id}, ...]
    error = pyqtSignal(str)

    def __init__(self, keyword: str):
        super().__init__()
        self.keyword = keyword

    def run(self):
        try:
            keyword = self.keyword.strip()
            is_chinese_query = search_module.is_chinese(keyword)

            # 1. 通过 GameSearcher 进行多策略搜索（拼音/缩写/模糊）
            try:
                searcher = search_module.get_searcher()
                dict_results = searcher.search(keyword, limit=30)
            except Exception as e:
                logger.warning(f"词典搜索失败: {e}")
                dict_results = []

            # 2. 从数据库查找匹配的修改器
            db_matches = []
            seen_urls = set()

            if not is_chinese_query:
                # 英文/拼音查询：先用子串搜索（SQL LIKE），再用模糊匹配补充
                direct_matches = database.search_mods_substring(keyword, limit=30)
                fuzzy_matches = database.search_mods(keyword, threshold=85, limit=30)
                for m in direct_matches + fuzzy_matches:
                    if m['detail_url'] not in seen_urls:
                        db_matches.append(m)
                        seen_urls.add(m['detail_url'])
            else:
                # 中文查询：翻译兜底 + 中文名直接匹配（弥补词典覆盖不全）
                # 2a. 翻译中文→英文，再对数据库英文名做子串+模糊搜索
                try:
                    en_kw = translator.translate(keyword, target='en')
                except Exception:
                    en_kw = keyword
                if en_kw and en_kw != keyword:
                    en_matches = database.search_mods_substring(en_kw, limit=30)
                    en_fuzzy = database.search_mods(en_kw, threshold=85, limit=20)
                    for m in en_matches + en_fuzzy:
                        if m['detail_url'] not in seen_urls:
                            db_matches.append(m)
                            seen_urls.add(m['detail_url'])

                # 2b. 直接按数据库 name_cn 中文名匹配
                cn_matches = database.search_mods_by_cn(keyword, limit=30)
                for m in cn_matches:
                    if m['detail_url'] not in seen_urls:
                        db_matches.append(m)
                        seen_urls.add(m['detail_url'])

                # 2c. 中文转拼音，再对数据库英文名做子串+模糊搜索
                #     实现拼音/汉语同等：卡赞→kazan 能命中 Khazan（词典未收录也能搜到）
                try:
                    py_kw = search_module.to_pinyin(keyword)[0]
                except Exception:
                    py_kw = ""
                if py_kw and len(py_kw) >= 2:
                    py_direct = database.search_mods_substring(py_kw, limit=30)
                    py_fuzzy = database.search_mods(py_kw, threshold=85, limit=20)
                    for m in py_direct + py_fuzzy:
                        if m['detail_url'] not in seen_urls:
                            db_matches.append(m)
                            seen_urls.add(m['detail_url'])

            # 用词典匹配到的英文名查数据库（中文/英文查询都走此路径）
            for dr in dict_results[:15]:
                en_name = dr['en']
                if not en_name:
                    continue

                # 精确匹配优先
                exact = database.get_mod_by_name(en_name)
                if exact and exact.get('detail_url'):
                    exact['match_score'] = max(exact.get('match_score', 0), dr.get('score', 90))
                    if exact['detail_url'] not in seen_urls:
                        db_matches.append(exact)
                        seen_urls.add(exact['detail_url'])
                    continue

                # 高阈值模糊匹配兜底
                extra = database.search_mods(en_name, threshold=92, limit=3)
                for m in extra:
                    if m['detail_url'] not in seen_urls:
                        db_matches.append(m)
                        seen_urls.add(m['detail_url'])

            logger.info(f"[Search] '{keyword}': dict={len(dict_results)}, db={len(db_matches)}")

            # 3. 构建结果
            dict_en_to_cn = {}
            for dr in dict_results:
                if dr['en'] and dr['cn']:
                    dict_en_to_cn[dr['en']] = dr['cn']

            results = []
            for m in db_matches:
                name_en = m['name_en']
                name_cn = dict_en_to_cn.get(name_en) or m.get('name_cn') or name_en
                if name_cn == name_en:
                    try:
                        translated = translator.translate(name_en, target='zh')
                        if translated and translated != name_en:
                            name_cn = translated
                    except Exception:
                        pass

                if m.get('id'):
                    database.update_mod_cn_name(m['id'], name_cn)

                score = m.get('match_score', 0)
                results.append({
                    'mod_id': m.get('id'),
                    'name_cn': name_cn,
                    'name_en': name_en,
                    'detail_url': m['detail_url'],
                    'match_score': score,
                    'version': m.get('version', ''),
                })

            # 4. 补充词典中匹配但数据库未收录的（仅高分结果）
            db_en_names = {r['name_en'].lower() for r in results}
            for dr in dict_results:
                if dr['en'].lower() not in db_en_names and dr.get('score', 0) >= 90:
                    results.append({
                        'mod_id': None,
                        'name_cn': dr['cn'] or dr['en'],
                        'name_en': dr['en'],
                        'detail_url': '',
                        'match_score': dr['score'],
                        'version': '',
                    })

            # 5. 质量过滤：match_score < 80 的结果丢弃
            filtered = [r for r in results if r.get('match_score', 0) >= 80]
            if not filtered and results:
                filtered = results[:3]  # 至少保留前3条

            # 去重（按英文名）
            seen_en = set()
            deduped = []
            for r in filtered:
                en_key = r['name_en'].lower()
                if en_key not in seen_en:
                    seen_en.add(en_key)
                    deduped.append(r)

            self.results.emit(deduped)
        except Exception as e:
            logger.error(f"搜索失败: {e}", exc_info=True)
            self.error.emit(str(e))


class DetailWorker(QThread):
    """后台获取详情页"""
    finished = pyqtSignal(dict)  # 详情数据
    error = pyqtSignal(str)

    def __init__(self, detail_url: str):
        super().__init__()
        self.detail_url = detail_url

    def run(self):
        try:
            data = scraper.fetch_detail(self.detail_url)
            if data:
                self.finished.emit(data)
            else:
                self.error.emit("获取详情失败")
        except Exception as e:
            logger.error(f"获取详情失败: {e}", exc_info=True)
            self.error.emit(str(e))


class DictUpdateWorker(QThread):
    """后台抓取多源数据并构建游戏词典"""
    progress = pyqtSignal(str, int, int)  # stage, current, total
    finished = pyqtSignal(int)  # 条目数
    error = pyqtSignal(str)

    def run(self):
        try:
            from dict_builder import DictBuilder
            builder = DictBuilder(
                progress_cb=lambda s, c, t: self.progress.emit(s, c, t)
            )
            dict_data = builder.build()
            builder.save(dict_data)  # 默认保存到用户目录
            self.finished.emit(len(dict_data))
        except Exception as e:
            logger.error(f"词典更新失败: {e}", exc_info=True)
            self.error.emit(str(e))


# ============================================================
# 对话框
# ============================================================

class FirstRunDialog(AnimatedDialog):
    """首次运行引导 — 选择下载盘符"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择下载路径")
        self.setFixedSize(420, 200)
        self._selected_path = None

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("请选择修改器下载保存位置："))
        layout.addWidget(QLabel("将在所选盘符下创建「风灵月影修改器」文件夹"))

        # 盘符按钮列表
        btn_layout = QHBoxLayout()
        drives = config.get_available_drives()
        for drive in drives:
            btn = QPushButton(drive)
            btn.setFixedSize(60, 40)
            btn.clicked.connect(lambda _, d=drive: self._select_drive(d))
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

        # 自定义路径
        custom_btn = QPushButton("选择其他文件夹...")
        custom_btn.clicked.connect(self._select_custom)
        layout.addWidget(custom_btn)

        # 提示
        self.label_hint = QLabel("")
        self.label_hint.setStyleSheet("color: #666;")
        layout.addWidget(self.label_hint)

    def _select_drive(self, drive: str):
        path = os.path.join(drive + "\\", "风灵月影修改器")
        self._selected_path = path
        self.label_hint.setText(f"将创建：{path}")
        self._confirm()

    def _select_custom(self):
        path = QFileDialog.getExistingDirectory(self, "选择下载文件夹")
        if path:
            self._selected_path = os.path.join(path, "风灵月影修改器")
            self.label_hint.setText(f"将创建：{self._selected_path}")
            self._confirm()

    def _confirm(self):
        if self._selected_path:
            try:
                config.set_download_path(self._selected_path)
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建文件夹失败：{e}")

    def get_path(self) -> str | None:
        return self._selected_path


class SettingsDialog(AnimatedDialog):
    """设置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(520, 660)
        self.setMinimumSize(500, 600)

        cfg = config.load_config()
        layout = QVBoxLayout(self)

        # 下载路径
        path_group = QGroupBox("下载路径")
        path_layout = QHBoxLayout(path_group)
        self.path_label = QLabel(cfg.get("download_path", "未设置"))
        self.path_label.setMinimumWidth(300)
        path_layout.addWidget(self.path_label)
        btn_browse = QPushButton("修改...")
        btn_browse.clicked.connect(self._change_path)
        path_layout.addWidget(btn_browse)
        layout.addWidget(path_group)

        # 游戏词典
        dict_group = QGroupBox("游戏词典")
        dict_layout = QVBoxLayout(dict_group)

        dict_btn_layout = QHBoxLayout()
        self.btn_update_dict = QPushButton("更新游戏词典（多源抓取）")
        self.btn_update_dict.clicked.connect(self._update_dict)
        dict_btn_layout.addWidget(self.btn_update_dict)
        dict_btn_layout.addStretch()
        dict_layout.addLayout(dict_btn_layout)

        self.label_dict_status = QLabel()
        self._update_translation_status()
        dict_layout.addWidget(self.label_dict_status)
        layout.addWidget(dict_group)

        # 更新间隔
        interval_group = QGroupBox("数据更新间隔")
        interval_layout = QHBoxLayout(interval_group)
        interval_layout.addWidget(QLabel("每"))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 168)
        self.spin_interval.setValue(cfg.get("update_interval_hours", 24))
        interval_layout.addWidget(self.spin_interval)
        interval_layout.addWidget(QLabel("小时自动更新"))
        interval_layout.addStretch()
        layout.addWidget(interval_group)

        # 本地修改器排序
        sort_group = QGroupBox("本地修改器排序")
        sort_layout = QHBoxLayout(sort_group)
        sort_layout.addWidget(QLabel("排序方式："))
        self.combo_sort_mode = QComboBox()
        self.combo_sort_mode.addItem("按下载时间（最新在前）", "time")
        self.combo_sort_mode.addItem("按首字母（A→Z）", "name")
        current_mode = cfg.get("sort_mode", "time")
        idx = self.combo_sort_mode.findData(current_mode)
        if idx >= 0:
            self.combo_sort_mode.setCurrentIndex(idx)
        sort_layout.addWidget(self.combo_sort_mode)
        sort_layout.addStretch()
        sort_hint = QLabel(f"⭐ 收藏修改器始终置顶（最多 {config.STARRED_MAX} 个）")
        sort_hint.setStyleSheet("color: #8D8DA0; font-size: 9pt;")
        sort_layout2 = QVBoxLayout()
        sort_layout2.addLayout(sort_layout)
        sort_layout2.addWidget(sort_hint)
        sort_group.setLayout(sort_layout2)
        layout.addWidget(sort_group)

        # 保存按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self._save)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _update_translation_status(self):
        """更新词典状态显示"""
        status = translator.get_translation_status()
        if status.get('dict_loaded'):
            dict_count = status.get('dict_count', 0)
            self.label_dict_status.setWordWrap(True)
            self.label_dict_status.setText(f"✅ 游戏词典已加载（{dict_count} 条）")
        else:
            self.label_dict_status.setWordWrap(True)
            self.label_dict_status.setText("❌ 游戏词典未加载")

    def _update_dict(self):
        """后台调用 dict_builder 更新游戏词典"""
        self._dict_worker = DictUpdateWorker()
        self._dict_worker.progress.connect(self._on_dict_progress)
        self._dict_worker.finished.connect(self._on_dict_done)
        self._dict_worker.error.connect(self._on_dict_error)
        self._dict_worker.start()
        self.btn_update_dict.setEnabled(False)
        self.label_dict_status.setText("正在抓取游戏词典...")

    def _on_dict_progress(self, stage, current, total):
        self.label_dict_status.setText(f"词典构建中：{stage} {current}/{total}")

    def _on_dict_done(self, count):
        self.btn_update_dict.setEnabled(True)
        translator.reload_game_dict()
        search_module.reload_searcher()
        QMessageBox.information(self, "完成", f"词典已更新（共 {count} 条）")
        self._update_translation_status()

    def _on_dict_error(self, err):
        self.btn_update_dict.setEnabled(True)
        QMessageBox.warning(self, "失败", f"词典更新失败：{err}")
        self._update_translation_status()

    def _change_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择下载文件夹")
        if path:
            full_path = os.path.join(path, "风灵月影修改器")
            self.path_label.setText(full_path)

    def _save(self):
        cfg = config.load_config()
        cfg["update_interval_hours"] = self.spin_interval.value()
        cfg["sort_mode"] = self.combo_sort_mode.currentData()
        new_path = self.path_label.text()
        if new_path and new_path != "未设置":
            try:
                config.set_download_path(new_path)
            except Exception as e:
                QMessageBox.warning(self, "警告", f"下载路径设置失败：{e}")
        config.save_config(cfg)
        self.accept()


class DetailDialog(AnimatedDialog):
    """修改器详情对话框"""

    def __init__(self, mod_info: dict, download_path: str, parent=None):
        super().__init__(parent)
        self.mod_info = mod_info
        self.download_path = download_path
        self.detail_data = None
        self.download_worker = None

        self.setWindowTitle(f"修改器详情 — {mod_info.get('name_cn', mod_info.get('name_en', ''))}")
        self.resize(700, 500)

        layout = QVBoxLayout(self)

        # 基本信息
        info_text = f"""
        <h3>{mod_info.get('name_cn', '')}</h3>
        <p><b>英文名：</b>{mod_info.get('name_en', '')}</p>
        <p><b>匹配度：</b>{mod_info.get('match_score', 0)}%</p>
        <p><b>版本：</b>{mod_info.get('version', '加载中...')}</p>
        """
        info_label = QLabel(info_text)
        info_label.setTextFormat(Qt.RichText)
        layout.addWidget(info_label)

        # 下载列表表格
        layout.addWidget(QLabel("下载列表："))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["文件名", "大小", "日期", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        # 进度条（绿色充电格样式）
        self.progress_bar = ChargingProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # 关闭按钮
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self._on_close)
        layout.addWidget(btn_close)

        # 后台获取详情
        self.detail_worker = DetailWorker(mod_info['detail_url'])
        self.detail_worker.finished.connect(self._on_detail_loaded)
        self.detail_worker.error.connect(self._on_detail_error)
        self.detail_worker.start()

    def _on_detail_loaded(self, data: dict):
        self.detail_data = data
        # 更新版本信息
        version = data.get('version', '')
        if version:
            self.mod_info['version'] = version

        downloads = data.get('downloads', [])
        self.table.setRowCount(len(downloads))
        for i, dl in enumerate(downloads):
            self.table.setItem(i, 0, QTableWidgetItem(dl.get('file_name', '')))
            self.table.setItem(i, 1, QTableWidgetItem(dl.get('file_size', '')))
            self.table.setItem(i, 2, QTableWidgetItem(dl.get('date_added', '')))
            btn = QPushButton("下载")
            btn.clicked.connect(lambda _, d=dl: self._start_download(d))
            self.table.setCellWidget(i, 3, btn)

        if not downloads:
            self.status_label.setText("未找到下载链接")

    def _on_detail_error(self, err: str):
        self.status_label.setText(f"获取详情失败：{err}")

    def _start_download(self, dl_info: dict):
        url = dl_info.get('download_url', '')
        file_name = dl_info.get('file_name', 'trainer.zip')
        if not url:
            QMessageBox.warning(self, "警告", "下载链接无效")
            return

        # 检查下载路径
        dl_path = config.get_download_path()
        if not dl_path:
            QMessageBox.warning(self, "警告", "下载路径无效，请在设置中重新配置")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"正在下载：{file_name}")

        self.download_worker = downloader.DownloadWorker(
            str(url), str(dl_path), file_name,
            game_name=self.mod_info.get('name_cn') or self.mod_info.get('name_en', ''),
            referer_url=self.mod_info.get('detail_url', '')
        )
        self.download_worker.progress.connect(self._on_download_progress)
        self.download_worker.finished.connect(self._on_download_done)
        self.download_worker.error.connect(self._on_download_error)
        self.download_worker.start()

    def _on_download_progress(self, percent: int, speed: str, remaining: str):
        if percent < 0:
            # 未知总大小：进入不确定进度模式
            self.progress_bar.setRange(0, 0)
            self.status_label.setText(f"下载中... 速度: {speed}（总大小未知）")
            return
        # 恢复正常确定进度模式
        if self.progress_bar.maximum() == 0:
            self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(percent)
        self.status_label.setText(f"下载中... {percent}%  速度: {speed}  剩余: {remaining}")

    def _on_download_done(self, file_path: str):
        self.progress_bar.setValue(100)
        self.status_label.setText(f"下载完成：{file_path}")
        QMessageBox.information(self, "下载完成", f"文件已保存到：\n{file_path}")
        # 记录下载历史
        try:
            mod_id = self.mod_info.get('mod_id')
            if mod_id and self.detail_data:
                file_name = Path(file_path).name
                database.add_download(mod_id, file_name, file_path, "")
        except Exception as e:
            logger.warning(f"记录下载历史失败: {e}")
        # 刷新主窗口的本地修改器列表
        try:
            parent = self.parent()
            if parent and hasattr(parent, '_refresh_local_trainers'):
                parent._refresh_local_trainers()
        except Exception:
            pass

    def _on_download_error(self, err: str):
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"下载失败：{err}")
        QMessageBox.critical(self, "下载失败", err)

    def _on_close(self):
        if self.download_worker and self.download_worker.isRunning():
            reply = QMessageBox.question(
                self, "确认", "下载仍在进行中，确定关闭？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
            self.download_worker.cancel()
            self.download_worker.wait(3000)
        self.accept()


# ============================================================
# 主窗口
# ============================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cheat Engine Loader")
        self.resize(1000, 650)

        self.search_worker = None
        self.update_worker = None
        self._local_trainers = []  # 本地修改器列表

        self._init_ui()
        self._init_data()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # 顶部工具栏
        top_layout = QHBoxLayout()
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("输入游戏名称、拼音或缩写（如：只狼 / zhilang / DS3）...")
        self.input_search.returnPressed.connect(self._do_search)
        top_layout.addWidget(self.input_search, stretch=1)

        btn_search = QPushButton("搜索")
        btn_search.clicked.connect(self._do_search)
        top_layout.addWidget(btn_search)

        btn_update = QPushButton("手动更新")
        btn_update.clicked.connect(self._do_update)
        top_layout.addWidget(btn_update)

        btn_settings = QPushButton("设置")
        btn_settings.clicked.connect(self._open_settings)
        top_layout.addWidget(btn_settings)

        main_layout.addLayout(top_layout)

        # 双栏布局：左=本地修改器  右=搜索结果
        splitter = QSplitter(Qt.Horizontal)

        # === 左栏：本地修改器管理 ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("已下载修改器："))
        self.input_local_search = QLineEdit()
        self.input_local_search.setPlaceholderText("筛选本地修改器...")
        self.input_local_search.textChanged.connect(self._filter_local_trainers)
        left_layout.addWidget(self.input_local_search)

        self.list_local = QListWidget()
        self.list_local.itemDoubleClicked.connect(self._launch_local_trainer)
        self.list_local.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_local.customContextMenuRequested.connect(self._show_local_context_menu)
        left_layout.addWidget(self.list_local)

        local_btn_layout = QHBoxLayout()
        btn_launch = QPushButton("启动")
        btn_launch.clicked.connect(self._launch_local_trainer)
        local_btn_layout.addWidget(btn_launch)
        btn_delete = QPushButton("删除")
        btn_delete.clicked.connect(self._delete_local_trainer)
        local_btn_layout.addWidget(btn_delete)
        btn_delete_all = QPushButton("一键清空")
        btn_delete_all.clicked.connect(self._delete_all_local_trainers)
        local_btn_layout.addWidget(btn_delete_all)
        btn_open_dir = QPushButton("打开目录")
        btn_open_dir.clicked.connect(self._open_download_dir)
        local_btn_layout.addWidget(btn_open_dir)
        btn_refresh = QPushButton("刷新")
        btn_refresh.clicked.connect(self._refresh_local_trainers)
        local_btn_layout.addWidget(btn_refresh)
        left_layout.addLayout(local_btn_layout)

        splitter.addWidget(left_widget)

        # === 右栏：在线搜索结果 ===
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_layout.addWidget(QLabel("搜索结果（双击下载）："))
        self.list_results = QListWidget()
        self.list_results.itemDoubleClicked.connect(self._on_item_double_clicked)
        right_layout.addWidget(self.list_results)

        splitter.addWidget(right_widget)

        # 设置分割比例
        splitter.setSizes([400, 600])
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        main_layout.addWidget(splitter)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.progress_bar = AnimatedProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedWidth(200)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.version_label = QLabel(f"v{APP_VERSION}")
        self.version_label.setStyleSheet("color: #8D8DA0; padding: 0 8px;")
        self.status_bar.addPermanentWidget(self.version_label)
        self.label_status = QLabel("就绪")
        self.status_bar.addWidget(self.label_status)

        # 菜单栏
        menubar = self.menuBar()
        menu_help = menubar.addMenu("帮助")
        action_log = menu_help.addAction("查看日志")
        action_log.triggered.connect(self._open_log)
        action_whitelist = menu_help.addAction("添加到Defender白名单")
        action_whitelist.triggered.connect(self._add_defender_whitelist)
        action_about = menu_help.addAction("关于")
        action_about.triggered.connect(self._show_about)

    def _init_data(self):
        """初始化数据：检查下载路径、数据库"""
        # 1. 检查下载路径
        dl_path = config.get_download_path()
        if not dl_path:
            self._show_first_run_dialog()

        # 2. 初始化数据库
        database.init_db()

        # 3. 检查数据是否过期
        count = database.get_mod_count()
        last_update = database.get_last_update()
        if last_update:
            self.label_status.setText(f"数据量：{count}  最后更新：{last_update[:19]}")
        else:
            self.label_status.setText("无数据")

        if count == 0 or database.is_data_stale(
            config.load_config().get("update_interval_hours", 24)
        ):
            self._do_update()

        # 4. 扫描本地修改器
        self._refresh_local_trainers()

    # ============================================================
    # 本地修改器管理
    # ============================================================

    def _refresh_local_trainers(self):
        """扫描下载目录，刷新本地修改器列表（支持加星显示和排序）"""
        self.list_local.clear()
        self._local_trainers = []

        dl_path = config.get_download_path()
        if not dl_path or not os.path.isdir(dl_path):
            self._populate_local_list([])
            return

        dl_dir = Path(dl_path)

        # 收集所有 .exe 文件
        for f in dl_dir.rglob('*.exe'):
            name = f.name.lower()
            if any(skip in name for skip in ['unins', 'setup', 'update.exe']):
                continue
            self._local_trainers.append(self._build_local_trainer(f, dl_dir))

        # 扫描无扩展名的文件，检测是否为 PE/EXE
        for f in dl_dir.rglob('*'):
            if not f.is_file():
                continue
            if f.suffix:
                continue
            try:
                with open(f, 'rb') as fh:
                    header = fh.read(2)
                if header == b'MZ':
                    new_path = f.with_suffix('.exe')
                    f.rename(new_path)
                    self._local_trainers.append(self._build_local_trainer(new_path, dl_dir))
            except Exception:
                pass

        # 排序：加星置顶 → 按 sort_mode 排序
        sort_mode = config.get_sort_mode()
        if sort_mode == "name":
            self._local_trainers.sort(key=lambda x: (0 if x['starred'] else 1, x['name'].lower()))
        else:
            self._local_trainers.sort(key=lambda x: (0 if x['starred'] else 1, -x.get('mtime', 0)))

        self._populate_local_list(self._local_trainers)
        count_all = len(self._local_trainers)
        count_star = sum(1 for t in self._local_trainers if t['starred'])
        self.label_status.setText(
            f"本地修改器：{count_all} 个（⭐ {count_star}）  |  数据量：{database.get_mod_count()}"
        )

    def _build_local_trainer(self, filepath: Path, dl_dir: Path) -> dict:
        """构建本地修改器条目（含加星状态和修改时间）"""
        rel_path = filepath.relative_to(dl_dir)
        display_name = self._translate_trainer_name(filepath.stem)
        try:
            mtime = filepath.stat().st_mtime
        except Exception:
            mtime = 0
        return {
            'name': display_name,
            'file_name': filepath.name,
            'path': str(filepath),
            'rel_path': str(rel_path),
            'mtime': mtime,
            'starred': config.is_trainer_starred(str(filepath)),
        }

    def _populate_local_list(self, trainers: list):
        """填充本地修改器列表（加星条目前加 ⭐）"""
        self.list_local.clear()
        for t in trainers:
            prefix = "⭐ " if t.get('starred') else "   "
            item = QListWidgetItem(f"{prefix}{t['name']}")
            item.setData(Qt.UserRole, t)
            item.setToolTip(f"路径: {t['path']}\n"
                           f"收藏: {'是（永不删除）' if t.get('starred') else '否'}")
            self.list_local.addItem(item)

    def _translate_trainer_name(self, name: str) -> str:
        """尝试将修改器文件名翻译为中文名"""
        try:
            import search as search_module
            searcher = search_module.get_searcher()
            for en, cn in searcher.en_to_cn.items():
                if en.lower() in name.lower() or name.lower() in en.lower():
                    if cn:
                        return f"{cn}（{name}）"
        except Exception:
            pass
        return name

    def _show_local_context_menu(self, pos):
        """本地修改器列表右键菜单：加星/取消收藏"""
        item = self.list_local.itemAt(pos)
        if not item:
            return
        data = item.data(Qt.UserRole)
        if not data:
            return

        menu = QMenu(self)
        starred = data.get('starred', False)
        action_star = menu.addAction("★ 取消收藏" if starred else "☆ 添加收藏（永不删除）")
        menu.addSeparator()
        action_launch = menu.addAction("▶ 启动修改器")
        action_open_dir = menu.addAction("📂 打开所在目录")
        action_delete = menu.addAction("🗑 删除此修改器")

        global_pos = self.list_local.mapToGlobal(pos)
        chosen = menu.exec_(global_pos)

        if chosen == action_star:
            ok, msg = config.toggle_star_trainer(data['path'])
            if not ok:
                QMessageBox.warning(self, "收藏失败", msg)
            else:
                self._refresh_local_trainers()
        elif chosen == action_launch:
            self._launch_local_trainer(item)
        elif chosen == action_open_dir:
            try:
                parent_dir = str(Path(data['path']).parent)
                os.startfile(parent_dir)
            except Exception as e:
                QMessageBox.critical(self, "失败", f"无法打开目录：{e}")
        elif chosen == action_delete:
            self.list_local.setCurrentItem(item)
            self._delete_local_trainer()

    def _filter_local_trainers(self):
        """根据搜索框过滤本地修改器"""
        keyword = self.input_local_search.text().strip().lower()
        if not keyword:
            self._populate_local_list(self._local_trainers)
            return

        filtered = [t for t in self._local_trainers if keyword in t['name'].lower()]
        self._populate_local_list(filtered)

    def _launch_local_trainer(self, item=None):
        """启动选中的本地修改器"""
        if item is None:
            item = self.list_local.currentItem()
        if not item:
            QMessageBox.warning(self, "提示", "请先选择一个修改器")
            return

        data = item.data(Qt.UserRole)
        if not data:
            return

        try:
            os.startfile(data['path'])
            logger.info(f"启动修改器: {data['path']}")
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"无法启动修改器：{e}")

    def _delete_local_trainer(self):
        """删除选中的本地修改器"""
        item = self.list_local.currentItem()
        if not item:
            QMessageBox.warning(self, "提示", "请先选择一个修改器")
            return

        data = item.data(Qt.UserRole)
        if not data:
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除以下修改器吗？\n\n{data['name']}\n{data['path']}",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            os.remove(data['path'])
            logger.info(f"已删除修改器: {data['path']}")
            self._refresh_local_trainers()
        except Exception as e:
            QMessageBox.critical(self, "删除失败", f"无法删除文件：{e}")

    def _delete_all_local_trainers(self):
        """一键清空所有非收藏修改器（白名单保护）"""
        if not self._local_trainers:
            QMessageBox.information(self, "提示", "本地暂无修改器可清理")
            return

        starred = [t for t in self._local_trainers if t.get('starred')]
        unstarred = [t for t in self._local_trainers if not t.get('starred')]

        if not unstarred:
            if starred:
                QMessageBox.information(self, "提示",
                    f"所有 {len(starred)} 个修改器均为⭐收藏（白名单保护），无需清理")
            return

        reply = QMessageBox.question(
            self, "一键清空",
            f"即将删除 {len(unstarred)} 个未收藏的修改器。\n"
            f"⭐ {len(starred)} 个收藏修改器将保留（永不删除）。\n\n"
            f"此操作不可撤销，确定继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        deleted = 0
        failed = 0
        for t in unstarred:
            try:
                os.remove(t['path'])
                deleted += 1
                logger.info(f"批量删除: {t['path']}")
            except Exception as e:
                failed += 1
                logger.warning(f"批量删除失败 {t['path']}: {e}")

        msg = f"已删除 {deleted} 个修改器"
        if failed:
            msg += f"，{failed} 个删除失败"
        if starred:
            msg += f"（⭐ {len(starred)} 个收藏已保留）"
        QMessageBox.information(self, "完成", msg)
        self._refresh_local_trainers()

    def _open_download_dir(self):
        """打开下载目录"""
        dl_path = config.get_download_path()
        if dl_path and os.path.isdir(dl_path):
            os.startfile(dl_path)
        else:
            QMessageBox.warning(self, "提示", "下载目录不存在，请在设置中重新配置")

    def _add_defender_whitelist(self):
        """将下载目录添加到 Windows Defender 排除列表"""
        import subprocess
        dl_path = config.get_download_path()
        if not dl_path:
            QMessageBox.warning(self, "提示", "下载路径未设置")
            return

        reply = QMessageBox.question(
            self, "添加白名单",
            f"将以管理员权限将以下路径添加到 Windows Defender 排除列表：\n\n{dl_path}\n\n"
            "这可以防止修改器被误报为病毒。\n是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            # 通过 PowerShell 以管理员权限执行
            ps_cmd = f'Start-Process powershell -Verb RunAs -ArgumentList \'-Command', \
                     f'Add-MpPreference -ExclusionPath "{dl_path}";', \
                     f'Write-Host "已添加白名单"; Start-Sleep -Seconds 2\''
            subprocess.Popen(
                ['powershell', '-Command',
                 f'Start-Process powershell -Verb RunAs -ArgumentList '
                 f'\'-Command "Add-MpPreference -ExclusionPath \\"{dl_path}\\"; '
                 f'Write-Host \\"已添加白名单\\"; Start-Sleep -Seconds 2"\''],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            QMessageBox.information(self, "已执行", "请在弹出的 UAC 窗口中确认添加白名单。")
        except Exception as e:
            QMessageBox.critical(self, "失败", f"添加白名单失败：{e}\n"
                                "可手动在 Windows 安全中心 → 病毒和威胁防护 → 排除项中添加。")

    def _show_first_run_dialog(self):
        """首次运行引导"""
        while True:
            dialog = FirstRunDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                path = dialog.get_path()
                if path:
                    QMessageBox.information(self, "下载路径", f"下载路径已设置为：\n{path}")
                    break
            else:
                # 用户取消，提示必须选择
                reply = QMessageBox.critical(
                    self, "必须选择",
                    "必须选择下载路径才能使用本程序。\n是否重新选择？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    sys.exit(0)

    def _do_search(self):
        keyword = self.input_search.text().strip()
        if not keyword:
            return

        # 检查数据是否存在
        if database.get_mod_count() == 0:
            QMessageBox.information(self, "提示", "数据正在加载中，请稍后再试")
            return

        self.label_status.setText("搜索中...")
        self.list_results.clear()

        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.quit()
            self.search_worker.wait(2000)

        self.search_worker = SearchWorker(keyword)
        self.search_worker.results.connect(self._on_search_results)
        self.search_worker.error.connect(self._on_search_error)
        self.search_worker.start()

    def _on_search_results(self, results: list):
        if not results:
            self.label_status.setText("未找到匹配结果")
            return

        for item in results:
            name_cn = item.get('name_cn', item['name_en'])
            name_en = item['name_en']
            score = item.get('match_score', 0)
            # 双语显示：中文名（英文名）
            if name_cn and name_cn != name_en:
                display = f"{name_cn}（{name_en}）"
            else:
                display = name_en

            list_item = QListWidgetItem(display)
            tooltip = f"英文名: {name_en}\n中文名: {name_cn}\n匹配度: {score}%\n版本: {item.get('version', '未知')}"
            list_item.setToolTip(tooltip)
            # 存储完整数据供双击使用
            list_item.setData(Qt.UserRole, item)
            self.list_results.addItem(list_item)

        self.label_status.setText(f"找到 {len(results)} 个结果")

    def _on_search_error(self, err: str):
        self.label_status.setText(f"搜索失败：{err}")
        QMessageBox.warning(self, "搜索失败", err)

    def _do_update(self):
        self.label_status.setText("正在更新数据...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度

        if self.update_worker and self.update_worker.isRunning():
            return

        self.update_worker = UpdateWorker()
        self.update_worker.finished.connect(self._on_update_done)
        self.update_worker.error.connect(self._on_update_error)
        self.update_worker.start()

    def _on_update_done(self, count: int):
        self.progress_bar.setVisible(False)
        last_update = database.get_last_update()
        time_str = last_update[:19] if last_update else ""
        self.label_status.setText(f"更新成功：{count} 个修改器  更新时间：{time_str}")

    def _on_update_error(self, err: str):
        self.progress_bar.setVisible(False)
        count = database.get_mod_count()
        if count > 0:
            self.label_status.setText(f"更新失败（使用缓存数据：{count} 个）：{err}")
        else:
            self.label_status.setText(f"更新失败：{err}")
            QMessageBox.critical(self, "更新失败", f"获取数据失败：\n{err}\n\n请检查网络连接后重试。")

    def _on_item_double_clicked(self, item: QListWidgetItem):
        mod_info = item.data(Qt.UserRole)
        if not mod_info:
            return

        # 如果没有详情页链接，说明数据库未收录
        if not mod_info.get('detail_url'):
            game_name = mod_info.get('name_cn', mod_info.get('name_en', ''))
            QMessageBox.information(
                self, "暂无下载链接",
                f"《{game_name}》在当前修改器库中未收录。\n\n"
                f"请尝试点击「手动更新」按钮刷新修改器列表。"
            )
            return

        dl_path = config.get_download_path()
        if not dl_path:
            QMessageBox.warning(self, "警告", "下载路径无效，请重新设置")
            self._show_first_run_dialog()
            return

        dialog = DetailDialog(mod_info, str(dl_path), self)
        dialog.exec_()

    def _open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # 排序设置可能变化，刷新本地列表
            self._refresh_local_trainers()

    def _open_log(self):
        log_path = Path.home() / ".fling_trainer" / "logs" / "app.log"
        if log_path.exists():
            dialog = QDialog(self)
            dialog.setWindowTitle("应用日志")
            dialog.resize(800, 600)
            layout = QVBoxLayout(dialog)
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            with open(log_path, "r", encoding="utf-8") as f:
                # 只读最后 1000 行
                lines = f.readlines()
                text_edit.setPlainText("".join(lines[-1000:]))
            layout.addWidget(text_edit)
            btn_close = QPushButton("关闭")
            btn_close.clicked.connect(dialog.accept)
            layout.addWidget(btn_close)
            dialog.exec_()
        else:
            QMessageBox.information(self, "日志", "暂无日志文件")

    def _show_about(self):
        QMessageBox.about(
            self, "关于",
            "<h3>Cheat Engine Loader</h3>"
            "<p>快速搜索并下载游戏修改器</p>"
            "<p>数据来源：flingtrainer.com</p>"
        )


# ============================================================
# 程序入口
# ============================================================

def create_app_icon():
    """加载应用图标 — 优先 .ico 文件，回退到代码生成"""
    import sys as _sys
    # 1. 尝试加载 .ico 文件
    if getattr(_sys, 'frozen', False):
        ico_path = Path(_sys._MEIPASS) / 'assets' / 'app_icon.ico'
    else:
        ico_path = Path(__file__).parent / 'assets' / 'app_icon.ico'
    if ico_path.exists():
        return QIcon(str(ico_path))
    # 2. 回退：代码生成简单图标
    from PyQt5.QtCore import Qt
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#007AFF"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
    painter.setPen(QColor("#ffffff"))
    font = QFont("Arial", 32, QFont.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "F")
    painter.end()
    return QIcon(pixmap)


def _check_single_instance() -> bool:
    """Windows 单实例检查：通过命名互斥锁防止多开"""
    try:
        import ctypes
        mutex_name = "FlingTrainer_Mutex_v1"
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return False
        # 保持 mutex 引用防止被 GC
        _check_single_instance._mutex = mutex
    except Exception:
        pass  # 检查失败不阻止启动
    return True


def main():
    # 单实例检查
    if not _check_single_instance():
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "程序已在运行中", "提示", 0x40)
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setApplicationName("Cheat Engine Loader")
    app.setWindowIcon(create_app_icon())

    # 设置全局字体
    font = QFont("Microsoft YaHei UI", 9)
    app.setFont(font)

    # 应用现代深色主题 QSS
    app.setStyleSheet(MODERN_QSS)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
