"""Verify phantom bead material rows and CDN images in the test environment."""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote

import pymysql

from upload_phantom_beads_to_cos_and_db import load_local_env


SERIES = ("绿幽灵", "红幽灵", "彩幽灵")
ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    load_local_env(ROOT / ".env")
    load_local_env(ROOT / ".env.local")
    database = os.getenv("MYSQL_DATABASE", "yujian_test")
    if database != "yujian_test":
        database = "yujian_test"

    connection = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3307")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  series,
                  COUNT(*) AS rows_count,
                  MIN(size) AS min_size,
                  MAX(size) AS max_size,
                  MIN(JSON_LENGTH(image_urls_json)) AS min_images,
                  MAX(JSON_LENGTH(image_urls_json)) AS max_images,
                  MIN(image_path) AS sample_path,
                  MIN(image_url) AS sample_url
                FROM managed_materials
                WHERE series IN (%s, %s, %s)
                GROUP BY series
                ORDER BY FIELD(series, %s, %s, %s)
                """,
                (*SERIES, *SERIES),
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    print(json.dumps(rows, ensure_ascii=False, default=str, indent=2))

    from qcloud_cos import CosConfig, CosS3Client

    bucket = os.getenv("TENCENT_VERIFY_COS_BUCKET") or "yujian-test-1258267288"
    region = os.getenv("TENCENT_COS_REGION") or "ap-guangzhou"
    client = CosS3Client(
        CosConfig(
            Region=region,
            SecretId=os.getenv("TENCENT_COS_SECRET_ID"),
            SecretKey=os.getenv("TENCENT_COS_SECRET_KEY"),
            Scheme="https",
        )
    )

    for row in rows:
        object_key = f"materials/{row['sample_path']}".replace("//", "/")
        head = client.head_object(Bucket=bucket, Key=object_key)
        print(
            f"{row['series']} cos_head="
            f"{head.get('Content-Length')} {head.get('Content-Type')} {head.get('ETag')}"
        )
        direct_url = f"https://{bucket}.cos.{region}.myqcloud.com/{quote(object_key)}"
        check_url(row["series"], "db_url", row["sample_url"])
        check_url(row["series"], "cos_url", direct_url)

    verify_test_api()


def check_url(series: str, label: str, url: str) -> None:
    try:
        request = urllib.request.Request(
            url,
            headers={
                "Range": "bytes=0-31",
                "User-Agent": "CodexVerify/1.0",
            },
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            data = response.read(32)
            print(
                f"{series} {label} "
                f"url_status={response.status} "
                f"content_type={response.headers.get('Content-Type')} "
                f"bytes={len(data)} "
                f"url={url}"
            )
    except HTTPError as exc:
        print(f"{series} {label} url_status={exc.code} url={url}")
    except URLError as exc:
        print(f"{series} {label} url_error={exc.reason} url={url}")


def verify_test_api() -> None:
    base_url = "https://api.yustream.cn/test-api/api/v1/materials"
    for series in SERIES:
        url = f"{base_url}?top=bead&compact=true&keyword={quote(series)}"
        with urllib.request.urlopen(url, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        materials = payload.get("data", {}).get("materials", [])
        preview = [
            {
                "name": item.get("name"),
                "series": item.get("series"),
                "size": item.get("size"),
                "image_url": item.get("image_url"),
            }
            for item in materials[:3]
        ]
        print(
            f"{series} test_api_count={len(materials)} "
            f"preview={json.dumps(preview, ensure_ascii=False)}"
        )


if __name__ == "__main__":
    main()
