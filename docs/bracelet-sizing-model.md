# 手串有效串长模型

## 目标

DIY 工作台不能直接用 `珠径总和` 当作可佩戴串长。珠子聚成圆后，珠体厚度会吃掉内圈空间；同样的直线长度，圆珠手串戴起来会比链条或细绳更紧。

因此工作台采用两个独立概念：

- `有效串长`：手串聚成圆后，近似可容纳手腕的长度。
- `舒适松量`：在裸手围基础上额外留出的佩戴余量。

## 当前公式

```text
有效串长 mm = 所有珠径总和 mm - 平均珠径 mm × 成串损耗系数
推荐目标 mm = 裸手围 cm × 10 + 舒适松量 mm
```

当前参数：

```text
成串损耗系数 = 1.0
舒适松量 = 8mm
```

示例：

```text
21 颗 8mm 圆珠
直线总长 = 21 × 8 = 168mm
有效串长 = 168 - 8 × 1.0 = 160mm
```

## 参数依据

珠宝和串珠尺码资料通常会把成品手链长度设置为 `手围 + 佩戴松量`，而不是裸手围本身。Think Beads 将常规舒适佩戴建议为手围加 0.5 到 0.75 inch，Bravado Bay 的舒适档为加 0.50 inch；Fire Mountain Gems 的串珠问答用“把珠子和隔片长度加到目标成品长度”的方式计算颗数；Jewelry Making Journal 还明确说明 10mm 这类粗珠会占用手链内侧空间，需要额外增加长度。

项目先取更贴近小程序当前体验的保守值：

- 舒适松量：8mm，沿用工作台原有 `wristSize + 0.8cm` 的判断口径。
- 成串损耗系数：1.0，即先把内圈损耗折算为约 1 颗平均珠径。

## 后续校准建议

后续可以用真实样品校准系数：

1. 每种常用珠径取 3 条实物样品，例如 6mm、8mm、10mm、12mm。
2. 记录颗数、珠径、实际内圈舒适手围。
3. 反推：

```text
成串损耗系数 = (珠径总和 - 实测有效串长) / 平均珠径
```

4. 如果差异明显，再按珠径或珠形分组：

```text
小圆珠 4-6mm：0.7 - 0.9
常规圆珠 7-9mm：1.0
大圆珠 10mm+：1.1 - 1.4
随形 / 异形：按实测单独建模
```

## 参考资料

- Jewelry Making Journal, Bracelet Sizes Guide: https://jewelrymakingjournal.com/bracelet-sizes/
- Fire Mountain Gems, Ask the Experts Stretch Bracelet Sizing Q&A: https://www.firemountaingems.com/learn/categories/ask-the-experts/RH54-ask-the-experts.html
- Think Beads, Bracelet Sizing Guide: https://thinkbeads.com/pages/bracelet-sizing-guide
- Bravado Bay, Stretch Bracelet Size Guide: https://bravadobay.com/pages/copy-of-stretch-bracelet-size-guide
