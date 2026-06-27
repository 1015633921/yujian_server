from __future__ import annotations

import argparse
import html
import os
import re
import sys
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin

import httpx
from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.admin_service import AdminService  # noqa: E402
from app.avatar_storage import AvatarStorage  # noqa: E402


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


POSTS = [
    {
        "post_id": "test-inspo-clear-quartz-morning",
        "title": "晨光白水晶",
        "desc": "清透白水晶搭配细闪切面珠，适合想要干净、轻盈、日常耐看的手串。",
        "story": "这条灵感从晨光照进工作室的感觉出发，主石用白水晶保留通透感，辅以月光石和银色隔珠，让整体更像一圈柔和的光。",
        "scene": "通勤、白衬衫、轻商务、日常叠戴",
        "tone": "clear",
        "recipe": ["clearQuartz", "moonstone", "clearQuartz", "silverSpacer"],
        "materials": ["白水晶 8mm", "月光石 6mm", "白水晶切面 6mm", "银色隔珠"],
        "tags": ["白水晶", "清透", "通勤"],
        "source_page": "https://oralia.in/products/crystal-beads-stretchable-bracelet-1",
    },
    {
        "post_id": "test-inspo-clear-quartz-palm",
        "title": "掌心净透",
        "desc": "圆珠白水晶保留天然包体，视觉轻、气质安静，适合低负担佩戴。",
        "story": "把手串放在掌心时，最打动人的是水晶和皮肤之间的柔光。这个方案不追求复杂装饰，而是用连续圆珠做出安定、清爽的节奏。",
        "scene": "冥想、居家、轻运动、素色穿搭",
        "tone": "clear",
        "recipe": ["clearQuartz", "clearQuartz", "moonstone", "silverSpacer"],
        "materials": ["白水晶圆珠 8mm", "白水晶圆珠 6mm", "月光石 6mm", "银色隔珠"],
        "tags": ["净透", "极简", "日常"],
        "source_page": "https://uniwamart.com/products/gd506",
    },
    {
        "post_id": "test-inspo-faceted-quartz-bloom",
        "title": "花影切面白水晶",
        "desc": "切面白水晶在木色和花影里更有闪光，适合想要精致但不夸张的人。",
        "story": "灵感来自干花、浅木和透明晶体的组合。切面珠负责捕捉光，月光石负责柔化边界，成串后有一点手作礼物的温度。",
        "scene": "约会、礼物、周末咖啡、浅色针织",
        "tone": "pink",
        "recipe": ["clearQuartz", "moonstone", "roseQuartz", "silverSpacer"],
        "materials": ["白水晶切面 8mm", "月光石 6mm", "粉晶 6mm", "银色隔珠"],
        "tags": ["切面", "温柔", "礼物"],
        "source_page": "https://temporlainbloom.com.au/products/faceted-clear-quartz-bracelet-8mm",
    },
    {
        "post_id": "test-inspo-citrine-sun",
        "title": "黄水晶小太阳",
        "desc": "黄水晶圆珠有自然金色包体，整体明亮、有精神，适合需要一点行动感的搭配。",
        "story": "这条方案以黄水晶为主角，保留金黄色的天然层次。配方里加入少量白水晶，让明亮感不过分厚重，更适合日常穿戴。",
        "scene": "工作日、会议、旅行、暖色穿搭",
        "tone": "gold",
        "recipe": ["citrine", "clearQuartz", "citrine", "goldSpacer"],
        "materials": ["黄水晶 8mm", "白水晶 6mm", "黄水晶 6mm", "金色隔珠"],
        "tags": ["黄水晶", "明亮", "行动感"],
        "source_page": "https://mindfulsouls.com/products/citrine-bead-bracelet",
    },
    {
        "post_id": "test-inspo-amethyst-wood",
        "title": "紫晶木影",
        "desc": "深紫色紫水晶搭配自然木纹，适合想要沉静、有一点艺术感的方案。",
        "story": "紫水晶本身颜色很有存在感，所以配方不做复杂堆叠，用白水晶和银色隔珠拉开呼吸感，让紫色保留主角位置。",
        "scene": "夜间出行、展览、深色针织、独处时刻",
        "tone": "black",
        "recipe": ["amethyst", "clearQuartz", "amethyst", "silverSpacer"],
        "materials": ["紫水晶 8mm", "白水晶 6mm", "紫水晶 6mm", "银色隔珠"],
        "tags": ["紫水晶", "沉静", "艺术感"],
        "source_page": "https://themiraclehub.in/blog/amethyst-bracelet-benefits-and-uses",
    },
    {
        "post_id": "test-inspo-rose-quartz-soft",
        "title": "粉晶柔雾",
        "desc": "粉晶色调轻柔，适合想要温暖、干净、不过分甜腻的手串视觉。",
        "story": "粉晶很容易做得太甜，这里只保留低饱和粉色，搭配白水晶和月光石，让它更像一层柔雾，而不是强烈装饰。",
        "scene": "约会、生日礼物、浅色裙装、春夏日常",
        "tone": "pink",
        "recipe": ["roseQuartz", "moonstone", "clearQuartz", "goldSpacer"],
        "materials": ["粉晶 10mm", "月光石 6mm", "白水晶 6mm", "金色隔珠"],
        "tags": ["粉晶", "柔和", "礼物"],
        "source_page": "https://blessingandluck.com/products/rose-quartz-bracelet",
    },
    {
        "post_id": "test-inspo-aquamarine-breeze",
        "title": "海蓝宝微风",
        "desc": "淡蓝色海蓝宝清爽干净，适合夏天、白色上衣和需要降低视觉重量的搭配。",
        "story": "海蓝宝的蓝不是强烈的蓝，而是带一点雾感的浅色。配方中加入白水晶让整体更亮，银色隔珠则让蓝色显得更清爽。",
        "scene": "夏日通勤、白 T、旅行、海边穿搭",
        "tone": "blue",
        "recipe": ["aquamarine", "clearQuartz", "moonstone", "silverSpacer"],
        "materials": ["海蓝宝 8mm", "白水晶 6mm", "月光石 6mm", "银色隔珠"],
        "tags": ["海蓝宝", "清爽", "夏日"],
        "source_page": "https://bailong.easy.co/products/aquamarine-bracelet-%E6%B5%B7%E8%93%9D%E5%AE%9D%E6%89%8B%E9%93%BE",
    },
    {
        "post_id": "test-inspo-tiger-eye-wood",
        "title": "虎眼石木色守护",
        "desc": "虎眼石的金棕光带很适合木质背景，整体更稳、更有力量感。",
        "story": "这条灵感保留虎眼石天然的猫眼光感，配方里少量加入黄水晶和金色隔珠，让棕金色不显沉，适合偏中性和复古的穿搭。",
        "scene": "复古衬衫、中性穿搭、商务休闲、秋冬叠戴",
        "tone": "gold",
        "recipe": ["tigerEye", "citrine", "clearQuartz", "goldSpacer"],
        "materials": ["虎眼石 10mm", "黄水晶 6mm", "白水晶 6mm", "金色隔珠"],
        "tags": ["虎眼石", "复古", "稳定"],
        "source_page": "https://ladylaila.com/products/tiger-eye-natural-stone-polished-round-beads-elastic-bracelet",
    },
]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def extract_meta(html_text: str) -> list[str]:
    patterns = [
        r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image(?::secure_url)?["\']',
        r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<img[^>]+src=["\']([^"\']+)["\']',
    ]
    urls: list[str] = []
    for pattern in patterns:
        urls.extend(re.findall(pattern, html_text, flags=re.I))
    return [html.unescape(url).strip() for url in urls if url.strip()]


def resolve_image_url(client: httpx.Client, page_url: str) -> str:
    response = client.get(page_url)
    response.raise_for_status()
    candidates = []
    for url in extract_meta(response.text):
        full_url = urljoin(page_url, "https:" + url if url.startswith("//") else url)
        lowered = full_url.lower()
        if any(token in lowered for token in ("logo", "icon", "payment", "sprite")):
            continue
        if any(ext in lowered for ext in (".jpg", ".jpeg", ".png", ".webp")):
            candidates.append(full_url)
    if not candidates:
        raise RuntimeError(f"没有在页面中找到可用图片：{page_url}")
    return candidates[0]


def download_image(client: httpx.Client, url: str) -> tuple[bytes, str]:
    response = client.get(url, follow_redirects=True)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if not content_type.startswith("image/"):
        raise RuntimeError(f"下载结果不是图片：{url} ({content_type})")
    return response.content, content_type


def to_webp(content: bytes) -> bytes:
    image = Image.open(BytesIO(content))
    image = ImageOps.exif_transpose(image).convert("RGB")
    image = ImageOps.fit(image, (1200, 900), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    output = BytesIO()
    image.save(output, format="WEBP", quality=88, method=6)
    return output.getvalue()


def seed(database: str, dry_run: bool, cos_bucket: str | None, cdn_base_url: str | None) -> None:
    load_env_file(ROOT / ".env.local")
    load_env_file(ROOT / ".env")
    os.environ["DATABASE_BACKEND"] = "mysql"
    os.environ["MYSQL_DATABASE"] = database
    if database == "yujian_test":
        os.environ["TENCENT_COS_BUCKET"] = cos_bucket or os.getenv("TENCENT_TEST_COS_BUCKET") or "yujian-test-1258267288"
        os.environ["TENCENT_COS_CDN_BASE_URL"] = cdn_base_url or os.getenv("TENCENT_TEST_COS_CDN_BASE_URL") or "https://cdn-test.yustream.cn"
    elif cos_bucket:
        os.environ["TENCENT_COS_BUCKET"] = cos_bucket
    if cdn_base_url:
        os.environ["TENCENT_COS_CDN_BASE_URL"] = cdn_base_url.rstrip("/")

    service = None if dry_run else AdminService()
    storage = None if dry_run else AvatarStorage()
    timeout = httpx.Timeout(30, connect=15)
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,image/avif,image/webp,image/apng,image/*,*/*;q=0.8"}

    with httpx.Client(headers=headers, follow_redirects=True, timeout=timeout) as client:
        for index, post in enumerate(POSTS, start=1):
            image_url = post.get("image_url") or resolve_image_url(client, post["source_page"])
            content, content_type = download_image(client, image_url)
            webp = to_webp(content)
            uploaded_url = image_url
            if not dry_run:
                assert storage is not None
                result = storage.upload_media(
                    prefix="community/inspiration-test",
                    user_id=post["post_id"],
                    content=webp,
                    content_type="image/webp",
                    filename=f"{post['post_id']}.webp",
                    label="灵感图片",
                )
                uploaded_url = result.url

            payload = {
                **post,
                "author": "宇涧灵感室",
                "likes": 0,
                "image_url": uploaded_url,
                "status": "published",
                "sort_order": index,
            }
            payload.pop("source_page", None)

            if dry_run:
                print(f"[dry-run] {post['post_id']} image={image_url} webp={len(webp)} bytes")
                continue
            assert service is not None
            saved = service.save_community_post(payload, post_id=post["post_id"])
            print(f"[saved] {saved['id']} {saved['title']} {uploaded_url}")


def main() -> None:
    parser = argparse.ArgumentParser(description="创建灵感社区测试数据，并把真实手串图片上传到 COS。")
    parser.add_argument("--database", default="yujian_test", help="目标 MySQL 数据库，默认 yujian_test")
    parser.add_argument("--cos-bucket", default=None, help="覆盖 COS bucket；测试库默认 yujian-test-1258267288")
    parser.add_argument("--cdn-base-url", default=None, help="覆盖图片 CDN 根地址；测试库默认 https://cdn-test.yustream.cn")
    parser.add_argument("--dry-run", action="store_true", help="只下载和转换图片，不上传 COS、不写数据库")
    args = parser.parse_args()
    seed(
        database=args.database,
        dry_run=args.dry_run,
        cos_bucket=args.cos_bucket,
        cdn_base_url=args.cdn_base_url,
    )


if __name__ == "__main__":
    main()
