# 宇涧水晶小程序页面映射

## 技术栈摘要

- 小程序：微信原生小程序，页面由 `.wxml`、`.wxss`、`.js`、`.json` 组成。
- 路由配置：`miniprogram/app.json`
- 全局样式：`miniprogram/app.wxss`
- 接口工具：`miniprogram/utils/api.js`
- 登录工具：`miniprogram/utils/auth.js`
- 物理引擎依赖：`miniprogram/package.json` 中的 `matter-js`
- 后端：FastAPI，入口 `app/main.py`

## 当前 tabBar

当前 `miniprogram/app.json` 的 tabBar 为：

| Tab | 路由 |
| --- | --- |
| 首页 | `pages/home/home` |
| 灵感 | `pages/community/community` |
| DIY | `pages/workspace/workspace` |
| 我的 | `pages/profile/profile` |

设计图中包含“购物车”Tab；当前项目没有购物车 tabBar 项，购物车相关页面是 `pages/inspiration-cart/inspiration-cart`。后续若要把购物车加入底部导航，需要单独确认，不应在单页视觉重构中顺手修改。

## 页面与文件映射

| 任务 | 页面 | 路由/文件 |
| --- | --- | --- |
| P01 | 首页 | `miniprogram/pages/home/home.*` |
| P02 | 定制方式选择页 | `miniprogram/pages/custom-mode/custom-mode.*` |
| P03 | 测算信息填写页 | `miniprogram/pages/assessment/assessment.*` |
| P04 | 测算结果页 | `miniprogram/pages/report/report.*` |
| P05 | 方案推荐页 | `miniprogram/pages/plan-detail/plan-detail.*`、`miniprogram/pages/recommendation-detail/recommendation-detail.*`（需审计确认实际入口） |
| P06 | DIY 工作台 | `miniprogram/pages/workspace/workspace.*` |
| P07 | 方案确认页 | `miniprogram/pages/checkout/checkout.*` |
| P08 | 订单提交成功页 | 可能由 `checkout` 成功态或 `order-detail` 承载，需审计确认 |
| P09 | 灵感库页 | `miniprogram/pages/community/community.*` |
| P10 | 购物车页 | `miniprogram/pages/inspiration-cart/inspiration-cart.*` |
| P11 | 我的方案页 | 当前可能由 `profile` / `plan-detail` / `community-favorites` 分散承载，需审计确认 |
| P12 | 个人中心页 | `miniprogram/pages/profile/profile.*` |

## 推荐重构顺序

1. P00 设计变量与基础组件
2. P01 首页
3. P02 定制方式选择页
4. P03 测算信息填写页
5. P04 测算结果页
6. P05 方案推荐页
7. P06 DIY 工作台
8. P07 方案确认页
9. P08 订单提交成功页
10. P09 灵感库页
11. P10 购物车页
12. P11 我的方案页
13. P12 个人中心页

## 已识别风险

- 设计图包含购物车 tab，但当前 tabBar 没有购物车。
- P02、P08、P11 在当前项目中可能不是独立页面，需要先确认真实业务入口。
- DIY 工作台涉及动画、碰撞、音效和性能，不适合与其他页面一起改。
- 首页、灵感页、热门推荐和后台内容数据存在联动，不能用静态图替换真实接口。
- 订单、支付、openid、购物订单、物流履约属于高风险链路，视觉重构时不得修改业务逻辑。
- 当前工作区已有大量历史未提交改动，执行页面任务前必须确认修改范围。
