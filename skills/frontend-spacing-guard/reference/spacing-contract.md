# 间距契约（写代码前读）

这份文档解决的是"为什么会忘调间距"，不是"怎么补救"。核心结论：**间距失控不是因为某个值写错了，而是因为同一段距离有多个机制在管，而你又没给它们分工。**

## 一、刻度：只用 8 的倍数，必要时用 4

| 值 | 用在哪 |
|----|--------|
| 2px | 图标与紧邻文字之间（唯一该用非 4 倍数的地方） |
| 4px | 徽章/标签内部、极紧凑的行内元素之间 |
| 8px | 同组元素之间：按钮组、列表项、图标按钮 |
| 12px | 段落之间、表单字段的 label 与 input 之间 |
| 16px | 卡片内边距、表单字段之间 |
| 24px | 区块之间（标题组 → 列表、卡片之间） |
| 32px | 页面内的主要分区之间 |
| 48px | 页面级区域（header → main） |

出现 13 / 17 / 22 / 6 这种值，说明每一处都是当场估的，没有系统。**不必追求 100% 落格，但新写的值必须落格。**

## 二、三个机制，各管一层（最重要的一条）

```
┌─ 容器 ──────────────────────┐
│  padding ← 内容与容器边界的距离  │
│  ┌──────┐   gap   ┌──────┐  │   gap ← 同级兄弟之间的距离
│  │ 子元素 │ ←────→ │ 子元素 │  │
│  └──────┘         └──────┘  │
└──────────────────────────────┘
   margin ← 只在不参与 gap 的单点场景用
```

- **`gap` 管同级兄弟**，是兄弟间距离的**唯一**来源
- **`padding` 管容器内部**，是内容与边界的距离
- **`margin` 只做单点微调**（"这个标题下面我要多留一截"），不做批量间距

同一段距离被两个机制同时管，就是间距翻倍或消失的起点：

```css
/* 错：父有 gap，子又有 margin → 实际 24px，你以为是 12 */
.list { display: flex; flex-direction: column; gap: 12px; }
.list > .item { margin-bottom: 12px; }

/* 对：只留 gap */
.list { display: flex; flex-direction: column; gap: 12px; }
.list > .item { margin: 0; }

/* 错：父 padding 16 + 首个子元素 margin-top 16 → 顶部 32px */
.card { padding: 16px; }
.card > h3:first-child { margin-top: 16px; }

/* 对：容器负责边界，子元素的首尾 margin 归零 */
.card { padding: 16px; }
.card > :first-child { margin-top: 0; }
.card > :last-child { margin-bottom: 0; }
```

## 三、间距必须表达分组

读者靠空白判断"哪些内容是一伙的"。规则：**组内距离 : 组间距离 ≈ 1 : 2.5 ~ 3**

```css
/* 哑巴：整页 16px，处处均匀，结构看不出来 */
.section { margin-bottom: 16px; }
.section h2 { margin-bottom: 16px; }
.section p { margin-bottom: 16px; }

/* 会说话：组内紧、组间松 */
.section { margin-bottom: 32px; }        /* 区块之间 32 */
.section h2 { margin-bottom: 8px; }      /* 标题与它的正文 8 */
.section p { margin-bottom: 12px; }      /* 段落之间 12 */
```

标题尤其要"靠近它管的内容"：标题上方留 32、下方留 8，读者一眼就知道下面这段归它管。上下都是 16 时，标题谁也不属于。

## 四、组件级契约

写这些组件时，直接照抄；不要每写一个就重新估。

```css
/* 按钮组 —— 忘写 gap 的头号重灾区 */
.btn-group { display: flex; gap: 8px; }

/* 卡片列表 */
.card-list { display: flex; flex-direction: column; gap: 16px; }
.card { padding: 20px 24px; border-radius: 10px; }
.card > h3 { margin: 0 0 6px; }
.card > p { margin: 0; }
.card .actions { display: flex; gap: 12px; margin-top: 16px; }

/* 表单 */
.field { display: flex; flex-direction: column; gap: 6px; }   /* label 与 input */
.form { display: flex; flex-direction: column; gap: 16px; }    /* 字段之间 */

/* 侧边导航 */
.nav { display: flex; flex-direction: column; gap: 4px; }
.nav a { padding: 8px 12px; border-radius: 6px; min-height: 32px; }

/* 图标栏 / 工具栏 */
.toolbar { display: flex; align-items: center; gap: 8px; }      /* 图标按钮之间 8 */
.icon-btn { min-width: 32px; min-height: 32px; padding: 6px; }  /* 别做 18×18 */

/* 标签行 */
.tag-row { display: flex; flex-wrap: wrap; gap: 8px; }

/* 正文排版 */
.prose { line-height: 1.65; }
.prose h2 { margin: 32px 0 8px; line-height: 1.3; }
.prose h3 { margin: 24px 0 6px; line-height: 1.35; }
.prose p  { margin: 0 0 12px; }

/* 页面主容器 —— 防止文字贴视口边 */
.page { max-width: 720px; margin: 0 auto; padding: 32px 20px 48px; }
```

## 五、三问自检（代码敲完、跑检测器之前）

1. 每个 `display:flex` / `display:grid` 容器的 `gap` 写了吗？
2. 每对相邻的块，它们之间隔几像素？说不出来 = 没设计。
3. 那个带背景/边框的容器，文字离边框几像素？

过不了的地方，`run-audit.js` 一定会报。
