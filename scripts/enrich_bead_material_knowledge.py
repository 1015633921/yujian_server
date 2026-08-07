from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import DEFAULT_SQLITE_PATH, connect_database, use_mysql


SERIES_CODE_OVERRIDES = {
    "黑玛瑙": "black_agate",
    "金耀石": "golden_obsidian",
    "银耀石": "silver_obsidian",
    "极光 23": "aurora_23",
    "金太阳阿鲁沙": "arusha_sunstone",
    "毒液黑超七": "black_super_seven",
    "南红玛瑙": "south_red_agate",
    "条纹玛瑙": "banded_agate",
    "盐源玛瑙": "salt_source_agate",
    "阿拉善玛瑙": "alashan_agate",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def j(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def knowledge(
    name: str,
    primary_element: str,
    secondary_elements: list[str],
    chakras: list[str],
    effects: list[str],
    wish_pools: list[str],
    color_family: str,
    mood_tags: list[str],
    visual_tags: list[str],
    story: str,
    texture_features: list[str],
    care_tags: list[str] | None = None,
    transparency_level: str = "semi_transparent",
    batch_variation: str = "medium",
) -> dict[str, Any]:
    return {
        "name": name,
        "primary_element": primary_element,
        "secondary_elements": secondary_elements,
        "chakras": chakras,
        "chakra_weights": {chakra: max(1, len(chakras) - index) for index, chakra in enumerate(chakras)},
        "effects": effects,
        "wish_pools": wish_pools,
        "color_family": color_family,
        "mood_tags": mood_tags,
        "visual_tags": visual_tags,
        "story": story,
        "allowed_roles": ["primary", "support", "accent"],
        "match_rules": ["no_limit"],
        "care_tags": care_tags or ["clean_regularly", "storage_separate"],
        "material_params": {
            "bead_shape": "round",
            "surface_finish": "glossy",
            "transparency_level": transparency_level,
            "texture_features": texture_features,
            "batch_variation": batch_variation,
            "hole_diameter_mm": 1.0,
            "size_tolerance_mm": 0.3,
        },
        "asset": {},
        "enabled": 1,
    }


KNOWLEDGE_BY_CODE: dict[str, dict[str, Any]] = {
    "clear_quartz": knowledge(
        "白水晶",
        "metal",
        ["water"],
        ["crown", "third_eye"],
        ["净化与放大", "清晰秩序", "聚焦意图"],
        ["focus", "study", "protection"],
        "clear",
        ["clarity", "focus"],
        ["transparent", "icy"],
        "白水晶适合做全局调和石，用干净通透的视觉把复杂搭配收束起来，帮助方案保持清晰、轻盈和有秩序。",
        ["clean"],
        transparency_level="transparent",
    ),
    "milky_quartz": knowledge(
        "奶白晶",
        "metal",
        ["earth"],
        ["crown", "heart"],
        ["温和净化", "柔和稳定", "日常陪伴"],
        ["calm", "emotion", "relationship"],
        "white",
        ["softness", "calming"],
        ["milky", "soft_color"],
        "奶白晶的能量表达比白水晶更柔，适合把冷感或强势配色变得亲近，也适合作为日常佩戴里的安定底色。",
        ["cloud"],
        transparency_level="translucent",
    ),
    "rose_quartz": knowledge(
        "粉水晶",
        "wood",
        ["fire"],
        ["heart"],
        ["关系柔和", "自我接纳", "亲密吸引"],
        ["love", "relationship", "emotion"],
        "pink",
        ["softness", "companionship"],
        ["soft_color", "transparent"],
        "粉水晶适合放在需要柔化关系、提升亲和感的方案里，它的重点不是强烈推进，而是让佩戴者更容易打开自己。",
        ["clean", "cloud"],
    ),
    "strawberry_quartz": knowledge(
        "草莓晶",
        "fire",
        ["wood"],
        ["heart", "sacral"],
        ["桃花人缘", "热情表达", "愉悦感"],
        ["love", "relationship", "inspiration"],
        "pink",
        ["vitality", "softness"],
        ["sparkling", "soft_color"],
        "草莓晶比粉水晶更有活力，适合用于需要一点甜感、主动表达和社交气场的手串。",
        ["mineral_inclusion", "sparkling"],
        batch_variation="high",
    ),
    "rhodochrosite": knowledge(
        "红纹石",
        "fire",
        ["earth"],
        ["heart"],
        ["情绪修复", "亲密勇气", "自我价值"],
        ["love", "relationship", "emotion"],
        "pink",
        ["softness", "confidence"],
        ["texture", "soft_color"],
        "红纹石的纹理有明显层次，适合表达更成熟的亲密关系能量，也适合在粉色系里承担主石。",
        ["color_band", "texture"],
        care_tags=["avoid_sweat", "clean_regularly", "storage_separate"],
    ),
    "flower_agate": knowledge(
        "樱花玛瑙",
        "fire",
        ["earth"],
        ["heart", "root"],
        ["温柔生长", "关系修复", "内在安全感"],
        ["love", "emotion", "health"],
        "pink",
        ["softness", "companionship"],
        ["texture", "soft_color"],
        "樱花玛瑙像把花影封在石头里，适合用于温柔、治愈感和低攻击性的粉色搭配。",
        ["mineral_inclusion", "cloud"],
        batch_variation="high",
    ),
    "amethyst": knowledge(
        "紫水晶",
        "fire",
        ["water"],
        ["third_eye", "crown"],
        ["灵感觉察", "专注安定", "睡眠修复"],
        ["focus", "sleep", "inspiration", "study"],
        "purple",
        ["calming", "clarity"],
        ["transparent", "soft_color"],
        "紫水晶适合需要静心、学习和灵感整理的方案，能把视觉重心从外放拉回内在思考。",
        ["clean", "cloud"],
    ),
    "ametrine": knowledge(
        "紫黄晶",
        "fire",
        ["earth"],
        ["solar_plexus", "third_eye"],
        ["灵感落地", "行动判断", "目标整合"],
        ["career", "inspiration", "focus"],
        "purple",
        ["clarity", "confidence"],
        ["transparent", "color_band"],
        "紫黄晶把紫色的觉察和黄色的行动感放在一起，适合创意、决策和把想法推进成结果的方案。",
        ["color_band", "clean"],
        batch_variation="high",
    ),
    "lepidolite": knowledge(
        "紫锂辉",
        "water",
        ["fire"],
        ["heart", "third_eye"],
        ["情绪缓冲", "压力放松", "温和觉察"],
        ["calm", "emotion", "sleep"],
        "purple",
        ["calming", "softness"],
        ["soft_color", "milky"],
        "紫锂辉更偏柔和舒缓，适合把高能量配方压低一点，让整体佩戴感更安静。",
        ["cloud"],
        care_tags=["avoid_water", "fragile", "clean_regularly", "storage_separate"],
        transparency_level="translucent",
    ),
    "garnet": knowledge(
        "石榴石",
        "fire",
        ["earth"],
        ["root", "solar_plexus"],
        ["活力自信", "身体感", "持续行动"],
        ["career", "health", "love"],
        "red",
        ["vitality", "confidence"],
        ["dark", "sparkling"],
        "石榴石适合需要补一点稳定热度的方案，视觉上沉稳，能量上更偏持续、耐力和自我驱动。",
        ["clean", "sparkling"],
    ),
    "aurora_23": knowledge(
        "极光23",
        "fire",
        ["water", "metal"],
        ["third_eye", "crown", "root"],
        ["多维整合", "灵感觉察", "深层稳定"],
        ["inspiration", "focus", "protection"],
        "purple",
        ["clarity", "boundary"],
        ["texture", "sparkling"],
        "极光23适合做带有矿物层次感的主石，表达综合、转化和内在校准，搭配时建议少量点出重点。",
        ["mineral_inclusion", "texture"],
        batch_variation="high",
    ),
    "rabbit_hair_quartz": knowledge(
        "兔毛水晶",
        "fire",
        ["wood"],
        ["sacral", "solar_plexus"],
        ["热情流动", "灵感牵引", "情绪点亮"],
        ["love", "career", "emotion", "inspiration"],
        "gold",
        ["vitality", "softness"],
        ["texture", "sparkling"],
        "兔毛水晶的发丝更柔，适合把行动力做得轻盈一点；不同颜色可分别偏向温柔、人缘、表达或创作。",
        ["rutile", "texture"],
        batch_variation="high",
    ),
    "gold_rutilated_quartz": knowledge(
        "金发晶",
        "metal",
        ["earth", "fire"],
        ["solar_plexus", "crown"],
        ["财富推进", "目标聚焦", "决断力"],
        ["wealth", "career", "focus"],
        "gold",
        ["confidence", "focus"],
        ["rutile", "sparkling"],
        "金发晶适合作为财富和事业主题的核心石，发丝越明显，视觉推进感越强，搭配时要注意留白。",
        ["rutile", "clean"],
        batch_variation="high",
    ),
    "titanium_quartz": knowledge(
        "钛晶",
        "metal",
        ["fire", "earth"],
        ["solar_plexus", "crown"],
        ["强势推进", "财富启动", "领导气场"],
        ["wealth", "career", "focus"],
        "gold",
        ["confidence", "vitality"],
        ["rutile", "sparkling"],
        "钛晶是高存在感的财富型主石，适合少量做视觉锚点，让整串更有力量和方向。",
        ["rutile", "mineral_inclusion"],
        batch_variation="high",
    ),
    "silver_rutilated_quartz": knowledge(
        "银发晶",
        "metal",
        ["water"],
        ["third_eye", "throat"],
        ["清晰判断", "理性聚焦", "表达边界"],
        ["focus", "communication", "protection"],
        "clear",
        ["clarity", "boundary"],
        ["rutile", "sparkling"],
        "银发晶比金发晶更冷静，适合需要理性判断、清晰表达和减少情绪干扰的方案。",
        ["rutile", "clean"],
        batch_variation="high",
    ),
    "black_rutilated_quartz": knowledge(
        "黑发晶",
        "water",
        ["metal"],
        ["root", "third_eye"],
        ["边界守护", "专注收束", "稳定气场"],
        ["protection", "focus", "career"],
        "black",
        ["boundary", "focus"],
        ["dark", "rutile"],
        "黑发晶适合把能量向内收束，用在需要稳住边界、增强判断和减少外界干扰的搭配里。",
        ["rutile", "dark"],
        batch_variation="high",
    ),
    "red_rutilated_quartz": knowledge(
        "红铜发晶",
        "fire",
        ["metal"],
        ["root", "solar_plexus"],
        ["行动热度", "自信表达", "目标驱动"],
        ["career", "health", "love"],
        "red",
        ["vitality", "confidence"],
        ["rutile", "warm"],
        "红铜发晶的热度更明显，适合需要启动、表达和持续推进的方案，搭配时可用白水晶或茶晶平衡。",
        ["rutile", "warm"],
        batch_variation="high",
    ),
    "green_rutilated_quartz": knowledge(
        "绿发晶",
        "wood",
        ["earth"],
        ["heart", "solar_plexus"],
        ["成长机会", "事业拓展", "稳定专注"],
        ["career", "wealth", "focus"],
        "green",
        ["focus", "confidence"],
        ["rutile", "cat_eye"],
        "绿发晶适合事业成长、资源拓展和稳步推进主题；顺发或猫眼感强的珠子很适合做主石。",
        ["rutile", "cat_eye"],
        batch_variation="high",
    ),
    "white_phantom": knowledge(
        "白幽灵",
        "wood",
        ["metal"],
        ["heart", "root"],
        ["复原整理", "内在生长", "秩序重建"],
        ["focus", "health", "calm"],
        "white",
        ["clarity", "calming"],
        ["phantom", "milky"],
        "白幽灵适合表达整理、重启和把混乱慢慢归位，千层或半盆形态能让方案更有自然层次。",
        ["phantom", "cloud"],
        batch_variation="high",
    ),
    "green_phantom": knowledge(
        "绿幽灵",
        "wood",
        ["earth"],
        ["heart", "root"],
        ["事业生长", "财富积累", "稳步推进"],
        ["career", "wealth", "focus"],
        "green",
        ["focus", "confidence"],
        ["phantom", "texture"],
        "绿幽灵适合做成长和事业主题的主石，聚宝盆形态可强调积累感，整串搭配宜保留自然留白。",
        ["phantom", "mineral_inclusion"],
        batch_variation="high",
    ),
    "red_phantom": knowledge(
        "红幽灵",
        "wood",
        ["fire"],
        ["root", "heart"],
        ["行动复原", "资源积累", "热度回升"],
        ["career", "wealth", "health"],
        "red",
        ["vitality", "confidence"],
        ["phantom", "warm"],
        "红幽灵比绿幽灵更有行动热度，适合需要从低状态里重新启动、积累资源和稳住执行力的方案。",
        ["phantom", "mineral_inclusion"],
        batch_variation="high",
    ),
    "yellow_phantom": knowledge(
        "黄幽灵",
        "wood",
        ["earth"],
        ["solar_plexus", "root"],
        ["财富积累", "事业机会", "落地执行"],
        ["wealth", "career", "focus"],
        "gold",
        ["confidence", "focus"],
        ["phantom", "warm"],
        "黄幽灵适合把幽灵的生长感转向财富和目标落地，视觉温暖，适合与白晶、茶晶做平衡。",
        ["phantom", "mineral_inclusion"],
        batch_variation="high",
    ),
    "pink_phantom": knowledge(
        "粉幽灵",
        "wood",
        ["fire"],
        ["heart", "root"],
        ["关系生长", "柔和修复", "温暖陪伴"],
        ["love", "relationship", "emotion"],
        "pink",
        ["softness", "companionship"],
        ["phantom", "soft_color"],
        "粉幽灵适合把关系和自我接纳放进更有层次的自然纹理里，比普通粉晶更有成长感。",
        ["phantom", "cloud"],
        batch_variation="high",
    ),
    "purple_phantom": knowledge(
        "紫幽灵",
        "wood",
        ["fire"],
        ["third_eye", "heart"],
        ["内在觉察", "灵感生长", "专注沉淀"],
        ["focus", "inspiration", "calm"],
        "purple",
        ["clarity", "calming"],
        ["phantom", "texture"],
        "紫幽灵适合把灵感、复盘和内在成长放在一起，视觉上比紫水晶更有矿物故事感。",
        ["phantom", "mineral_inclusion"],
        batch_variation="high",
    ),
    "colorful_phantom": knowledge(
        "彩幽灵",
        "wood",
        ["fire", "earth"],
        ["heart", "root", "solar_plexus"],
        ["综合成长", "状态整合", "灵感复原"],
        ["career", "emotion", "inspiration"],
        "green",
        ["vitality", "clarity"],
        ["phantom", "texture"],
        "彩幽灵适合表达多阶段成长和复合状态，适合作为自然感强的主石，也能让方案更有收藏感。",
        ["phantom", "mineral_inclusion"],
        batch_variation="high",
    ),
    "four_seasons_phantom": knowledge(
        "四季幽灵",
        "wood",
        ["earth", "fire"],
        ["heart", "root", "solar_plexus"],
        ["四季流转", "稳定生长", "状态整合"],
        ["career", "health", "emotion", "inspiration"],
        "green",
        ["vitality", "calming"],
        ["phantom", "texture"],
        "四季幽灵适合表达周期、变化和长期生长，适合给方案加入自然层次与时间感。",
        ["phantom", "mineral_inclusion"],
        batch_variation="high",
    ),
    "citrine": knowledge(
        "黄水晶",
        "earth",
        ["fire"],
        ["solar_plexus"],
        ["财富行动", "自信表达", "目标推进"],
        ["wealth", "career", "focus"],
        "gold",
        ["confidence", "vitality"],
        ["transparent", "warm"],
        "黄水晶适合财富、目标和行动主题，颜色越明亮越适合做轻快的推进感，避免整串过满可更显高级。",
        ["clean", "warm"],
    ),
    "arusha_sunstone": knowledge(
        "金太阳阿鲁沙",
        "fire",
        ["earth"],
        ["solar_plexus", "sacral"],
        ["阳光活力", "自信显化", "行动热度"],
        ["career", "wealth", "inspiration"],
        "gold",
        ["vitality", "confidence"],
        ["sparkling", "warm"],
        "金太阳阿鲁沙适合做明亮、外放和显化主题的主石，能把方案的气质从温柔推向更有存在感。",
        ["sparkling", "mineral_inclusion"],
        batch_variation="high",
    ),
    "moonstone": knowledge(
        "月光石",
        "water",
        ["metal"],
        ["sacral", "crown"],
        ["情绪柔和", "女性能量", "睡眠修复"],
        ["emotion", "sleep", "love"],
        "white",
        ["softness", "calming"],
        ["milky", "icy"],
        "月光石适合柔和、陪伴和情绪照顾主题，白月光偏清透，灰月光更沉静，适合在冷暖之间做过渡。",
        ["cloud", "sparkling"],
        batch_variation="high",
    ),
    "labradorite": knowledge(
        "拉长石",
        "earth",
        ["water"],
        ["third_eye", "crown"],
        ["灵感守护", "直觉觉察", "状态转换"],
        ["protection", "inspiration", "focus"],
        "blue",
        ["clarity", "boundary"],
        ["sparkling", "dark"],
        "拉长石的蓝绿色晕彩适合做灵感和保护主题，低调但有变化，适合高级冷感搭配。",
        ["mineral_inclusion", "sparkling"],
        batch_variation="high",
    ),
    "fluorite": knowledge(
        "萤石",
        "water",
        ["wood"],
        ["third_eye", "heart"],
        ["专注秩序", "学习整理", "灵感分类"],
        ["focus", "study", "inspiration"],
        "green",
        ["clarity", "focus"],
        ["transparent", "color_band"],
        "萤石适合学习、整理和把想法分层，彩萤石可增加变化感，拉丝萤石更适合清爽秩序感。",
        ["color_band", "clean"],
        care_tags=["avoid_sun", "fragile", "clean_regularly", "storage_separate"],
        batch_variation="high",
    ),
    "purple_fluorite": knowledge(
        "紫萤石",
        "fire",
        ["water"],
        ["third_eye", "heart"],
        ["灵感整理", "专注复盘", "安静觉察"],
        ["focus", "study", "inspiration"],
        "purple",
        ["clarity", "calming"],
        ["transparent", "color_band"],
        "紫萤石适合在学习和灵感之间做桥梁，视觉轻盈，适合搭配白水晶或月光石。",
        ["color_band", "clean"],
        care_tags=["avoid_sun", "fragile", "clean_regularly", "storage_separate"],
    ),
    "yellow_fluorite": knowledge(
        "黄萤石",
        "earth",
        ["water"],
        ["solar_plexus", "third_eye"],
        ["思路落地", "学习效率", "目标拆解"],
        ["study", "focus", "career"],
        "gold",
        ["clarity", "confidence"],
        ["transparent", "warm"],
        "黄萤石适合把复杂任务拆开处理，颜色明亮但不强势，适合作为学习和工作主题的辅助石。",
        ["color_band", "clean"],
        care_tags=["avoid_sun", "fragile", "clean_regularly", "storage_separate"],
    ),
    "blue_fluorite": knowledge(
        "蓝萤石",
        "water",
        ["metal"],
        ["throat", "third_eye"],
        ["冷静沟通", "思维清理", "表达秩序"],
        ["communication", "focus", "study"],
        "blue",
        ["clarity", "calming"],
        ["transparent", "icy"],
        "蓝萤石适合表达、学习和冷静判断主题，适合把方案做得更清爽、更有空气感。",
        ["color_band", "clean"],
        care_tags=["avoid_sun", "fragile", "clean_regularly", "storage_separate"],
    ),
    "amazonite": knowledge(
        "天河石",
        "water",
        ["wood"],
        ["throat", "heart"],
        ["舒缓表达", "关系沟通", "情绪放松"],
        ["communication", "emotion", "relationship"],
        "blue",
        ["calming", "softness"],
        ["soft_color", "texture"],
        "天河石适合让表达更松弛，不是强势说服，而是把真实想法温和地说出来。",
        ["color_band", "cloud"],
        transparency_level="opaque",
    ),
    "aquamarine": knowledge(
        "海蓝宝",
        "water",
        ["metal"],
        ["throat", "heart"],
        ["清透沟通", "平静表达", "情绪降噪"],
        ["communication", "emotion", "calm"],
        "blue",
        ["calming", "clarity"],
        ["transparent", "icy"],
        "海蓝宝适合沟通和平静主题，视觉清透，能把整串气质拉向干净、清凉和理性。",
        ["clean", "cloud"],
    ),
    "larimar": knowledge(
        "海纹石",
        "water",
        ["wood"],
        ["throat", "heart"],
        ["放松疗愈", "柔和表达", "情绪舒展"],
        ["communication", "emotion", "sleep"],
        "blue",
        ["calming", "softness"],
        ["texture", "soft_color"],
        "海纹石适合海风感、松弛感和温柔沟通主题，纹理本身就是视觉重点，搭配宜简单。",
        ["color_band", "texture"],
        care_tags=["avoid_sun", "avoid_sweat", "clean_regularly", "storage_separate"],
        transparency_level="opaque",
        batch_variation="high",
    ),
    "kyanite": knowledge(
        "蓝晶石",
        "water",
        ["metal"],
        ["throat", "third_eye"],
        ["高频表达", "冷静判断", "直觉校准"],
        ["communication", "focus", "inspiration"],
        "blue",
        ["clarity", "focus"],
        ["texture", "icy"],
        "蓝晶石适合做清醒、锋利但不喧闹的蓝色主石，玉化质感会让整体更温润。",
        ["color_band", "texture"],
        care_tags=["fragile", "clean_regularly", "storage_separate"],
        batch_variation="high",
    ),
    "blue_topaz": knowledge(
        "蓝托帕石",
        "water",
        ["metal"],
        ["throat", "third_eye"],
        ["清晰表达", "轻盈思考", "自信沟通"],
        ["communication", "focus", "career"],
        "blue",
        ["clarity", "confidence"],
        ["transparent", "sparkling"],
        "蓝托帕石适合干净明亮的表达主题，视觉上比海蓝宝更闪，适合少量提亮。",
        ["clean", "sparkling"],
    ),
    "iolite": knowledge(
        "堇青石",
        "water",
        ["fire"],
        ["third_eye", "throat"],
        ["方向感", "判断力", "灵感导航"],
        ["focus", "study", "inspiration"],
        "blue",
        ["clarity", "focus"],
        ["dark", "transparent"],
        "堇青石适合需要方向感和自我校准的方案，色调克制，适合和银色、白色晶石搭配。",
        ["clean", "dark"],
    ),
    "lapis_lazuli": knowledge(
        "青金石",
        "water",
        ["metal"],
        ["throat", "third_eye"],
        ["表达权威", "洞察学习", "内在秩序"],
        ["communication", "study", "focus"],
        "blue",
        ["confidence", "clarity"],
        ["dark", "texture"],
        "青金石适合表达、学习和内在秩序主题，金色矿点会让蓝色方案更有仪式感。",
        ["mineral_inclusion", "dark"],
        care_tags=["avoid_water", "avoid_sweat", "clean_regularly", "storage_separate"],
        transparency_level="opaque",
        batch_variation="high",
    ),
    "tourmaline": knowledge(
        "碧玺",
        "earth",
        ["water", "fire"],
        ["heart", "root"],
        ["综合平衡", "守护调和", "多彩人缘"],
        ["love", "protection", "emotion"],
        "green",
        ["vitality", "softness"],
        ["sparkling", "color_band"],
        "碧玺颜色丰富，适合做综合调和型珠材；多色搭配时可作为连接不同能量主题的桥梁。",
        ["color_band", "clean"],
        batch_variation="high",
    ),
    "prehnite": knowledge(
        "葡萄石",
        "wood",
        ["water"],
        ["heart"],
        ["温柔成长", "情绪舒展", "关系缓和"],
        ["emotion", "health", "relationship"],
        "green",
        ["softness", "calming"],
        ["milky", "soft_color"],
        "葡萄石适合做温柔的绿色过渡，能把事业型绿色晶石变得更亲近，也适合情绪修复主题。",
        ["cloud", "clean"],
        transparency_level="translucent",
    ),
    "tiger_eye": knowledge(
        "虎眼石",
        "earth",
        ["fire"],
        ["solar_plexus", "root"],
        ["行动判断", "财富稳定", "自信边界"],
        ["wealth", "career", "protection"],
        "brown",
        ["confidence", "boundary"],
        ["cat_eye", "warm"],
        "虎眼石适合行动、财富和自我边界主题，猫眼光带让它很适合作为有方向感的主石。",
        ["cat_eye", "color_band"],
        transparency_level="opaque",
        batch_variation="high",
    ),
    "blue_tiger_eye": knowledge(
        "蓝虎眼石",
        "earth",
        ["water"],
        ["solar_plexus", "root", "third_eye"],
        ["冷静行动", "守护判断", "压力稳定"],
        ["protection", "focus", "career"],
        "blue",
        ["boundary", "focus"],
        ["cat_eye", "dark"],
        "蓝虎眼石比金虎眼更冷静，适合在保护和行动之间做平衡，也适合男款或低饱和搭配。",
        ["cat_eye", "dark"],
        transparency_level="opaque",
        batch_variation="high",
    ),
    "obsidian": knowledge(
        "黑曜石",
        "water",
        ["metal"],
        ["root"],
        ["边界守护", "稳定安全感", "断舍离"],
        ["protection", "calm", "focus"],
        "black",
        ["boundary", "calming"],
        ["dark"],
        "黑曜石适合做守护和边界主题，视觉上能压住过甜或过亮的配色，让整串更稳。",
        ["dark", "clean"],
        transparency_level="opaque",
    ),
    "golden_obsidian": knowledge(
        "金曜石",
        "earth",
        ["water"],
        ["root", "solar_plexus"],
        ["守护财富", "稳定气场", "内在底气"],
        ["protection", "wealth", "career"],
        "black",
        ["boundary", "confidence"],
        ["dark", "sparkling"],
        "金曜石在黑色守护感里带一点金色显化，适合稳住边界的同时保留事业和财富主题。",
        ["dark", "sparkling"],
        transparency_level="opaque",
    ),
    "silver_obsidian": knowledge(
        "银曜石",
        "metal",
        ["water"],
        ["root", "third_eye"],
        ["冷静守护", "清理杂念", "边界感"],
        ["protection", "focus", "calm"],
        "black",
        ["boundary", "clarity"],
        ["dark", "sparkling"],
        "银曜石比金曜石更冷静，适合需要清理杂念、保持距离感和稳定判断的方案。",
        ["dark", "sparkling"],
        transparency_level="opaque",
    ),
    "black_agate": knowledge(
        "黑玛瑙",
        "water",
        ["earth"],
        ["root"],
        ["稳定守护", "情绪沉淀", "安全边界"],
        ["protection", "calm", "health"],
        "black",
        ["boundary", "calming"],
        ["dark"],
        "黑玛瑙适合做低调守护型珠材，比黑曜石更温和，适合日常佩戴里的稳定底色。",
        ["color_band", "dark"],
        transparency_level="opaque",
    ),
    "smoky_quartz": knowledge(
        "茶晶",
        "earth",
        ["water"],
        ["root"],
        ["落地稳定", "压力释放", "安全感"],
        ["protection", "emotion", "health"],
        "brown",
        ["calming", "boundary"],
        ["transparent", "warm"],
        "茶晶适合把过强的能量往下沉，帮助整串更稳、更耐看，也适合做守护和减压主题。",
        ["clean", "cloud"],
    ),
    "black_super_seven": knowledge(
        "黑超七",
        "water",
        ["fire", "metal"],
        ["root", "third_eye", "crown"],
        ["深层守护", "状态整合", "直觉觉察"],
        ["protection", "inspiration", "focus"],
        "black",
        ["boundary", "clarity"],
        ["dark", "texture"],
        "黑超七适合做强层次的守护型主石，能量表达更复合，搭配时建议用少量浅色珠子调亮。",
        ["mineral_inclusion", "dark"],
        batch_variation="high",
    ),
    "red_agate": knowledge(
        "红玛瑙",
        "fire",
        ["earth"],
        ["root", "sacral"],
        ["稳定活力", "行动热度", "日常守护"],
        ["health", "career", "protection"],
        "red",
        ["vitality", "confidence"],
        ["warm", "texture"],
        "红玛瑙适合补充日常热度和稳定感，颜色温暖，适合做不夸张但有气血感的红色搭配。",
        ["color_band", "warm"],
        transparency_level="opaque",
    ),
    "south_red_agate": knowledge(
        "南红玛瑙",
        "fire",
        ["earth"],
        ["root", "heart"],
        ["温润守护", "气血感", "稳定热度"],
        ["health", "protection", "love"],
        "red",
        ["vitality", "softness"],
        ["warm", "milky"],
        "南红玛瑙的红更温润厚实，适合中式、守护和稳定热度主题，做主石会比普通红玛瑙更有质感。",
        ["color_band", "warm"],
        transparency_level="opaque",
        batch_variation="high",
    ),
    "salt_source_agate": knowledge(
        "盐源玛瑙",
        "fire",
        ["earth"],
        ["heart", "root"],
        ["柔和活力", "情绪平衡", "温暖陪伴"],
        ["emotion", "love", "health"],
        "pink",
        ["softness", "vitality"],
        ["soft_color", "texture"],
        "盐源玛瑙颜色跨度丰富，适合做温柔但不单薄的综合色系，常用于柔和人缘与情绪平衡主题。",
        ["color_band", "texture"],
        transparency_level="opaque",
        batch_variation="high",
    ),
    "alashan_agate": knowledge(
        "阿拉善玛瑙",
        "earth",
        ["fire"],
        ["root", "solar_plexus"],
        ["大地稳定", "色彩趣味", "长期陪伴"],
        ["health", "emotion", "career"],
        "brown",
        ["calming", "vitality"],
        ["texture", "warm"],
        "阿拉善玛瑙适合做自然、旷野和耐看型搭配，颜色变化大，适合把方案做得更有个性。",
        ["color_band", "texture"],
        transparency_level="opaque",
        batch_variation="high",
    ),
    "banded_agate": knowledge(
        "条纹玛瑙",
        "earth",
        ["fire"],
        ["root", "solar_plexus"],
        ["层次稳定", "节奏整理", "耐心推进"],
        ["focus", "career", "health"],
        "red",
        ["focus", "calming"],
        ["color_band", "texture"],
        "条纹玛瑙的纹理很适合表达节奏和层次，用在方案里能增加秩序感，也适合做过渡珠。",
        ["color_band", "texture"],
        transparency_level="opaque",
        batch_variation="high",
    ),
    "quartz_inclusion": knowledge(
        "胶花水晶",
        "fire",
        ["earth"],
        ["solar_plexus", "root"],
        ["创造热情", "好运意象", "行动启动"],
        ["career", "wealth", "inspiration"],
        "gold",
        ["vitality", "confidence"],
        ["mineral_inclusion", "warm"],
        "胶花水晶适合做有画面感和好运意象的主石，内含物越丰富越有故事，搭配时建议减少其他复杂纹理。",
        ["mineral_inclusion", "cloud"],
        batch_variation="high",
    ),
}


KNOWLEDGE_COLUMNS = [
    "code",
    "name",
    "primary_element",
    "secondary_elements_json",
    "chakras_json",
    "chakra_weights_json",
    "effects_json",
    "wish_pools_json",
    "color_family",
    "mood_tags_json",
    "visual_tags_json",
    "story",
    "allowed_roles_json",
    "match_rules_json",
    "care_tags_json",
    "material_params_json",
    "asset_json",
    "enabled",
    "created_at",
    "updated_at",
]


def db_item(code: str, item: dict[str, Any], timestamp: str) -> dict[str, Any]:
    return {
        "code": code,
        "name": item["name"],
        "primary_element": item["primary_element"],
        "secondary_elements_json": j(item["secondary_elements"]),
        "chakras_json": j(item["chakras"]),
        "chakra_weights_json": j(item["chakra_weights"]),
        "effects_json": j(item["effects"]),
        "wish_pools_json": j(item["wish_pools"]),
        "color_family": item["color_family"],
        "mood_tags_json": j(item["mood_tags"]),
        "visual_tags_json": j(item["visual_tags"]),
        "story": item["story"],
        "allowed_roles_json": j(item["allowed_roles"]),
        "match_rules_json": j(item["match_rules"]),
        "care_tags_json": j(item["care_tags"]),
        "material_params_json": j(item["material_params"]),
        "asset_json": j(item["asset"]),
        "enabled": int(item["enabled"]),
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def image_filter_sql() -> str:
    return "(COALESCE(image_url,'')<>'' OR COALESCE(image_path,'')<>'' OR COALESCE(image_urls_json,'')<>'')"


def list_target_groups(connection: Any) -> list[dict[str, Any]]:
    rows = connection.execute(
        f"""
        SELECT material_code, category, series, COUNT(*) AS row_count
        FROM managed_materials
        WHERE top = 'bead' AND enabled = 1 AND {image_filter_sql()}
        GROUP BY material_code, category, series
        ORDER BY category, series
        """
    ).fetchall()
    return [dict(row) for row in rows]


def target_code_for(group: dict[str, Any]) -> str:
    return SERIES_CODE_OVERRIDES.get(str(group.get("series") or "").strip()) or str(group.get("material_code") or "").strip()


def update_material_code(connection: Any, series: str, code: str, timestamp: str) -> int:
    cursor = connection.execute(
        f"""
        UPDATE managed_materials
        SET material_code = ?, updated_at = ?
        WHERE top = 'bead' AND series = ? AND {image_filter_sql()}
        """,
        (code, timestamp, series),
    )
    return int(getattr(cursor, "rowcount", 0) or 0)


def upsert_knowledge(connection: Any, code: str, item: dict[str, Any], timestamp: str, mysql: bool) -> None:
    payload = db_item(code, item, timestamp)
    values = [payload[column] for column in KNOWLEDGE_COLUMNS]
    placeholders = ", ".join(["?"] * len(KNOWLEDGE_COLUMNS))
    column_sql = ", ".join(KNOWLEDGE_COLUMNS)
    update_columns = [column for column in KNOWLEDGE_COLUMNS if column not in {"code", "created_at"}]
    if mysql:
        update_sql = ", ".join(f"{column}=VALUES({column})" for column in update_columns)
        connection.execute(
            f"""
            INSERT INTO material_knowledge ({column_sql})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {update_sql}
            """,
            values,
        )
        return
    update_sql = ", ".join(f"{column}=excluded.{column}" for column in update_columns)
    connection.execute(
        f"""
        INSERT INTO material_knowledge ({column_sql})
        VALUES ({placeholders})
        ON CONFLICT(code) DO UPDATE SET {update_sql}
        """,
        values,
    )


def backup_sqlite_database(db_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = db_path.with_name(f"{db_path.stem}.before_bead_knowledge_{timestamp}{db_path.suffix}")
    shutil.copy2(db_path, backup)
    return backup


def run(apply: bool, db_path: Path | None = None, backup: bool = True) -> dict[str, Any]:
    timestamp = now_iso()
    mysql = db_path is None and use_mysql()
    connection_factory = (lambda: connect_database(db_path)) if db_path else connect_database
    backup_path = None
    if apply and backup and db_path and db_path.exists():
        backup_path = backup_sqlite_database(db_path)

    with connection_factory() as connection:
        groups = list_target_groups(connection)
        target_codes = sorted({target_code_for(group) for group in groups})
        missing_definitions = [code for code in target_codes if code not in KNOWLEDGE_BY_CODE]
        code_changes = [
            {
                "series": group["series"],
                "from": group["material_code"],
                "to": target_code_for(group),
                "rows": group["row_count"],
            }
            for group in groups
            if target_code_for(group) != group["material_code"]
        ]
        if missing_definitions:
            return {
                "apply": apply,
                "groups": len(groups),
                "target_codes": len(target_codes),
                "missing_definitions": missing_definitions,
                "code_changes": code_changes,
                "updated_material_rows": 0,
                "upserted_knowledge": 0,
                "backup": str(backup_path) if backup_path else "",
            }
        updated_material_rows = 0
        upserted_knowledge = 0
        if apply:
            for change in code_changes:
                updated_material_rows += update_material_code(connection, change["series"], change["to"], timestamp)
            for code in target_codes:
                upsert_knowledge(connection, code, KNOWLEDGE_BY_CODE[code], timestamp, mysql=mysql)
                upserted_knowledge += 1
    return {
        "apply": apply,
        "groups": len(groups),
        "target_codes": len(target_codes),
        "missing_definitions": [],
        "code_changes": code_changes,
        "updated_material_rows": updated_material_rows,
        "upserted_knowledge": upserted_knowledge,
        "backup": str(backup_path) if backup_path else "",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Complete energy knowledge for bead materials that already have images.")
    parser.add_argument("--apply", action="store_true", help="Write updates to the database.")
    parser.add_argument("--db", type=Path, default=DEFAULT_SQLITE_PATH, help="SQLite database path.")
    parser.add_argument("--no-backup", action="store_true", help="Skip SQLite backup before applying.")
    args = parser.parse_args()

    result = run(apply=args.apply, db_path=args.db, backup=not args.no_backup)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["missing_definitions"]:
        raise SystemExit(2)
    if not args.apply:
        print("dry_run=true; add --apply to write changes")


if __name__ == "__main__":
    main()
