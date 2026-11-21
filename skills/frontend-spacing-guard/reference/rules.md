# 检测规则详解

## 判定基础

全部规则基于渲染后的 `getBoundingClientRect()` 与 `getComputedStyle()`，**不读源码文本**。原因：只有渲染后才成立的效果无法从 CSS 文本推断

- margin 塌陷（`p` 之间的 16px margin 可能塌成一个 16，也可能不塌）
- flex/grid 的 `gap` 与子元素 `margin` 叠加
- `normal` 在 flex 上下文里等于 `0`，在别处等于别的值
- 负 margin、绝对定位、`transform` 造成的视觉位移

所以"源码里写了 `margin: 16px` 所以有间距"经常是错的，几何测量不会错。

## 逐条规则

### `flex-no-gap`

**判据**：容器 `display` 为 flex/grid，`row-gap` 与 `column-gap` 都为 0，且至少一对相邻子元素实测距离 < 阈值。

**为什么单列一条**：这是 AI 生成代码里出现频率最高的间距缺陷。写 `display:flex` 时手很顺，`gap` 却要另外想起来。而且它的修复点在**父容器**（加一行 `gap`），比逐个子元素加 margin 干净得多。

**报告形态**：一个容器聚合一条，附 `紧挨处 N / M 个子元素`，并给出可直接粘贴的 `.class { gap: 8px }`。

**已豁免**：含 `iframe` / `canvas` / `video` / `object` / `embed` 的相邻对 —— 这类紧贴通常是 app shell 骨架（侧栏贴内容区），不是排版失误。

### `text-block-too-close` / `sibling-too-close`

**判据**：同一父容器内相邻的两个块级子元素，实测间距小于阈值。涉及 `h1-h6/p/li/blockquote/pre/figcaption/label/dt/dd` 时用 6px，其它块级元素用 4px。

**0px 判 critical**：完全贴死是"忘调"的确定信号，不是设计选择。

**已有视觉分隔时放宽到 4px**：相邻两个元素各自都有背景色或边框时，边界由视觉承担，不靠空白 —— 分区明确的卡片网格、带背景的标签，间距 4px 是合理的。

**已豁免**：表格内部（`td`/`th`/`tr` 本来就紧）、内联元素（文本流里 `span` 紧挨是正常排版）、`display:contents`、零高度元素。

### `content-flush`

**判据**：元素有可见背景色/背景图/边框，含文本，且四边 padding 最小值 < 4px（边框宽度可抵扣）。

**为什么**：带背景的容器视觉上是一个"面"，文字贴到面的边缘会显得被裁掉。无背景的 `p` 不受此规则约束 —— 它没有边界可供贴近。

**已豁免**：尺寸 < 28×20 的元素（徽章、圆点）。

### `sibling-overlap`

**判据**：同一父容器内两个块级子元素的矩形相交面积 > 12px²。

**级别 critical**：这是"紧挨"的极端形态，文字可能直接互相压住。

_极少误报，出现即是真问题_，或是一方用了负 margin 做重叠设计。

### `floater-covers-sibling`

**判据**：`position: absolute/fixed` 的子元素，与同容器的 in-flow 兄弟矩形相交，且遮住对方 15% 以上面积。

**为什么只报 warning**：弹窗、下拉、tooltip 合法地遮住内容。报告措辞已带"若是弹窗/提示层可忽略"，由人判断。

**排除的条件**：父子关系（不在同一层）、遮住面积 < 15%（轻微擦边）。

### `tap-targets-too-close` / `tap-target-small`

**判据**：`a[href]/button/input/select/textarea/[role=button]/[role=link]/[role=tab]/[onclick]` 之间距离 < 8px；或自身宽或高 < 24px。

**依据**：WCAG 2.5.8 最小目标尺寸 24×24，以及相邻目标至少留出间距。移动端尤其要紧。

**已豁免**：正文里的长文本链接（`<a>` 内联且文字 > 30 字）；父容器已被 `flex-no-gap` 报告时不再逐个重复报。

### `line-height-tight`

**判据**：含自有文本、字号 ≥ 11px、行高为数值且 `行高/字号 < 1.25`、元素高度 > 1.6 倍字号（即确实多行）。

**为什么**：单行文本行高小一点看不出来，多行就会行贴行。行高为 `normal` 的不报（交给浏览器，通常在 1.2 左右，足够）。

### `edge-flush`

**判据**：块级元素含文本，左右两侧都距视口边缘 < 8px，且自身无左右 padding。

**只报 info**：这是提醒而非错误，全宽容器本身是合法设计。只在**两侧都贴**时才报，避免把正常的全宽 header 当成问题。

## 阈值

| 参数 | 默认 | 说明 |
|------|------|------|
| `minSiblingGap` | 4 | 块级兄弟最小间距 |
| `minTextGap` | 6 | 文本块最小间距（0 必报） |
| `minPadding` | 4 | 有背景容器的内边距下限 |
| `minTapGap` | 8 | 相邻可点击元素间距 |
| `minTapSize` | 24 | 可点击元素最小尺寸 |
| `minLineHeight` | 1.25 | 行高/字号下限 |
| `maxEdgeFlush` | 8 | 距视口边缘留白下限 |
| `overlapArea` | 12 | 判定重叠的最小面积(px²) |
| `maxIssuesPerRule` | 30 | 单规则最多报几条（防刷屏） |

覆盖方式：`--threshold minTextGap=10,minPadding=8`。

**调参建议**：不要为了"让报告变干净"而放宽阈值。如果某个阈值持续误报，多半是缺了一条豁免条件，而不是阈值不对 —— 把那个案例记下来，比调数字更有价值。

## 局限

- **Shadow DOM 内部**不检测（`querySelectorAll` 穿不透），报告 meta 里有 `shadowHosts` 计数，非 0 说明有盲区
- **iframe 内部**不检测（跨域拿不到）
- **伪元素**（`::before/::after`）不参与几何测量
- **hover / focus / 展开态**不检测 —— 需要交互才出现的元素，先用 `--wait` 或改造成静态可复现状态
- **视觉审美**不判断：间距是否好看、层级是否合适，机器只能报"数值上过紧"，判断还得靠人

## 手工复核方法

报告里某条存疑时，在浏览器控制台执行：

```js
// 看两个元素的实际距离
const a = document.querySelector('第一处选择器');
const b = document.querySelector('第二处选择器');
const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
console.log('垂直间距', rb.top - ra.bottom);
console.log('a 的 margin', getComputedStyle(a).marginBottom);
console.log('父容器 gap', getComputedStyle(a.parentElement).gap);
```

三条数字一摆，是"真挤"还是"报告算错"立刻清楚。
