# 订单链路加固上线说明

## 变更范围

- 删除旧版单数售后接口和主订单 `after_sale` 状态。
- 增加结构化售后工单、用户退回物流和取消动作。
- 收紧发货、地址修改、确认收货、直接退款和售后退款事务。
- 退款外部调用采用本地 claim，防止重复提交。
- 退款网络结果不确定时先查微信，明确未生效后才使用原退款单号恢复提交。
- 待发货全额退款成功后幂等回补库存；发货后退款等待仓库验收。
- 增加独立 commerce maintenance worker，先支付对账再释放过期库存。
- 删除后台任意修改订单状态的 API。

## 数据库迁移

依次执行：

- `20260713_08_after_sale_cases`
- `20260714_09_after_sale_return_flow`

v08 新增售后工单与事件表；v09 只为工单新增退回物流和取消时间字段。两者均不删除订单旧列。应用不得依赖启动时自动补生产字段。

## 上线顺序

1. 保持 `COMMERCE_CHECKOUT_ENABLED=false`、`WECHAT_PAYMENT_ENABLED=false`、`COMMERCE_MAINTENANCE_ENABLED=false`。
2. 停止 API、物流 worker 和 commerce worker 的写入实例。
3. 备份订单、订单请求、库存预占、支付事件、售后工单和售后事件表，并验证备份可读。
4. 执行版本化 migration upgrade，核对 `schema_migrations`。
5. 部署 API、运营后台和小程序候选版本，先不启用 commerce worker。
6. 在非生产支付链路验证创建、取消、发货、确认收货、直接退款和退货退款。
7. 配置并验证微信支付查询能力后，单实例启用 `COMMERCE_MAINTENANCE_ENABLED=true`。
8. 观察 `runtime_task_runs`；出现 `partial_failed`、支付补偿待办或库存不一致时立即停用 worker 并阻止放量。

## 空数据起步

本版本不兼容旧测试订单。若上线前决定清除测试订单，必须先备份相关表，再按外键和业务依赖从子记录到主记录清理：售后事件、售后工单、库存预占、订单幂等请求、支付事件，最后才是订单。清理脚本必须在目标数据库核对库名和记录数后单独审批执行，本次代码改造不自动清库。

清理后至少校验：

- `orders`、`order_requests`、`inventory_reservations`、`after_sale_cases`、`after_sale_events` 无孤儿记录。
- `managed_materials.reserved_stock >= 0` 且不大于 `stock`。
- 没有 `payment_status=processing` 的遗留订单。
- 没有 `processing_status=compensation_required` 的未处理支付事件。

## 回滚

1. 先设置 `COMMERCE_MAINTENANCE_ENABLED=false` 并停止 commerce worker。
2. 停止新 API 写入并回滚应用镜像。
3. 默认保留 additive 新表和字段，旧应用可忽略它们。
4. 只有在已备份、无新售后数据且所有新进程停止后，才按 v09、v08 的逆序 downgrade。
5. 若退款指令已处于 `submitting|processing`，不得通过应用回滚重新提交，必须先按商户退款单号核对微信状态。

## 人工验收

- 同一发货单号重复提交不产生第二条发货历史；不同单号返回冲突。
- 待发货退款拒绝后恢复“待发货”，不会出现“商家待发货/打包中”两个并列状态。
- 已发货订单显示“已发货待揽收 -> 运输中 -> 已签收 -> 待确认收货 -> 已完成”。
- 售后列表能看到已完成或运输中订单的独立售后状态，同时订单详情保留完整履约时间线。
- 并发点击退款只产生一次微信退款调用；网络超时恢复会先查询，并复用原商户退款单号。
- 支付处理中且预占过期时库存保持预占，微信明确未支付后才释放。
