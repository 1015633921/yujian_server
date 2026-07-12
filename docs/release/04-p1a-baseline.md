# P1-A 支付完整性实施基线

记录时间：2026-07-12。当前项目整体结论：**NO-GO**。

## Git 基线

- 分支：`codex/material-taxonomy-checkpoint`。
- HEAD：`454668e feat: show MBTI influence in assessment results`。
- P0-A、P0-B、报告页和工作台等修改仍在未提交工作区；P1-A 必须保留这些改动。
- 本阶段禁止提交、推送、部署、连接生产数据库和调用真实微信支付/退款接口。

## 修改前测试

| 命令 | 结果 |
|---|---|
| `pytest -q tests/test_api.py -k 'wechat or pay or refund or order' tests/test_p0b_order_integrity.py::test_payment_confirmation_is_idempotent_and_stock_never_negative -p no:cacheprovider` | `17 passed, 44 deselected, 1 warning` |
| `pytest -q --ignore=tests/minium -p no:cacheprovider` | `127 passed, 1 skipped, 1 failed, 1 warning` |
| `node --test tests/js/*.test.js` | `38 passed, 0 failed` |
| `git diff --check` | 通过 |

Minium 按项目默认规则未运行。MySQL 并发测试因本机无 Docker/MySQL 运行时而跳过。

## 原有失败

`tests/test_energy.py::test_recommendation_primary_follows_wish_and_support_avoids_primary_elements`：财富愿望期望黄水晶等主石，实际返回 `green_phantom`。该失败在 P0-A 前已存在，不属于 P1-A。

## 支付现状

- 支付通知先验签、再解密，但没有数据库事件唯一键或处理台账。
- 支付成功会在一个订单事务中确认预占并更新订单，但重复/并发通知仅依靠订单状态判断。
- 非 `SUCCESS` 支付通知直接返回，没有状态审计和乱序规则。
- 退款通知没有统一事件去重，重复非成功通知会重复追加订单历史。
- checkout 在 `wx.requestPayment.success` 后直接显示“支付完成”，未等待服务端订单状态。
- 订单详情已有 6 次固定间隔轮询，但没有卸载取消、账号绑定和明确的取消/未知状态区分。
