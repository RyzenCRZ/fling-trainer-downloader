"""爬虫模块 — 爬取 flingtrainer.com 的修改器列表与详情页。

目标站点：https://flingtrainer.com/
支持 Cloudflare 防护自动切换 cloudscraper。
"""
import re

import requests
import cloudscraper
from bs4 import BeautifulSoup

from utils import get_logger

# 站点基础 URL（字符串拼接使用）
BASE_URL = "https://flingtrainer.com"

# 浏览器 User-Agent
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 文件大小正则（形如 1.2 MB / 500 KB）
_SIZE_RE = re.compile(r"[\d.]+\s*(?:TB|GB|MB|KB|B)")
# 日期正则（形如 2024-01-31）
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def fetch_page(url: str) -> str | None:
    """获取页面 HTML 文本。

    先用 requests（带浏览器 User-Agent）请求，超时 15 秒。
    若状态码 403 或响应含 "cloudflare"（不区分大小写），
    则切换 cloudscraper.create_scraper() 重试。
    返回 HTML 文本或 None。
    """
    logger = get_logger()
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        # 检测 Cloudflare 防护：403 状态码或响应体含 cloudflare
        if resp.status_code == 403 or "cloudflare" in resp.text.lower():
            logger.info(f"检测到 Cloudflare 防护，切换 cloudscraper 重试: {url}")
            scraper = cloudscraper.create_scraper()
            resp = scraper.get(url, timeout=15)
        if resp.status_code == 200:
            return resp.text
        logger.warning(f"获取页面失败 [HTTP {resp.status_code}]: {url}")
        return None
    except Exception as e:
        logger.error(f"请求页面异常: {url} - {e}")
        return None


def parse_all_trainers(html: str) -> list[dict]:
    """解析 /all-trainers/ 页面，返回修改器列表。

    遍历所有 <a> 标签，筛选 href 含 /trainer/ 的链接，
    链接文本去掉末尾 " Trainer" 作为 name_en，
    detail_url 为完整 URL（BASE_URL + href）。
    返回 [{name_en, detail_url}, ...]
    """
    soup = BeautifulSoup(html, "html.parser")
    mods = []
    seen = set()  # 用于 detail_url 去重
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/trainer/" not in href:
            continue
        # 链接文本作为英文名，去掉末尾 " Trainer"
        name_en = a.get_text(strip=True)
        if name_en.endswith(" Trainer"):
            name_en = name_en[:-len(" Trainer")].strip()
        if not name_en:
            continue
        # 拼接完整 URL（字符串拼接）
        if href.startswith("http"):
            detail_url = href
        else:
            detail_url = BASE_URL + href
        if detail_url in seen:
            continue
        seen.add(detail_url)
        mods.append({"name_en": name_en, "detail_url": detail_url})
    return mods


def _extract_text_after(text: str, marker: str) -> str:
    """在 text 中查找 marker，返回其后的内容（取到换行前，去除首尾标点）"""
    idx = text.find(marker)
    if idx < 0:
        return ""
    after = text[idx + len(marker):].strip()
    # 取到换行或回车前
    after = after.split("\n")[0].split("\r")[0].strip()
    # 去除尾部常见标点
    return after.rstrip(",;:.").strip()


def parse_detail_page(html: str) -> dict:
    """解析详情页。

    提取：
    - 版本：含 "Game Version:" 的文本，提取冒号后的内容
    - 选项数：含 "Options" 的文本（如 "33 Options"）
    - 最后更新：含 "Last Updated:" 的文本，提取日期
    - 下载列表："Download" 标题后的表格，每行提取文件名、下载 URL、文件大小、添加日期。
      注意区分 "Auto-Updating Version" 与 "Standalone Versions" 两个分区。
    返回 {version, options_count, last_updated, downloads: [...]}
    """
    soup = BeautifulSoup(html, "html.parser")
    result = {
        "version": "",
        "options_count": "",
        "last_updated": "",
        "downloads": [],
    }

    text = soup.get_text(" ", strip=True)

    # 提取版本号
    result["version"] = _extract_text_after(text, "Game Version:")

    # 提取选项数：搜索 "Options" 文本（如 "33 Options"）
    if "Options" in text:
        idx = text.find("Options")
        # 先尝试从 Options 前面找数字（"33 Options"）
        before = text[:idx].rstrip()
        parts = before.split()
        if parts and parts[-1].isdigit():
            result["options_count"] = parts[-1]
        else:
            # 再尝试从 Options 后面找数字（"Options: 33"）
            after = text[idx + len("Options"):].strip().lstrip(":").strip()
            after_parts = after.split()
            for part in after_parts:
                if part.isdigit():
                    result["options_count"] = part
                    break

    # 提取最后更新日期
    result["last_updated"] = _extract_text_after(text, "Last Updated:")

    # 提取下载列表：找到 "Download" 标题后的表格
    # 先定位 Download 标题元素
    download_heading = None
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "strong", "b"]):
        heading_text = tag.get_text(strip=True).lower()
        if heading_text == "download" or heading_text.startswith("download"):
            download_heading = tag
            break

    # 收集待解析的表格
    tables = []
    if download_heading:
        # 从 Download 标题向后查找所有表格（覆盖 Auto-Updating 与 Standalone 两个分区）
        node = download_heading
        while node is not None:
            node = node.find_next(["table", "h1", "h2", "h3", "h4", "h5", "h6"])
            if node is None:
                break
            if node.name == "table":
                tables.append(node)
            # 遇到与下载无关的新大标题则停止（避免误抓页面其它内容）
            elif node.name in ("h1", "h2", "h3") and "download" not in node.get_text(strip=True).lower():
                # 仅在标题明显离开下载区时停止；含 download 字样的标题（如子分区）继续
                break

    # 若未通过标题找到表格，退而求其次：解析页面全部表格
    if not tables:
        tables = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            # 至少需要 2 个单元格，且行内含 <a> 链接
            if len(cells) < 2:
                continue
            a = row.find("a", href=True)
            if not a:
                continue
            file_name = a.get_text(strip=True)
            if not file_name:
                continue
            download_url = a["href"]
            if download_url.startswith("/"):
                download_url = BASE_URL + download_url

            # 从其余单元格文本中识别文件大小与添加日期
            file_size = ""
            date_added = ""
            for cell in cells:
                cell_text = cell.get_text(" ", strip=True)
                if not file_size:
                    size_match = _SIZE_RE.search(cell_text)
                    if size_match:
                        file_size = size_match.group(0).strip()
                if not date_added:
                    date_match = _DATE_RE.search(cell_text)
                    if date_match:
                        date_added = date_match.group(0)

            result["downloads"].append({
                "file_name": file_name,
                "download_url": download_url,
                "file_size": file_size,
                "date_added": date_added,
            })

    return result


def fetch_and_parse() -> list[dict]:
    """主入口：获取 all-trainers 页面并解析，返回修改器列表。

    失败返回空列表并记日志。
    """
    logger = get_logger()
    url = BASE_URL + "/all-trainers/"
    html = fetch_page(url)
    if not html:
        logger.error("获取 all-trainers 页面失败，返回空列表")
        return []
    mods = parse_all_trainers(html)
    logger.info(f"解析到 {len(mods)} 个修改器")
    return mods


def fetch_detail(detail_url: str) -> dict | None:
    """获取并解析详情页，失败返回 None"""
    logger = get_logger()
    html = fetch_page(detail_url)
    if not html:
        logger.error(f"获取详情页失败: {detail_url}")
        return None
    return parse_detail_page(html)
