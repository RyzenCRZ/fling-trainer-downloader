"""开发态脚本：抓取多源 → 翻译 → 生成 game_dict.json

用法：
    # 直接构建词典（依赖内置词典翻译补全）
    python scripts/build_dict.py

    # 指定输出路径
    python scripts/build_dict.py --output ./game_dict.json

    # 跳过特定源
    python scripts/build_dict.py --skip metacritic,ign

    # 只抓取不翻译（生成 raw.json）
    python scripts/build_dict.py --no-translate
"""
import argparse
import json
import sys
from pathlib import Path

# 添加父目录到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dict_builder import DictBuilder


def main():
    parser = argparse.ArgumentParser(description="构建 game_dict.json 多源词典")
    parser.add_argument('--output', '-o', default='game_dict.json',
                        help='输出文件路径（默认：game_dict.json）')
    parser.add_argument('--skip', default='',
                        help='跳过的数据源（逗号分隔：fling,metacritic,3dm,gamersky,ign）')
    parser.add_argument('--no-translate', action='store_true',
                        help='只抓取不翻译（生成 raw.json，含未翻译条目）')
    parser.add_argument('--metacritic-pages', type=int, default=30,
                        help='Metacritic 抓取页数（默认 30）')
    parser.add_argument('--threedm-pages', type=int, default=50,
                        help='3DM 抓取页数（默认 50）')
    args = parser.parse_args()

    skip = [s.strip() for s in args.skip.split(',') if s.strip()] if args.skip else []

    builder = DictBuilder(
        progress_cb=lambda s, c, t: print(f"[{s}] {c}/{t}")
    )

    if args.no_translate:
        # 仅抓取，不翻译
        raw = builder.gather_raw(skip)
        # 转为可序列化格式
        serializable = [{"en": en, "cn": cn, "src": src} for en, cn, src in raw]
        out_path = Path(args.output)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
        print(f"\n已保存原始数据到 {out_path}（共 {len(raw)} 条）")
        print("提示：可人工补充中文名后，用 --no-translate=false 重新生成词典")
    else:
        dict_data = builder.build(skip)
        builder.save(dict_data, Path(args.output))
        print(f"\n已生成词典到 {args.output}（共 {len(dict_data)} 条）")


if __name__ == '__main__':
    main()
