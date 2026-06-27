from app.auth_service import WechatAuthService


service = WechatAuthService()
token = service.access_token()
print(
    {
        "app_id_configured": bool(service.app_id),
        "app_secret_configured": bool(service.app_secret),
        "access_token_received": bool(token),
        "access_token_length": len(token),
    }
)
