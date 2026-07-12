# 支付与订单状态机

## 当前模型

订单状态 `status` 与支付状态 `payment_status` 分离。P1-A 不删除旧状态，只收紧支付事件可触发的转换。

| 订单状态 | 支付状态 | 含义 | 合法下一状态 | 触发方 |
|---|---|---|---|---|
| `pending_payment` | `unpaid` | 待付款，库存已预占 | `pending_ship/paid`、`closed/cancelled`、`closed/expired`、`closed/failed` | 支付成功仅服务端；关闭可由用户取消、超时或预下单失败触发 |
| `pending_payment` | `processing` | 支付处理中 | `pending_ship/paid`、`closed/failed` | 服务端支付查询/通知；客户端只能读取 |
| `pending_ship` | `paid` | 已支付待发货，库存预占已确认 | `shipped/paid`、`refund_requested/paid` | 服务端通知、后台履约或用户退款申请 |
| `shipped` | `paid` | 已支付待收货 | `completed/paid`、`after_sale/paid`、`refund_requested/paid` | 用户或后台履约 |
| `completed` | `paid` | 已完成 | `after_sale/paid` | 用户售后 |
| `refund_requested` | `paid` | 退款处理中 | `refunded/refunded`、`after_sale/paid` | 退款通知/主动查询或后台审核 |
| `refunded` | `refunded` | 已退款，不可逆 | 无 | 仅服务端退款通知/主动查询 |
| `closed` | `cancelled/expired/failed` | 已取消、超时或支付失败，不可直接恢复 | 无 | 用户取消、超时任务或服务端失败处理 |

## 支付通知规则

- `TRANSACTION.SUCCESS` 只允许把 `pending_payment + unpaid/processing` 转为 `pending_ship + paid`。
- 已支付订单再次收到同一或另一成功通知，校验交易号和金额一致后幂等成功，不重复确认库存或写历史。
- 已支付订单收到旧的 `NOTPAY/USERPAYING/CLOSED/PAYERROR` 事件只记事件处理结果，不降级订单。
- 已关闭、已取消、已过期或失败订单收到支付成功通知时不恢复订单，事件终态标记为 `compensation_required` 并进入人工补偿队列；不得自动恢复库存或发货。
- 未支付订单收到支付失败/关闭类事件时，只在明确终态且订单仍为待付款时关闭订单并释放预占；`USERPAYING` 仅把支付状态更新为 `processing`，`NOTPAY` 不修改订单。
- 支付成功事务必须同时完成支付快照、订单状态、订单历史、库存确认和事件成功标记。

## 退款通知规则

- 退款通知复用统一事件台账。
- 只有已支付且处于 `refund_requested` 的订单可以由退款成功通知进入 `refunded`。
- 未支付、已关闭或已取消订单收到退款成功通知时 fail closed，不得进入已退款。
- 已退款订单收到重复成功通知幂等返回；旧的 `PROCESSING/ABNORMAL/CLOSED` 通知不得把 `refunded` 降级。
- 退款金额、原订单金额、商户号、商户订单号和交易号必须与订单支付快照及退款申请一致。

## 库存一致性

- 支付成功：`reserved -> confirmed`，同时 `stock -= quantity`、`reserved_stock -= quantity`。
- 取消、超时或支付失败：`reserved -> released/expired`，只减少 `reserved_stock`。
- 已确认预占永不被超时任务释放；已释放预占不能再次确认。
- 任一数据库步骤失败，订单、库存、历史和事件处理结果整体回滚。

## 前端确认

- `wx.requestPayment.success` 只进入“支付确认中”。
- 前端有限退避轮询受鉴权的本地订单详情；只有 `payment_status=paid` 才展示支付成功。
- 轮询超时展示“支付结果确认中，可稍后在订单列表查看”。
- 用户取消、明确失败和未知结果使用不同文案；页面卸载或账号变化立即停止轮询。
