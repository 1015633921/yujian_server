from app.order_service import OrderService, WechatPayConfig


config = WechatPayConfig()
print(
    {
        "ready": config.ready,
        "missing": config.missing,
        "test_mode": config.test_mode,
        "private_key_loaded": len(config.private_key_bytes()) > 1000,
        "api_v3_configured": bool(config.api_v3_key),
        "wechat_public_key_loaded": bool(config.public_key_bytes()),
    }
)
