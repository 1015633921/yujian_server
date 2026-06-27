# P00 设计变量与基础组件

## 目标

建立 Light Studio Lab 视觉体系的基础变量和可复用基础样式，不重构具体业务页面。

## 上下文

- 全局样式：`miniprogram/app.wxss`
- 设计系统：`docs/design/design-system.md`
- 总参考图：`docs/design/references/visual-language.png`

## 允许修改

- `miniprogram/app.wxss`
- 必要的全局基础样式
- 必要且兼容现有页面的通用 class

## 禁止修改

- 任何具体业务页面结构
- 后端接口
- 登录、支付、订单、物流逻辑
- tabBar 路由
- 未经确认的新依赖

## 必须建立的基础能力

- 页面背景、卡片、按钮、标签、细线、轻阴影变量
- 安全区 padding 规范
- 图片占位规范
- 统一按压反馈
- 统一空状态/加载状态基础样式

## 完成标准

- 不改变任一页面业务功能。
- 全局样式变量可被后续 P01–P12 复用。
- 已检查至少首页、DIY 工作台、个人中心没有明显回归。

