"""合并种子词典到 game_dict.json

种子词典包含风灵月影修改器中最热门的 ~150 个游戏的中英对照，
确保即使没有百度密钥，初始词典也有足够覆盖率。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, '.')

# 手动编写的热门游戏中英对照种子
SEED_DICT = {
    # AAA 大作
    "Elden Ring": "艾尔登法环",
    "Sekiro: Shadows Die Twice": "只狼：影逝二度",
    "Dark Souls": "黑暗之魂",
    "Dark Souls II": "黑暗之魂2",
    "Dark Souls III": "黑暗之魂3",
    "Bloodborne": "血源诅咒",
    "Demon's Souls": "恶魔之魂",
    "Cyberpunk 2077": "赛博朋克2077",
    "The Witcher 3: Wild Hunt": "巫师3：狂猎",
    "The Witcher 2: Assassins of Kings": "巫师2：国王刺客",
    "Grand Theft Auto V": "侠盗猎车手5",
    "Grand Theft Auto IV": "侠盗猎车手4",
    "Grand Theft Auto: San Andreas": "侠盗猎车手：圣安地烈斯",
    "Red Dead Redemption 2": "荒野大镖客2",
    "Red Dead Redemption": "荒野大镖客",
    "The Legend of Zelda: Breath of the Wild": "塞尔达传说：旷野之息",
    "The Legend of Zelda: Tears of the Kingdom": "塞尔达传说：王国之泪",
    "God of War": "战神",
    "God of War Ragnarok": "战神：诸神黄昏",
    "Horizon Zero Dawn": "地平线：零之曙光",
    "Horizon Forbidden West": "地平线：西之绝境",
    "Ghost of Tsushima": "对马岛之魂",
    "Spider-Man Remastered": "漫威蜘蛛侠重制版",
    "Marvel's Spider-Man 2": "漫威蜘蛛侠2",
    "The Last of Us Part I": "最后生还者 第一部",
    "The Last of Us Part II": "最后生还者 第二部",
    "Uncharted 4: A Thief's End": "神秘海域4：盗贼末路",
    "Uncharted: The Lost Legacy": "神秘海域：失落的遗产",
    "Resident Evil 2": "生化危机2",
    "Resident Evil 3": "生化危机3",
    "Resident Evil 4": "生化危机4",
    "Resident Evil 7: Biohazard": "生化危机7",
    "Resident Evil Village": "生化危机8：村庄",
    "Devil May Cry 5": "鬼泣5",
    "Monster Hunter: World": "怪物猎人：世界",
    "Monster Hunter Rise": "怪物猎人：崛起",
    "Monster Hunter Wilds": "怪物猎人：荒野",
    "Assassin's Creed Odyssey": "刺客信条：奥德赛",
    "Assassin's Creed Origins": "刺客信条：起源",
    "Assassin's Creed Valhalla": "刺客信条：英灵殿",
    "Assassin's Creed Mirage": "刺客信条：幻景",
    "Far Cry 5": "孤岛惊魂5",
    "Far Cry 6": "孤岛惊魂6",
    "Watch Dogs: Legion": "看门狗：军团",
    "Tom Clancy's The Division 2": "全境封锁2",
    "Starfield": "星空",
    "Fallout 4": "辐射4",
    "The Elder Scrolls V: Skyrim": "上古卷轴5：天际",
    "The Elder Scrolls V: Skyrim Special Edition": "上古卷轴5：天际 特别版",
    "Baldur's Gate 3": "博德之门3",
    "Diablo IV": "暗黑破坏神4",
    "Diablo III": "暗黑破坏神3",
    "Path of Exile": "流放之路",
    "Hollow Knight": "空洞骑士",
    "Hollow Knight: Silksong": "空洞骑士：丝之歌",
    "Hades": "哈迪斯",
    "Hades II": "哈迪斯2",
    "Dead Cells": "死亡细胞",
    "Slay the Spire": "杀戮尖塔",
    "Hollow Knight Voidheart Edition": "空洞骑士 虚心版",
    # RPG
    "Final Fantasy VII Remake": "最终幻想7 重制版",
    "Final Fantasy VII Rebirth": "最终幻想7 重生",
    "Final Fantasy XVI": "最终幻想16",
    "Final Fantasy XV": "最终幻想15",
    "Persona 5 Royal": "女神异闻录5 皇家版",
    "Persona 4 Golden": "女神异闻录4 黄金版",
    "Persona 3 Reload": "女神异闻录3 重载版",
    "Like a Dragon: Infinite Wealth": "如龙8",
    "Like a Dragon Gaiden: The Man Who Erased His Name": "如龙7外传：无名之龙",
    "Yakuza: Like a Dragon": "如龙7：光与暗的去向",
    "Tales of Arise": "破晓传说",
    "Tales of Vesperia: Definitive Edition": "薄暮传说：决定版",
    "Ni no Kuni: Wrath of the White Witch": "二之国：白色圣灰的女王",
    "Ni no Kuni II: Revenant Kingdom": "二之国2：亡灵之国",
    "Dragon Quest XI: Echoes of an Elusive Age": "勇者斗恶龙11",
    "Octopath Traveler": "八方旅人",
    "Octopath Traveler II": "八方旅人2",
    "Triangle Strategy": "三角战略",
    "Fire Emblem: Three Houses": "火焰纹章：风花雪月",
    "Xenoblade Chronicles 3": "异度神剑3",
    "Scarlet Nexus": "绯红结系",
    # 动作冒险
    "Batman: Arkham Knight": "蝙蝠侠：阿卡姆骑士",
    "Batman: Arkham City": "蝙蝠侠：阿卡姆之城",
    "Middle-earth: Shadow of War": "中土世界：战争之影",
    "Middle-earth: Shadow of Mordor": "中土世界：暗影魔多",
    "Tomb Raider": "古墓丽影",
    "Rise of the Tomb Raider": "古墓丽影：崛起",
    "Shadow of the Tomb Raider": "古墓丽影：暗影",
    "Dishonored 2": "耻辱2",
    "Prey": "掠食",
    "Death Stranding": "死亡搁浅",
    "Death Stranding Director's Cut": "死亡搁浅 导演剪辑版",
    "Control": "控制",
    "Alan Wake 2": "心灵杀手2",
    "Returnal": "死亡回归",
    # FPS / 射击
    "DOOM Eternal": "毁灭战士：永恒",
    "DOOM (2016)": "毁灭战士2016",
    "Wolfenstein II: The New Colossus": "德军总部2：新巨像",
    "Call of Duty: Modern Warfare II": "使命召唤：现代战争2",
    "Call of Duty: Black Ops Cold War": "使命召唤：黑色行动 冷战",
    "Call of Duty: Modern Warfare III": "使命召唤：现代战争3",
    "Battlefield V": "战地5",
    "Battlefield 2042": "战地2042",
    "Cyberpunk 2077: Phantom Liberty": "赛博朋克2077：往日之影",
    "Metro Exodus": "地铁：离去",
    "Metro 2033 Redux": "地铁2033 重制版",
    "Metro: Last Light Redux": "地铁：最后的曙光 重制版",
    # 策略 / 模拟
    "Civilization VI": "文明6",
    "Age of Empires II: Definitive Edition": "帝国时代2：决定版",
    "Age of Empires IV": "帝国时代4",
    "Age of Empires III: Definitive Edition": "帝国时代3：决定版",
    "Total War: THREE KINGDOMS": "全面战争：三国",
    "Total War: WARHAMMER III": "全面战争：战锤3",
    "Total War: WARHAMMER II": "全面战争：战锤2",
    "Total War: Shogun 2": "全面战争：将军2",
    "Crusader Kings III": "十字军之王3",
    "Stellaris": "群星",
    "Cities: Skylines": "城市：天际线",
    "Cities: Skylines II": "城市：天际线2",
    "Anno 1800": "纪元1800",
    "Tropico 6": "海岛大亨6",
    "Frostpunk": "冰汽时代",
    "Frostpunk 2": "冰汽时代2",
    "They Are Billions": "亿万僵尸",
    # 沙盒 / 生存
    "Minecraft": "我的世界",
    "Terraria": "泰拉瑞亚",
    "Valheim": "英灵神殿",
    "Rust": "腐蚀",
    "ARK: Survival Evolved": "方舟：生存进化",
    "Don't Starve Together": "饥荒联机版",
    "No Man's Sky": "无人深空",
    "Subnautica": "深海迷航",
    "Subnautica: Below Zero": "深海迷航：零度之下",
    "The Forest": "森林",
    "Sons of the Forest": "森林之子",
    # 独立 / 热门
    "Stardew Valley": "星露谷物语",
    "Terraria": "泰拉瑞亚",
    "Celeste": "蔚蓝",
    "Hollow Knight": "空洞骑士",
    "Cuphead": "茶杯头",
    "Undertale": "传说之下",
    "Deltarune": "三角符文",
    "Ori and the Blind Forest": "奥日与迷失森林",
    "Ori and the Will of the Wisps": "奥日与萤火意志",
    "Shovel Knight": "铲子骑士",
    "Katana ZERO": "武士零",
    "Outer Wilds": "星际拓荒",
    "Disco Elysium": "极乐迪斯科",
    "Disco Elysium: The Final Cut": "极乐迪斯科：最终剪辑版",
    "Spiritfarer": "灵魂摆渡人",
    "Inscryption": "邪恶冥刻",
    "Sifu": "师父",
    "Lies of P": "匹诺曹的谎言",
    "Black Myth: Wukong": "黑神话：悟空",
    "Wukong": "悟空",
    "Palworld": "幻兽帕鲁",
    "Helldivers 2": "绝地潜兵2",
    # 竞速
    "Forza Horizon 5": "极限竞速：地平线5",
    "Forza Horizon 4": "极限竞速：地平线4",
    "Need for Speed Heat": "极品飞车：热度",
    "Need for Speed Unbound": "极品飞车：不羁",
    "Dirt Rally 2.0": "尘埃拉力赛2.0",
    # 恐怖
    "Outlast": "逃生",
    "Outlast 2": "逃生2",
    "Amnesia: The Dark Descent": "失忆症：黑暗后裔",
    "Amnesia: Rebirth": "失忆症：重生",
    "Phasmophobia": "恐鬼症",
    "Resident Evil 2 Remake": "生化危机2 重制版",
    "Resident Evil 3 Remake": "生化危机3 重制版",
    "Resident Evil 4 Remake": "生化危机4 重制版",
    # 其他热门
    "Sea of Thieves": "盗贼之海",
    "Grounded": "禁闭求生",
    "State of Decay 2": "腐烂国度2",
    "Dying Light 2": "消逝的光芒2",
    "Dying Light": "消逝的光芒",
    "Dead Island 2": "死亡岛2",
    "Back 4 Blood": "喋血复仇",
    "World War Z": "僵尸世界大战",
    "The Ascent": "上行战场",
    "Cyberpunk 2077": "赛博朋克2077",
    "Mass Effect Legendary Edition": "质量效应 传奇版",
    "Mass Effect: Andromeda": "质量效应：仙女座",
    "Dragon Age: Inquisition": "龙腾世纪：审判",
    "Dragon Age: The Veilguard": "龙腾世纪：影障守护者",
    "Anthem": "圣歌",
    "Avatar: Frontiers of Pandora": "阿凡达：潘多拉边境",
    "Star Wars Jedi: Fallen Order": "星球大战 绝地：陨落的武士团",
    "Star Wars Jedi: Survivor": "星球大战 绝地：幸存者",
    "Lego Star Wars: The Skywalker Saga": "乐高星球大战：天行者传奇",
    # 常见简写别名（用户搜索时常用简短名称）
    "Sekiro": "只狼",
    "Black Myth: Wukong": "黑神话悟空",
    "The Witcher 3": "巫师3",
    "The Elder Scrolls V": "上古卷轴5",
    "Monster Hunter World": "怪物猎人世界",
    "Monster Hunter Rise": "怪物猎人崛起",
    "GTA V": "侠盗猎车手5",
    "GTA 5": "侠盗5",
    "RDR2": "荒野大镖客2",
    "DS3": "黑魂3",
    "RE4": "生化危机4",
    "RE2": "生化危机2",
    "DMC5": "鬼泣5",
    "MHW": "怪猎世界",
    "Skyrim": "天际",
    "Witcher 3": "巫师3",
    "Elden Ring": "艾尔登法环",
    "Cyberpunk": "赛博朋克",
    "Palworld": "幻兽帕鲁",
    "Stardew Valley": "星露谷物语",
    "Hollow Knight": "空洞骑士",
    "Hades": "哈迪斯",
    "Dead Cells": "死亡细胞",
    "Slay the Spire": "杀戮尖塔",
    "Cuphead": "茶杯头",
    "Celeste": "蔚蓝",
    "Terraria": "泰拉瑞亚",
    "Minecraft": "我的世界",
    "Valheim": "英灵神殿",
    "Subnautica": "深海迷航",
    "Disco Elysium": "极乐迪斯科",
    "Outer Wilds": "星际拓荒",
    "Control": "控制",
    "Returnal": "死亡回归",
    "Sifu": "师父",
    "Lies of P": "匹诺曹的谎言",
    "Helldivers 2": "绝地潜兵2",
    "Frostpunk": "冰汽时代",
    "Stellaris": "群星",
    "Cities: Skylines": "城市天际线",
    "Civilization VI": "文明6",
    "Age of Empires IV": "帝国时代4",
    "Forza Horizon 5": "极限竞速地平线5",
    "Starfield": "星空",
    "Fallout 4": "辐射4",
    "Baldur's Gate 3": "博德之门3",
    "Diablo IV": "暗黑破坏神4",
    "Hogwarts Legacy": "霍格沃茨之遗",
    "Atomic Heart": "原子之心",
    "Wild Hearts": "狂野之心",
    "Dead Island 2": "死亡岛2",
    "Dying Light 2": "消逝的光芒2",
    "Sons of the Forest": "森林之子",
    "Grounded": "禁闭求生",
    "Sea of Thieves": "盗贼之海",
    "Inscryption": "邪恶冥刻",
    "Katana ZERO": "武士零",
    "Kena: Bridge of Spirits": "柯娜：精神之桥",
    "Stray": "流浪",
    "Sackboy": "麻布仔",
    "It Takes Two": "双人成行",
    "Baldur's Gate 3": "博德之门3",
}


def main():
    dict_path = Path('game_dict.json')
    # 读取现有词典
    if dict_path.exists():
        with open(dict_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
        print(f"现有词典：{len(existing)} 条")
    else:
        existing = {}
        print("未找到现有词典，将创建新词典")

    # 构建种子中文→英文反向映射（用于去重）
    seed_cn_to_en = {}
    for en, cn in SEED_DICT.items():
        # 同一中文可能对应多个英文（如 "Resident Evil 4" 和 "Resident Evil 4 Remake"），
        # 取第一个（更通用）
        if cn not in seed_cn_to_en:
            seed_cn_to_en[cn] = en

    # 过滤现有词典：如果某条目的中文在种子中也有，且现有英文不规范（无空格），
    # 则删除现有条目（种子会覆盖）
    removed = 0
    to_remove = []
    for en, cn in existing.items():
        if cn and cn in seed_cn_to_en:
            # 检查现有英文是否规范（含空格通常更规范）
            if ' ' not in en and ' ' in seed_cn_to_en[cn]:
                to_remove.append(en)
                removed += 1
    for en in to_remove:
        del existing[en]
    print(f"过滤不规范英文：{removed} 条")

    # 合并种子词典（种子优先）
    existing.update(SEED_DICT)
    print(f"合并种子后：{len(existing)} 条（种子 {len(SEED_DICT)} 条）")

    # 写回
    with open(dict_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"已保存到 {dict_path}")


if __name__ == '__main__':
    main()
