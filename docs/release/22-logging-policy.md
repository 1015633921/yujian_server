# 结构化日志与追踪策略

应用日志输出单行 JSON，至少包含：`timestamp`、`level`、`service`、`request_id`、`user_id_hash`、`logger`、`event`、`message`。HTTP 和业务事件另外包含 route、method、duration_ms、result 或安全错误类型。

request ID 只接受 8 至 128 位的字母、数字、点、下划线、冒号和连字符；无效或缺失时生成随机 `req_` ID。相同客户端 ID允许用于一次明确重试链路。小程序请求封装自动添加 `X-Request-ID`，网络重试复用原 ID。响应始终返回同名 header。

禁止日志字段：Authorization、Token、OpenID/UnionID、手机号、地址、出生信息、支付报文、Secret、密码、请求体和完整第三方响应。用户 ID 使用 `LOG_HASH_SALT` 加盐 SHA-256 的前 16 位；生产 readiness 要求显式配置 salt。

关键事件：登录成功/失败、报告生成/读取、依据读取、海报 DTO、订单创建、支付/退款回调、物流运行和所有第三方失败。支付事件 ID 与 assessment ID 仅记录摘要；订单号只保留末 6 位。

异常日志记录 request ID、路由、方法和 error type。traceback 经过 Token、Secret、OpenID 和手机号文本脱敏；不启用 locals。客户端 500 响应不包含 traceback、SQL、文件路径或异常原文。

当前 formatter 覆盖应用 logger；Uvicorn/Nginx 自身访问日志的 JSON 化和集中采集属于 P1-D 部署配置。Nginx 应透传 `X-Request-ID`，不得记录 Authorization 或请求体。
