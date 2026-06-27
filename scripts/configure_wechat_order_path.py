from __future__ import annotations

import argparse
import json

from app.wechat_trade_service import WechatTradeService


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure and verify WeChat shopping order detail path.")
    parser.add_argument(
        "--path",
        default="/pages/order-detail/order-detail?id=${商品订单号}",
    )
    args = parser.parse_args()

    service = WechatTradeService()
    print(json.dumps(service.configure_order_detail_path(args.path), ensure_ascii=False))
    print(json.dumps(service.status(), ensure_ascii=False))


if __name__ == "__main__":
    main()
