# P06 DIY 工作台

## 目标

重构 DIY 工作台视觉和布局，提升不同机型适配、操作清晰度和性能表现。

## 上下文

- 页面实现：`miniprogram/pages/workspace/workspace.*`
- WXS：`miniprogram/pages/workspace/workspace.wxs`
- 参考图：`docs/design/references/P06-workspace.png`

## 必须保留的功能

- 珠材选择
- 珠子弹射和碰撞
- 手串环形排列
- 调整腕围
- 重新成串/解除组串
- 撤销/还原
- 清空、保存、预览、加入购物车/完成定制
- 五行占比展示
- 音效如当前已实现

## 视觉要求

- 工作盘居中，有刻度。
- 右侧工具栏清晰可识别，不遮挡盘子。
- 五行占比以小卡/按钮展示，不遮挡手串。
- 底部材料库与结算栏不挤压画布。

## 完成标准

- 真机不卡顿明显改善。
- 珠子不大面积重叠。
- 窄屏机型按钮不重叠。
- 编译无 WXML unexpected end。

