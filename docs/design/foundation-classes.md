# P00 基础类使用说明

P00 已在 `miniprogram/app.wxss` 中建立 `--yu-*` 设计变量和 `.yu-*` 基础类。后续页面重构优先复用这些类，不要在页面私有样式中重复散落颜色、圆角和阴影。

## 设计变量

变量挂载在 `page` 上，核心包括：

- `--yu-color-bg-page`
- `--yu-color-bg-page-warm`
- `--yu-color-bg-card`
- `--yu-color-text-primary`
- `--yu-color-text-secondary`
- `--yu-color-line`
- `--yu-color-anchor-dark`
- `--yu-color-blue`
- `--yu-color-yellow`
- `--yu-color-red`
- `--yu-color-purple`
- `--yu-color-green`
- `--yu-radius-control`
- `--yu-radius-card`
- `--yu-radius-card-lg`
- `--yu-radius-pill`
- `--yu-shadow-soft`

## 页面与布局

- `.yu-page`：标准暖白页面容器，包含顶部和底部安全区。
- `.yu-safe-bottom`：只补底部安全区。
- `.yu-section`：页面分区间距。
- `.yu-section-head`：分区标题行。

## 文本

- `.yu-eyebrow`：英文/小字眉标。
- `.yu-title`：页面主标题。
- `.yu-subtitle` / `.yu-desc`：副标题和说明文字。

## 卡片

- `.yu-card`：标准白色卡片。
- `.yu-card-lg`：更大的圆角。
- `.yu-card-soft`：半透明柔和卡片。
- `.yu-card-dark`：深色品牌锚点卡。
- `.yu-card-pressable`：卡片点击态，与 `.yu-card` 组合使用。

## 按钮

- `.yu-button`：按钮基础类。
- `.yu-button-primary`：深色主按钮。
- `.yu-button-secondary`：白底次按钮。
- `.yu-button-green`：绿色完成/保存按钮。
- `.yu-button-danger`：危险操作按钮。
- `.yu-button-ghost`：透明次级按钮。

按钮应组合使用，例如：

```html
<button class="yu-button yu-button-primary">开始定制</button>
```

## 标签与状态

- `.yu-tag`
- `.yu-tag-blue`
- `.yu-tag-yellow`
- `.yu-tag-red`
- `.yu-tag-purple`
- `.yu-tag-green`

## 图片、空状态和加载

- `.yu-image-placeholder`：图片失败或未上传占位。
- `.yu-empty`：空状态容器。
- `.yu-empty-title`：空状态标题。
- `.yu-empty-desc`：空状态说明。
- `.yu-loading`：加载状态容器。
- `.yu-spinner`：加载旋转图标。
- `.yu-skeleton`：骨架屏。

## 交互

- `.yu-pressable`：统一按压反馈。
- `.yu-card-pressable`：卡片按压反馈。

