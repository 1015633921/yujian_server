from app.order_service import WechatPayConfig


config = WechatPayConfig()
public_key = config.public_key_bytes()
print(
    {
        "public_key_id": config.public_key_id,
        "public_key_loaded": bool(public_key),
        "public_key_length": len(public_key or b""),
        "test_mode": config.test_mode,
        "payment_ready": config.ready,
    }
)
