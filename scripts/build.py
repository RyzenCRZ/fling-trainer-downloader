"""打包脚本 — 自动递增版本号并打包 exe。

用法：python scripts/build.py

流程：
1. 读取项目根目录 version.py 的 APP_VERSION（如 "1.0"）。
2. 用当前版本号执行 PyInstaller 打包（build.spec）。
3. 打包成功后，将版本号小数位 +0.1 写回 version.py（1.0 → 1.1）。
   打包失败则不递增版本号。
"""
import re
import subprocess
import sys
from pathlib import Path

# 项目根目录（scripts/ 的上一级）
ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "version.py"


def read_version() -> str:
    """读取 version.py 中的 APP_VERSION"""
    text = VERSION_FILE.read_text(encoding="utf-8")
    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else "1.0"


def bump_version(current: str) -> str:
    """版本号小数位 +0.1，如 1.0 -> 1.1，1.9 -> 2.0"""
    parts = current.split(".")
    major = int(parts[0])
    minor = int(parts[1]) if len(parts) > 1 else 0
    minor += 1
    if minor >= 10:
        major += 1
        minor = 0
    return f"{major}.{minor}"


def write_version(new: str):
    """写回 version.py"""
    VERSION_FILE.write_text(
        f'"""应用版本号（由打包脚本 scripts/build.py 自动递增）"""\n'
        f'APP_VERSION = "{new}"\n',
        encoding="utf-8",
    )


def main():
    current = read_version()
    print(f"[build] 当前版本: v{current}")

    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "build.spec"]
    print(f"[build] 执行: {' '.join(cmd)}")
    ret = subprocess.run(cmd, cwd=str(ROOT))

    if ret.returncode != 0:
        print(f"[build] 打包失败（退出码 {ret.returncode}），版本号保持 v{current} 不变")
        sys.exit(ret.returncode)

    new_version = bump_version(current)
    write_version(new_version)
    print(f"[build] 打包完成 v{current}，版本号已更新为 v{new_version}（下次打包使用）")


if __name__ == "__main__":
    main()
