from __future__ import annotations

import hashlib
import re
from datetime import datetime


OFFICIAL_BEAD_TSV = """
黑晶石	黑晶石
蓝晶石	油画蓝晶
蓝晶石	蓝晶石
蓝晶石	玉化蓝晶
蓝晶石	透体蓝晶
白水晶	喜马拉雅白水晶
白水晶	奶白水晶
白水晶	白阿塞水晶
白水晶	白水晶
白水晶	双A白水
紫水晶	乌拉圭紫晶
紫水晶	巴西紫晶
紫水晶	薰衣草紫晶
紫水晶	紫黄晶
紫水晶	玻利维亚紫水晶
黄水晶	巴西黄水晶
黄水晶	柠檬黄水晶
黄水晶	黄塔晶
粉水晶	莫桑比克粉晶
粉水晶	马达加斯加粉晶
粉水晶	老矿粉晶
粉水晶	果冻粉
粉水晶	冰种粉晶
粉水晶	六芒星光粉晶
茶晶/烟晶	浅茶
茶晶/烟晶	深茶
茶晶/烟晶	墨晶
茶晶/烟晶	黑茶晶
茶晶/烟晶	烟墨晶
绿水晶	绿水晶
绿水晶	绿阿塞
发晶	金发晶
发晶	钛晶
发晶	红铜发
发晶	黑发晶
发晶	绿发晶
发晶	银发晶
发晶	彩发晶
幽灵水晶	绿幽灵
幽灵水晶	满天星
幽灵水晶	抹茶幽灵
幽灵水晶	墨绿幽灵
幽灵水晶	翠绿幽灵
幽灵水晶	红幽灵
幽灵水晶	白幽灵
幽灵水晶	四季幽灵
幽灵水晶	黄幽灵
幽灵水晶	紫幽灵
幽灵水晶	意境幽灵
幽灵水晶	千层幽灵
幽灵水晶	雪花幽灵
幽灵水晶	红泥骸骨幽灵
兔毛水晶	红兔毛
兔毛水晶	黄兔毛
兔毛水晶	白兔毛
兔毛水晶	彩兔毛
兔毛水晶	紫兔毛
兔毛水晶	蓝兔毛
兔毛水晶	灰兔毛
兔毛水晶	绿兔毛
草莓晶系	草莓晶
草莓晶系	黑加仑草莓晶
草莓晶系	金草莓晶
草莓晶系	绿草莓晶
草莓晶系	黑草莓晶
超七	紫超七
超七	黑金超七
超七	烟花超七
极光 23	紫极光 23
堇青石	蓝堇青石
拉长石	拉长石
月光石系	白月光石
月光石系	蓝月光石
月光石系	橙月光石
月光石系	灰月光石
月光石系	黑月光石
萤石	彩虹萤石
萤石	蓝萤石
萤石	绿萤石
萤石	紫萤石
萤石	粉萤石
萤石	羽毛萤石
萤石	拉丝萤石
葡萄石	冰种葡萄石
葡萄石	绿葡萄石
红纹石	老矿红纹
红纹石	樱花红纹
紫锂辉石	猫眼紫锂辉
紫锂辉石	冰种紫锂辉
紫锂辉石	薰衣草紫锂辉
天河石	高蓝天河石
天河石	莫桑天河石
海蓝宝	冰川蓝
海蓝宝	蓝天白云
海蓝宝	岛屿
海蓝宝	圣蓝
海蓝宝	魔鬼蓝
海蓝宝	黑芝麻
骨干水晶	黑金骨干
骨干水晶	白骨干
贝母	白贝母
珊瑚石	珊瑚石
闪灵	黑闪灵
闪灵	彩闪灵
水胆水晶	水胆紫晶
水胆水晶	白水胆
水胆水晶	水胆幽灵
水胆水晶	水胆发晶
虎眼石	金虎眼
虎眼石	蓝虎眼
虎眼石	黄虎眼
虎眼石	红虎眼
虎眼石	彩虎眼
黑耀石	银耀石
黑耀石	金耀石
黑耀石	陨石耀
玛瑙	南虹玛瑙
玛瑙	红玛瑙
玛瑙	黑玛瑙
玛瑙	阿拉善
玛瑙	盐源玛瑙
玛瑙	樱花玛瑙
胶花水晶	红胶花
胶花水晶	黄胶花
胶花水晶	牛血红胶花
胶花水晶	冰糖雪梨胶花
胶花水晶	小树胶花
胶花水晶	枯树胶花
胶花水晶	锦鲤胶花
胶花水晶	闪灵胶花
特殊水晶	特殊水晶
玉石	岫玉
玉石	和田玉
托帕	蓝托帕
托帕	桂花托帕
托帕	彩托帕
托帕	黄托帕
托帕	粉托帕
孔雀石	孔雀石
天河石	天河石
海纹石	海纹石
祖母晶	紫祖母
祖母晶	绿祖母
祖母晶	粉祖母
龙麟石	龙麟石
云母	紫锂云母
云母	绿锂云母
云母	粉锂云母
云母	黑金云母
云母	金锂云母
阿鲁沙金太阳	阿鲁沙金太阳
金运石	金运石
摩根石	摩根石
碧玺	碧玺
石榴石	橙石榴
石榴石	红石榴
青金石	青金石
紫玉晶	紫玉晶
磷灰石	蓝磷灰
磷灰石	绿磷灰
磷灰石	粉磷灰
磷灰石	紫磷灰
东陵玉	绿东陵
东陵玉	蓝东陵
东陵玉	红东陵
蓝玉髓	蓝玉髓
方解石	方解石
蓝纹石	蓝纹石
蔷薇辉石	蔷薇辉
蓝铜矿	蓝铜矿
捷克陨石	捷克陨石
水胆水晶	水胆水晶
舒俱来	舒俱来
鹰眼石	鹰眼石
""".strip()


SIZE_OPTIONS = (8, 10, 12)


def parse_official_bead_pairs() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for line in OFFICIAL_BEAD_TSV.splitlines():
        category, series = [part.strip() for part in line.split("\t", 1)]
        key = (category, series)
        if key not in seen:
            seen.add(key)
            pairs.append(key)
    return pairs


def build_official_bead_materials() -> list[dict]:
    materials: list[dict] = []
    sort_order = 1000
    for category, series in parse_official_bead_pairs():
        profile = infer_bead_profile(category, series)
        sku_id = f"bead_{stable_token(category, series, length=10)}"
        for size in SIZE_OPTIONS:
            item_id = f"{sku_id}_{size}mm"
            materials.append(
                {
                    "id": item_id,
                    "skuId": sku_id,
                    "top": "bead",
                    "category": category,
                    "series": series,
                    "grade": "",
                    "name": series,
                    "effect": profile["effect"],
                    "element": profile["element"],
                    "price": estimate_price(category, series, size),
                    "size": size,
                    "weight": round((size / 8) ** 3 * 1.2, 2),
                    "color": profile["color"],
                    "shine": profile["shine"],
                    "image_path": f"beads/{sku_id}-{size}.png",
                    "image_url": "",
                    "enabled": 1,
                    "sort_order": sort_order,
                }
            )
            sort_order += 1
    return materials


def ensure_official_bead_catalog(connection) -> int:
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    inserted = 0
    for item in build_official_bead_materials():
        existing = connection.execute(
            """
            SELECT id FROM managed_materials
            WHERE top = 'bead' AND category = ? AND series = ? AND size = ?
            """,
            (item["category"], item["series"], item["size"]),
        ).fetchone()
        if existing:
            continue
        connection.execute(
            """
            INSERT INTO managed_materials
            (id, skuId, top, category, series, grade, name, effect, element, price, size, weight, color, shine,
             image_path, image_url, enabled, sort_order, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["id"],
                item["skuId"],
                item["top"],
                item["category"],
                item["series"],
                item["grade"],
                item["name"],
                item["effect"],
                item["element"],
                item["price"],
                item["size"],
                item["weight"],
                item["color"],
                item["shine"],
                item["image_path"],
                item["image_url"],
                item["enabled"],
                item["sort_order"],
                timestamp,
                timestamp,
            ),
        )
        inserted += 1
    return inserted


def stable_token(*parts: str, length: int = 12) -> str:
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:length]


def infer_bead_profile(category: str, series: str) -> dict[str, str]:
    text = f"{category}{series}"
    if any(key in text for key in ["粉", "红", "草莓", "红纹", "珊瑚", "蔷薇", "摩根"]):
        return {"element": "火", "effect": "亲密与吸引", "color": "#d98d96", "shine": "#fff0f2"}
    if any(key in text for key in ["黄", "金", "钛", "虎眼", "太阳", "橙", "桂花"]):
        return {"element": "土", "effect": "财富与行动", "color": "#d4a548", "shine": "#fff0b8"}
    if any(key in text for key in ["绿", "孔雀", "葡萄", "东陵", "幽灵"]):
        return {"element": "木", "effect": "生长与复原", "color": "#5f9a72", "shine": "#e1f2e7"}
    if any(key in text for key in ["蓝", "海", "青金", "堇青", "托帕", "磷灰"]):
        return {"element": "水", "effect": "沟通与平静", "color": "#6faec5", "shine": "#e9f8ff"}
    if any(key in text for key in ["黑", "墨", "茶", "烟", "耀", "骨干"]):
        return {"element": "水", "effect": "守护与稳定", "color": "#333238", "shine": "#bfc3c7"}
    if any(key in text for key in ["紫", "舒俱来", "云母", "超七", "极光"]):
        return {"element": "火", "effect": "灵感与睡眠", "color": "#8a69a8", "shine": "#f1e8ff"}
    if any(key in text for key in ["白", "贝母", "月光", "水胆", "方解石"]):
        return {"element": "金", "effect": "净化与放大", "color": "#dfe3e5", "shine": "#ffffff"}
    return {"element": "土", "effect": "平衡与守护", "color": "#9f8d7a", "shine": "#fff5e8"}


def estimate_price(category: str, series: str, size: int) -> int:
    text = f"{category}{series}"
    base = 8
    if any(key in text for key in ["钛晶", "金发晶", "捷克陨石", "舒俱来", "托帕", "碧玺", "海蓝宝"]):
        base = 38
    elif any(key in text for key in ["超七", "极光", "祖母", "紫锂辉", "红纹", "蓝晶", "发晶"]):
        base = 26
    elif any(key in text for key in ["幽灵", "月光", "天河", "萤石", "虎眼", "玛瑙", "石榴"]):
        base = 16
    elif any(key in text for key in ["白水晶", "茶", "烟", "黑晶", "黑耀"]):
        base = 8
    return int(round(base * (size / 8) ** 1.35))


def safe_slug(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return value or stable_token(text, length=8)
