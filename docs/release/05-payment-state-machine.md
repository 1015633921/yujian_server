# 支付、履约与售后状态机

## 唯一模型

新订单不兼容旧测试数据。订单只使用以下三条相互独立的状态轴：

- `orders.status`：付款、发货、收货、完成、退款和关闭。
- `orders.payment_status`：未支付、支付处理中、已支付、已退款及失败终态。
- `after_sale_cases.status`：售后审核、寄回、服务处理和退款进度。

`orders.status=after_sale` 和旧版 `/orders/{order_id}/after-sale` 不再存在。创建售后工单不会覆盖发货或完成状态。

## 订单状态

| 订单状态 | 支付状态 | 含义 | 合法下一状态 | 唯一触发方 |
|---|---|---|---|---|
| `pending_payment` | `unpaid` | 待付款，库存已预占 | `pending_ship/paid`、`closed/cancelled`、`closed/expired`、`closed/failed` | 微信支付结果、用户取消、维护任务 |
| `pending_payment` | `processing` | 微信仍在确认支付 | `pending_payment/unpaid`、`pending_ship/paid`、`closed/failed` | 微信支付查询或通知 |
| `pending_ship` | `paid` | 已支付，待制作和发货 | `shipped/paid`、`refund_requested/paid` | 后台发货、用户直接退款 |
| `shipped` | `paid` | 已发货，含待揽收、运输中和已签收 | `completed/paid`、`refund_requested/paid` | 用户确认、签收 7 天任务、售后退款审核 |
| `completed` | `paid` | 履约完成 | `refund_requested/paid` | 售后退款审核 |
| `refund_requested` | `paid` | 已进入真实退款流程 | `refunded/refunded`、`pending_ship/paid` | 微信退款结果；仅待发货直接退款可由审核拒绝后恢复 |
| `refunded` | `refunded` | 已退款，不可逆 | 无 | 微信退款成功通知或主动查询 |
| `closed` | `cancelled|expired|failed` | 未支付订单已关闭 | 无 | 用户取消、明确支付失败或预占过期 |

后台没有任意修改订单状态的 API。所有状态变化必须走对应业务动作。

## 发货与物流

1. 只有 `pending_ship + paid` 且无退款中的订单可以发货。
2. 本地事务先锁订单并写入 `shipped`、快递单号和“已发货待揽收”。
3. 同一快递单号重复提交幂等；不同单号返回 `409`。
4. 微信发货上传和快递 100 订阅在本地事务提交后执行，失败只记录重试状态，不回滚已发货事实。
5. 快递已签收仍保持 `shipped`；用户确认后立即完成，未确认则签收满 7 天自动完成。

## 售后工单

| 工单状态 | 含义 | 下一动作 |
|---|---|---|
| `requested` | 用户已提交 | 运营拒绝、接受服务、要求寄回或批准免退退款 |
| `awaiting_return` | 等待用户寄回 | 用户提交退回物流或取消工单 |
| `returning` | 用户已提交退回单号 | 运营确认收到退货 |
| `service_processing` | 改手围、维修或补发处理中 | 运营确认服务完成 |
| `refund_pending` | 售后审核完成，尚未调用微信退款 | 运营二次确认退款 |
| `refund_submitting` | 退款指令已登记，外部结果不确定 | 先同步微信；明确不存在且超过 60 秒保护期后，才可用原退款单号恢复提交 |
| `refunding` | 微信退款处理中 | 等待通知或主动同步 |
| `resolved` | 服务或退款已完成 | 终态 |
| `rejected` / `canceled` | 已拒绝或用户取消 | 终态，可重新发起新工单 |

用户退回单号、工单取消、后台审核、退款提交和退款通知均按“先锁订单、再锁工单”的固定顺序执行。

## 支付与库存

- 支付成功：`reserved -> confirmed`，同时扣减 `stock` 和 `reserved_stock`。
- 未支付取消、明确失败或过期：`reserved -> released|expired`，只减少 `reserved_stock`。
- `payment_status=processing` 时，预占过期也不得释放；必须先查询微信结果。
- 待发货全额退款成功：`confirmed -> restocked`，库存只回补一次。
- 已发货或已完成退款：标记 `pending_manual_inspection`，退货验收后的实物入库由仓库流程处理。
- 任一数据库步骤失败，订单、库存、历史和事件整体回滚。

## 退款幂等

运营确认退款时先在本地事务内把退款标记为 `submitting`，并记录提交尝试次数和尝试标识，再调用微信。并发或重复确认看到 `submitting|processing|success` 时返回冲突，不会再次调用外部退款。

外部调用结果不确定时，恢复动作必须先按同一商户退款单号查询微信：

- 微信返回 `PROCESSING` 或 `SUCCESS`：只同步结果，不发起第二次退款。
- 微信明确返回退款单不存在：首次提交满 60 秒后，才允许使用原 `out_refund_no` 恢复提交。
- 微信返回 `ABNORMAL` 或 `CLOSED`：售后工单回到 `refund_pending`，运营可核对后使用原 `out_refund_no` 恢复提交。
- 查询超时、鉴权失败或其他未知错误：保持原状态并 fail closed，不提交退款。

每次恢复都复用原商户退款单号，不生成新单号；微信官方规定同一商户退款单号多次请求只退款一次，失败重试也应使用原单号。

## 维护任务

库存过期与支付处理中对账由独立 `app.commerce_worker` 执行，不在 Uvicorn worker 内启动线程：

- `COMMERCE_MAINTENANCE_ENABLED` 默认 `false`。
- 每轮先对账支付处理中订单，再处理过期预占。
- 数据库租约保证同一窗口只有一个实例执行。
- 若存在处理中预占但微信配置不可用，任务返回 `partial_failed`，库存保持预占并触发人工关注。

前端 `wx.requestPayment.success` 只代表客户端调用结束。只有受鉴权的订单接口返回 `payment_status=paid`，页面才显示支付成功。
