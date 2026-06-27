import sqlite3

from app.order_service import OrderService
from app.repository import DB_PATH


with sqlite3.connect(DB_PATH) as connection:
    row = connection.execute(
        """
        SELECT user_id FROM users
        WHERE COALESCE(openid, '') <> '' AND openid NOT LIKE 'dev_%'
        ORDER BY updated_at DESC LIMIT 1
        """
    ).fetchone()

if not row:
    print({"real_wechat_user": False})
else:
    result = OrderService().create_order(
        {
            "user_id": row[0],
            "receiver": {
                "name": "支付联调",
                "phone": "13800000000",
                "address": "微信支付一分钱联调订单",
            },
            "design": {"summary": {"price": 0.01}},
            "sequence": [{"name": "支付测试", "price": 0.01}],
            "bom": [],
            "remark": "WECHAT_PAY_TEST_MODE",
        }
    )
    payment = result["payment"]
    print(
        {
            "real_wechat_user": True,
            "order_id": result["order"]["order_id"],
            "total_fee": result["order"]["total_fee"],
            "payment_available": payment.get("available"),
            "payment_state": payment.get("state"),
            "pay_params_ready": bool(payment.get("pay_params")),
        }
    )
