from __future__ import annotations

import csv
import json
from pathlib import Path

from PIL import Image


GENERATED_DIR = Path(r"C:\Users\10156\.codex\generated_images\019eda29-54de-7b32-acd6-883145383647")
OUTPUT_DIR = Path("outputs/宇涧水晶单珠白底图_100款")

GROUPS = [
    ["南红玛瑙", "四季幽灵", "堇青石", "天河石"],
    ["奶白晶", "巴西白幽灵千层水晶", "巴西白幽灵水晶半盆", "巴西黄水晶"],
    ["幽灵水晶", "幽灵水晶各种形态", "彩兔毛水晶", "彩幽灵蛋面"],
    ["彩幽灵魔盒", "彩耀石", "彩萤石", "拉丝萤石"],
    ["拉丝蓝萤石", "拉丝黄萤石", "拉长石", "月光石"],
    ["月光石各类", "条纹玛瑙", "极光 23", "柠檬黄水晶"],
    ["樱花玛瑙", "毒液黑超七", "海纹石", "灰月光"],
    ["牛血红胶花水晶", "玉化蓝晶石", "玻利维亚紫水晶", "白兔毛水晶"],
    ["白幽灵水晶高品", "白月光石", "白水晶", "白水草莓晶"],
    ["白阿塞水晶", "盐源玛瑙", "碧玺", "粉幽灵"],
    ["粉水品种", "粉水晶", "粉水晶马粉", "紫兔毛水晶"],
    ["紫兔毛水晶钢丝", "紫幽灵", "紫拉丝萤石", "紫水晶"],
    ["紫牙乌石榴石", "紫锂辉", "紫黄晶", "红兔毛水晶"],
    ["红幽灵", "红幽灵聚宝盆", "红玛瑙", "红石榴石"],
    ["红纹石", "红胶花水晶", "红草莓晶", "红铜发晶"],
    ["维纳斯金发晶", "绿兔毛水晶", "绿发晶", "绿发猫眼顺发"],
    ["绿幽灵", "绿钢丝发", "茶晶", "莫桑比亚粉水晶"],
    ["葡萄石", "蓝兔毛水晶", "蓝兔毛钢丝", "蓝托帕石"],
    ["蓝晶石", "蓝虎眼石", "薰衣草紫水晶", "车厘子草莓晶"],
    ["金发晶", "金太阳阿鲁沙", "金耀石", "金草莓晶"],
    ["金虎眼石", "钛晶", "钛晶发", "银发晶"],
    ["银耀石", "锦鲤胶花", "阿拉善玛瑙", "陨石曜"],
    ["雪花白幽灵水晶", "青金石", "马达加斯加粉晶果冻体", "鹰眼石"],
    ["黄兔毛水晶", "黄幽灵", "黄胶花水晶", "黄虎眼石"],
    ["黄阿塞水晶", "黑发晶", "黑发晶维纳斯细发", "黑玛瑙"],
]


def main() -> None:
    files = sorted(GENERATED_DIR.glob("*.png"), key=lambda path: path.stat().st_mtime)
    # 前 5 张是用户确认前生成的单图样例；之后正好是 25 张正式四宫格。
    sheets = files[5:30]
    if len(sheets) != len(GROUPS):
        raise SystemExit(f"期望 25 张正式四宫格，实际找到 {len(sheets)} 张")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    positions = [(0, 0), (1, 0), (0, 1), (1, 1)]

    index = 1
    for group_no, (sheet_path, names) in enumerate(zip(sheets, GROUPS, strict=True), start=1):
        sheet = Image.open(sheet_path).convert("RGB")
        half_w = sheet.width // 2
        half_h = sheet.height // 2
        for name, (column, row) in zip(names, positions, strict=True):
            left = column * half_w
            top = row * half_h
            tile = sheet.crop((left, top, left + half_w, top + half_h))
            tile = tile.resize((1024, 1024), Image.Resampling.LANCZOS)
            output = OUTPUT_DIR / f"{index:03d}_{name}.png"
            tile.save(output, quality=97)
            rows.append(
                {
                    "index": index,
                    "name": name,
                    "file": output.name,
                    "source_sheet": sheet_path.name,
                    "group": group_no,
                    "source": "image-generation",
                }
            )
            index += 1

    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (OUTPUT_DIR / "品类清单.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"split={len(rows)} output={OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
