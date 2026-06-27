import inspect

from app.auth_service import WechatAuthService


service = WechatAuthService()
print(
    {
        "app_id": service.app_id,
        "app_id_configured": bool(service.app_id),
        "app_secret_configured": bool(service.app_secret),
        "auth_source_has_pay_app_id_fallback": "WECHAT_PAY_APP_ID"
        in inspect.getsource(WechatAuthService.__init__),
    }
)
