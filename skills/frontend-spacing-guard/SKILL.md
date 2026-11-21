---
name: frontend-spacing-guard
description: 检查前端页面的元素间距——元素紧挨、零间距、文字贴边、浮层压字、行高过紧、可点击元素过近、flex/grid 忘写 gap。用真实浏览器读几何位置，不靠猜 CSS 值。当用户说"元素挤在一起/紧挨着/间距没调/排版拥挤/页面很挤/spacing 有问题/帮我检查下间距/检查一下这个页面/写完前端自检"，或要审查 HTML/CSS/JSX/单页应用的布局间距时使用。自己写完前端代码后也应主动跑一次交付前自检。
agent_created: true
---

# 元素间距守卫

AI 写前端最稳定的失误：元素都在、功能都对，但两个元素之间没有距离。根因是写代码时注意力在"元素是否存在"，而不在"元素之间隔多远"。这个 skill 补上两个动作：

- **写完就查** —— 把页面渲染出来，量出每对相邻元素的真实像素距离
- **写的时候就守** —— 按间距契约组织 CSS，从源头不产生这个问题（见 `reference/spacing-contract.md`）

## 快速开始

```bash
# 本地 HTML 文件
node scripts/run-audit.js --file ./index.html

# dev server（更准：带上真实数据、JS 渲染、异步内容）
node scripts/run-audit.js --url http://localhost:5173/ --viewport desktop,mobile --shot
```

（`scripts/` 指本 skill 目录下的 `scripts/`，在该目录下执行，或把脚本路径换成绝对路径。脚本会自动定位 `playwright-core` 与 Chromium 内核，通常无需额外配置；若提示找不到 Chromium，跑一次 `npx playwright install chromium` 即可，或用 `CHROME_PATH` 指向已有的 chrome.exe。）

常用参数：

| 参数 | 用途 |
|------|------|
| `--viewport desktop,mobile` | 多视口各测一遍，响应式断点处的间距问题只在这里暴露 |
| `--shot` | 生成全页截图，问题元素标红框，便于肉眼确认 |
| `--min-severity warning` | 只看要紧的，过滤 info |
| `--ignore flex-no-gap,edge-flush` | 抑制不适用的规则 |
| `--threshold minTextGap=10` | 覆盖阈值，适配自己的设计系统 |
| `--json` | 只输出 JSON，便于程序处理 |

`--help` 看全量参数。退出码：`0` 无 critical / `1` 有 critical / `2` 环境问题 —— 可直接接进 CI 或 pre-commit hook。

## 检测规则

| 规则 | 抓什么 | 级别 |
|------|--------|------|
| `flex-no-gap` | flex/grid 容器 `gap: 0`，子元素紧挨（最常见：按钮组、图标列表） | 紧挨 3 处以上为 critical |
| `text-block-too-close` | 标题/段落之间 < 6px | 0px 为 critical |
| `sibling-too-close` | 相邻块级元素之间 < 4px | warning |
| `content-flush` | 有背景/边框的容器 padding < 4px，文字贴到边框 | warning |
| `sibling-overlap` | 兄弟元素矩形重叠，可能压字 | critical |
| `floater-covers-sibling` | 绝对定位元素遮住同容器兄弟 | warning |
| `tap-targets-too-close` | 相邻可点击元素 < 8px，易误触 | warning |
| `tap-target-small` | 可点击元素 < 24px（WCAG 2.5.8） | info |
| `line-height-tight` | 多行文本行高 < 1.25× 字号 | warning |
| `edge-flush` | 文字左右都贴视口边缘 | info |

判定全部基于渲染后的 `getBoundingClientRect`，所以 margin 塌陷、flex gap、负 margin 这些只有渲染后才成立的效果都能算对。误报豁免（表格内部、内联文本流、内联元素、`overflow:hidden` 装饰、iframe/canvas 骨架布局、各自有背景的区块）已在引擎内处理，详见 `reference/rules.md`。

## 报告出来后要做什么

报告是**待办清单**，不是结论。逐条改 CSS，改完重跑，直到 `0 critical`。不要只把报告复述给用户。

- 报告里有 `直接可用:` 的 CSS 片段 —— flex-no-gap 会给出 `.toolbar { gap: 8px }` 这类可直接落地的补丁
- 聚合条目（`内有 N 处…`）指向的是**父容器**，改容器的 `gap` / 子元素统一的 `row-gap`，不要逐个挪
- `--shot` 的截图用来确认"真的挤"，而不是"算出来挤"
- 改完再跑一遍：间距修复很容易引入新问题（加了 margin 又加了 gap = 间距翻倍）

## 修复原则

1. **只用 4 或 8 的倍数**：4 / 8 / 12 / 16 / 24 / 32 / 48。出现 13px、7px、22px 就是逐处手写的痕迹。
2. **gap 管同级，padding 管容器内部，margin 只做单点微调**。三者混用是间距失控的头号原因 —— 一个父容器同时有 `gap` 和子元素 `margin` 就会翻倍。
3. **间距要能表达分组**：组内 8，组间 24。整页都是 16px 是"技术正确、结构哑巴"。
4. **文本块之间宁大勿小**：p↔p ≥ 12px，标题↔其正文 ≥ 6px，区块↔区块 ≥ 24px。
5. **别靠 `margin-top` 堆叠**：父 `padding: 16px` + 子 `margin-top: 16px` = 32px，你以为写的 16。
6. **可点击元素之间 ≥ 8px，自身 ≥ 24×24**。
7. **行高**：正文 1.5–1.7，标题 1.2–1.3。

## 写前端时的三问

代码敲完、还没跑检测器之前，先自问：

1. 每个 `display:flex` / `grid` 容器的 `gap` 写了吗？
2. 每对相邻的块，它们之间隔几像素？说不出来 = 没设计。
3. 那个带背景的卡片，文字离边框几像素？

三问过不了的地方，就是检测器会报的地方。

## 参考

| 文件 | 内容 |
|------|------|
| `reference/spacing-contract.md` | **写代码前**读：间距刻度、分组层级、组件级契约、可直接抄的骨架 |
| `reference/rules.md` | 每条规则的判据、误报豁免、手工复核方法、阈值调整建议 |
| `reference/fix-playbook.md` | 常见翻车模式 → 具体修复代码（按钮组、卡片、表单、列表、表格） |
| `examples/bad-spacing.html` | 故意做坏的样本，用于验证检测器本身有没有失灵 |
