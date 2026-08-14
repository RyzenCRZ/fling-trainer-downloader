# 风灵月影修改器搜索下载器（Cheat Engine Loader）

一个基于 PyQt5 的 Windows 桌面工具，用于搜索、下载并管理游戏修改器（Trainer）。数据来源为 [flingtrainer.com](https://flingtrainer.com)。

## 功能特性

- **多策略搜索**：支持中文、英文、拼音、拼音缩写及模糊音搜索（如「只狼 / zhilang / DS3」）
- **游戏词典**：内置多源抓取的 `game_dict.json`，可在设置中在线更新扩充
- **断点续传下载**：基于 cloudscraper 绕过 Cloudflare，支持 Range 续传与实时进度
- **自动解压归档**：下载后自动识别 `.exe` / `.zip` / `.7z` / `.rar`，解压并归类到游戏名文件夹
- **本地修改器管理**：启动、删除、一键清空、收藏（加星白名单，永不误删）、按时间/名称排序
- **中英互译缓存**：翻译结果持久化到 SQLite，减少重复请求
- **现代深色主题 UI**：含分段「充电格」下载进度条与动画

## 技术栈

- Python 3.14
- PyQt5（GUI）
- requests / cloudscraper（网络请求与反爬）
- beautifulsoup4 / lxml（页面解析）
- rapidfuzz（模糊匹配）
- pypinyin / zhon（拼音与中文处理）
- PyInstaller（打包为单文件 exe）

## 项目结构

```
fling_trainer/
├── main.py           # GUI 主程序
├── config.py         # 配置读写（~/.fling_trainer/config.json）
├── database.py       # SQLite 数据层（修改器 / 翻译缓存 / 下载记录）
├── scraper.py        # 抓取 flingtrainer.com
├── translator.py     # 翻译引擎（含缓存）
├── downloader.py     # 断点续传下载 + 解压归档
├── search.py         # 拼音 / 缩写 / 模糊搜索
├── dict_builder.py   # 多源游戏词典构建
├── game_dict.json    # 游戏中英词典
├── utils.py          # 日志与格式化工具
├── version.py        # 版本号（打包时自动递增）
├── build.spec        # PyInstaller 打包配置
├── assets/           # 应用图标
├── dependency/       # 内置 7z 解压工具
├── scripts/          # 构建 / 词典生成脚本
└── requirements.txt  # 依赖列表
```

## 开发运行

```powershell
# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

首次运行会引导选择修改器下载保存路径，运行时数据（数据库、日志、配置）保存在 `%USERPROFILE%\.fling_trainer` 下。

## 打包

```powershell
python scripts/build.py
```

打包产物输出到 `dist/`（已通过 `.gitignore` 排除）。`dependency/` 下的 7z 工具会在打包时一并内置，用于 `.7z` / `.rar` 解压与便携式自解压。

## 免责声明

本项目仅用于个人学习与技术研究。请遵守相关网站的服务条款与当地法律法规，尊重软件著作权，勿将下载内容用于商业用途。
