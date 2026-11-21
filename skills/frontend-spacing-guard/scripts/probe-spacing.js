/**
 * probe-spacing.js —— 在真实浏览器里测量元素间距，找出"紧挨 / 贴边 / 重叠 / 拥挤"。
 *
 * 设计原则：一切基于 getBoundingClientRect 的真实几何，不猜 CSS 值。
 * 因为 margin 塌陷、flex gap、负 margin、绝对定位这些效果，只有渲染后才成立。
 *
 * 用法（由 run-audit.js 注入）：
 *   window.__auditSpacing({ minSiblingGap: 4, ... })
 *
 * 返回纯 JSON 可序列化对象，不返回 DOM 节点。
 */
(function () {
  'use strict';

  var DEFAULTS = {
    minSiblingGap: 4,      // 相邻块级兄弟元素的最小视觉间距
    minTextGap: 6,         // 文本块（标题/段落）之间的最小间距；0 视为贴死，必报
    minPadding: 4,         // 有背景/边框的容器，内容到边缘的最小内边距
    minTapGap: 8,          // 相邻交互元素之间的最小间距
    minTapSize: 24,        // 交互元素自身最小尺寸（WCAG 2.5.8）
    minLineHeight: 1.25,   // 多行文本行高下限（与 font-size 的比值）
    maxEdgeFlush: 8,       // 文本容器距视口边缘的最小留白
    overlapArea: 12,       // 判定"重叠"的最小相交面积(px²)
    maxIssuesPerRule: 30
  };

  // 独占一行的块级显示类型 —— 只有它们参与垂直/水平的"兄弟间距"判断
  var BLOCKISH = {
    'block': 1, 'flex': 1, 'grid': 1, 'list-item': 1, 'flow-root': 1,
    'table': 1, 'table-caption': 1, 'inline-block': 0
  };

  // 不参与兄弟间距判断的 display（内联元素紧挨是正常文本流）
  var SKIP_DISPLAY = {
    'inline': 1, 'inline-flex': 1, 'inline-grid': 1, 'none': 1, 'contents': 1,
    'table-row': 1, 'table-cell': 1, 'table-row-group': 1, 'table-header-group': 1,
    'table-footer-group': 1, 'table-column': 1, 'table-column-group': 1
  };

  var TEXT_TAGS = {
    h1: 1, h2: 1, h3: 1, h4: 1, h5: 1, h6: 1, p: 1, li: 1, blockquote: 1,
    pre: 1, figcaption: 1, label: 1, dt: 1, dd: 1, caption: 1, legend: 1
  };

  var IGNORE_TAGS = {
    script: 1, style: 1, link: 1, meta: 1, head: 1, title: 1, noscript: 1,
    br: 1, hr: 1, option: 1, optgroup: 1, source: 1, track: 1, template: 1,
    svg: 0 // svg 自身要算，但内部 path 之类不该报
  };

  function px(v) {
    var n = parseFloat(v);
    return isNaN(n) ? 0 : n;
  }

  function num(v, fallback) {
    var n = parseFloat(v);
    return isNaN(n) ? fallback : n;
  }

  function style(el, cache) {
    var s = cache.get(el);
    if (!s) {
      s = window.getComputedStyle(el);
      cache.set(el, s);
    }
    return s;
  }

  function isVisible(el, cache) {
    var s = style(el, cache);
    if (s.display === 'none' || s.visibility === 'hidden' || s.visibility === 'collapse') return false;
    if (px(s.opacity) === 0 && s.opacity !== '') return false;
    if (s.clipPath === 'inset(50%)' || s.clip === 'rect(0px, 0px, 0px, 0px)') return false; // 视觉隐藏
    var r = el.getBoundingClientRect();
    return r.width > 0.5 && r.height > 0.5;
  }

  function isOutOfFlow(el, cache) {
    var p = style(el, cache).position;
    return p === 'absolute' || p === 'fixed';
  }

  function insideTable(el) {
    var cur = el;
    while (cur && cur.nodeType === 1) {
      var t = cur.tagName;
      if (t === 'TABLE' || t === 'THEAD' || t === 'TBODY' || t === 'TR' || t === 'TD' || t === 'TH') return true;
      cur = cur.parentElement;
    }
    return false;
  }

  function hasOwnText(el) {
    for (var i = 0; i < el.childNodes.length; i++) {
      var n = el.childNodes[i];
      if (n.nodeType === 3 && n.nodeValue && n.nodeValue.trim()) return true;
    }
    return false;
  }

  function textLen(el) {
    var t = el.textContent || '';
    return t.replace(/\s+/g, ' ').trim().length;
  }

  function hasBg(s) {
    var bg = s.backgroundColor || '';
    if (bg && bg !== 'transparent' && bg !== 'rgba(0, 0, 0, 0)') return true;
    return !!(s.backgroundImage && s.backgroundImage !== 'none');
  }

  function hasBorder(s) {
    return px(s.borderTopWidth) > 0 || px(s.borderRightWidth) > 0 ||
      px(s.borderBottomWidth) > 0 || px(s.borderLeftWidth) > 0;
  }

  function cssPath(el) {
    var parts = [];
    var cur = el;
    var guard = 0;
    while (cur && cur.nodeType === 1 && guard < 8) {
      guard++;
      var tag = cur.tagName.toLowerCase();
      if (tag === 'body' || tag === 'html') break; // 从 body 的直接子元素开始，路径更短
      var sel = tag;
      if (cur.id) {
        parts.unshift('#' + cur.id);
        break;
      }
      var cn = (typeof cur.className === 'string' ? cur.className : '').trim();
      if (cn) {
        var cls = cn.split(/\s+/).filter(function (c) {
          return c && !/^(ng-|css-|sc-|jsx-)/.test(c);
        }).slice(0, 2);
        if (cls.length) sel += '.' + cls.join('.');
      }
      var parent = cur.parentElement;
      if (parent) {
        var same = [];
        for (var i = 0; i < parent.children.length; i++) {
          if (parent.children[i].tagName === cur.tagName) same.push(parent.children[i]);
        }
        if (same.length > 1) sel += ':nth-of-type(' + (same.indexOf(cur) + 1) + ')';
      }
      parts.unshift(sel);
      cur = cur.parentElement;
    }
    return parts.join(' > ');
  }

  /** 人类可读的名字：button「提交」 或 div.card */
  function human(el) {
    var tag = el.tagName.toLowerCase();
    var t = (el.textContent || '').replace(/\s+/g, ' ').trim();
    if (t) {
      t = t.length > 18 ? t.slice(0, 18) + '…' : t;
      return tag + '「' + t + '」';
    }
    var cn = (typeof el.className === 'string' ? el.className : '').trim();
    if (cn) {
      var first = cn.split(/\s+/)[0];
      if (first && !/^(ng-|css-|sc-)/.test(first)) return tag + '.' + first;
    }
    if (el.id) return tag + '#' + el.id;
    return tag;
  }

  function rectOf(el) {
    var r = el.getBoundingClientRect();
    return {
      x: Math.round(r.left * 10) / 10,
      y: Math.round(r.top * 10) / 10,
      w: Math.round(r.width * 10) / 10,
      h: Math.round(r.height * 10) / 10
    };
  }

  /**
   * 判断 A、B 两元素的相对位置，返回间距。
   * 返回 null 表示不构成"相邻"关系（重叠或位置错乱），需交给重叠检测。
   */
  function distance(a, b) {
    // 垂直方向完全分离
    if (b.top >= a.bottom - 0.5) return { axis: 'v', d: b.top - a.bottom };
    if (a.top >= b.bottom - 0.5) return { axis: 'v', d: a.top - b.bottom };
    // 水平方向完全分离
    if (b.left >= a.right - 0.5) return { axis: 'h', d: b.left - a.right };
    if (a.left >= b.right - 0.5) return { axis: 'h', d: a.left - b.right };
    return null;
  }

  function overlapArea(a, b) {
    var w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
    var h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    if (w <= 0 || h <= 0) return 0;
    return w * h;
  }

  function totalGap(s) {
    // flex/grid 的 gap；'normal' 对 flex/grid 等价于 0
    var rg = s.rowGap === 'normal' ? 0 : px(s.rowGap);
    var cg = s.columnGap === 'normal' ? 0 : px(s.columnGap);
    return { row: rg, col: cg };
  }

  var EMBED_TAGS = { iframe: 1, canvas: 1, video: 1, object: 1, embed: 1 };

  /** 自身或内部含嵌入式媒体（iframe/canvas…），这类紧贴通常是 app shell 结构需要 */
  function isEmbedded(el) {
    if (EMBED_TAGS[el.tagName.toLowerCase()] === 1) return true;
    return !!el.querySelector('iframe, canvas, video, object, embed');
  }

  function audit(cfg) {
    var C = {};
    for (var k in DEFAULTS) {
      C[k] = (cfg && cfg[k] !== undefined) ? cfg[k] : DEFAULTS[k];
    }

    var cache = new Map();
    var issues = [];
    var seen = new Set();
    var perRule = {};
    var noGapParents = new Set(); // 已报为"flex 容器忘写 gap"的父容器

    function push(issue) {
      // 相邻关系是无向的，排序后做 key，避免 (A,B) 与 (B,A) 各报一条
      var pair = [issue.selector || '', issue.relatedSelector || ''].sort().join('|');
      var key = issue.rule + '|' + pair;
      if (seen.has(key)) return;
      seen.add(key);
      perRule[issue.rule] = (perRule[issue.rule] || 0) + 1;
      if (perRule[issue.rule] > C.maxIssuesPerRule) return;
      issues.push(issue);
    }

    var all = document.querySelectorAll('body *');
    var shadowHosts = 0;

    // ---------- 规则 1 & 2：兄弟元素间距 / flex-grid 忘写 gap ----------
    for (var i = 0; i < all.length; i++) {
      var parent = all[i];
      var tag = parent.tagName.toLowerCase();
      if (IGNORE_TAGS[tag] === 1) continue;
      if (parent.shadowRoot) { shadowHosts++; }
      if (!isVisible(parent, cache)) continue;
      if (insideTable(parent)) continue;

      var kids = [];
      for (var j = 0; j < parent.children.length; j++) {
        var kid = parent.children[j];
        var ktag = kid.tagName.toLowerCase();
        if (IGNORE_TAGS[ktag] === 1) continue;
        if (ktag === 'svg' || (kid.closest && kid.closest('svg') && kid.tagName.toLowerCase() !== 'svg')) {
          // svg 内部图元不参与
          if (ktag !== 'svg') continue;
        }
        var ks = style(kid, cache);
        if (SKIP_DISPLAY[ks.display] === 1) continue;
        if (ks.display === 'inline') continue;
        if (!isVisible(kid, cache)) continue;
        if (isOutOfFlow(kid, cache)) continue;
        kids.push(kid);
      }
      // ---- 规则 1b：绝对/固定定位元素压住同容器兄弟（浮层盖字）----
      var floatKids = [];
      var flowKids = [];
      for (var fj = 0; fj < parent.children.length; fj++) {
        var fc = parent.children[fj];
        if (IGNORE_TAGS[fc.tagName.toLowerCase()] === 1) continue;
        if (!isVisible(fc, cache)) continue;
        if (isOutOfFlow(fc, cache)) floatKids.push(fc);
        else flowKids.push(fc);
      }
      if (floatKids.length && flowKids.length) {
        for (var fi = 0; fi < floatKids.length; fi++) {
          var fEl = floatKids[fi];
          var fr = fEl.getBoundingClientRect();
          for (var mi = 0; mi < flowKids.length; mi++) {
            var mEl = flowKids[mi];
            var mr = mEl.getBoundingClientRect();
            var cov = overlapArea(fr, mr);
            if (cov < C.overlapArea) continue;
            var coverRatio = cov / Math.min(fr.width * fr.height, mr.width * mr.height);
            if (coverRatio < 0.15) continue; // 轻微擦碰不报
            push({
              rule: 'floater-covers-sibling',
              severity: 'warning',
              selector: cssPath(fEl),
              relatedSelector: cssPath(mEl),
              label: human(fEl) + ' ⟶ ' + human(mEl),
              measured: Math.round(coverRatio * 100),
              expected: 0,
              unit: '%',
              message: human(fEl) + '（' + style(fEl, cache).position + ' 定位）压住了同容器内的 ' +
                human(mEl) + '，遮住它 ' + Math.round(coverRatio * 100) + '% 的面积',
              hint: '若是弹窗/提示层可忽略；否则说明浮层没留出空间，检查 top/left 偏移或改回正常文档流'
            });
          }
        }
      }

      if (kids.length < 2) continue;

      var ps = style(parent, cache);
      var isFlexGrid = /flex|grid/.test(ps.display);
      var g = totalGap(ps);
      var gapMissing = isFlexGrid && g.row <= 0 && g.col <= 0;
      var tightPairs = [];

      for (var m = 0; m < kids.length - 1; m++) {
        var A = kids[m];
        var B = kids[m + 1];
        var ra = A.getBoundingClientRect();
        var rb = B.getBoundingClientRect();

        // iframe / canvas 这类嵌入式内容周边紧贴，多半是骨架布局，不当成间距问题
        if (isEmbedded(A) || isEmbedded(B)) continue;

        var ov = overlapArea(ra, rb);
        if (ov > C.overlapArea) {
          push({
            rule: 'sibling-overlap',
            severity: 'critical',
            selector: cssPath(A),
            relatedSelector: cssPath(B),
            label: human(A) + ' ⨯ ' + human(B),
            measured: Math.round(ov),
            expected: 0,
            unit: 'px²',
            message: '两个元素发生重叠（相交 ' + Math.round(ov) + 'px²），内容可能被遮挡或压字',
            hint: '检查这两个元素的 position / 绝对定位 / 负 margin，或给父容器加 gap 让它们自然排开'
          });
          continue;
        }

        var dist = distance(ra, rb);
        if (!dist) continue;
        if (dist.d < -0.5) continue;

        var isTextPair = TEXT_TAGS[A.tagName.toLowerCase()] === 1 || TEXT_TAGS[B.tagName.toLowerCase()] === 1;
        // 两个元素各自已有背景或边框时，边界由视觉分隔承担，不靠空白，可以贴得更近
        var sa = style(A, cache);
        var sb = style(B, cache);
        var selfSeparated = (hasBg(sa) || hasBorder(sa)) && (hasBg(sb) || hasBorder(sb));
        var limit = (isTextPair && !selfSeparated) ? C.minTextGap : C.minSiblingGap;
        if (dist.d >= limit) continue;

        tightPairs.push({
          a: A, b: B, d: dist.d, axis: dist.axis, limit: limit, text: isTextPair
        });
      }

      if (!tightPairs.length) continue;

      if (gapMissing) {
        // 根因在父容器：一次性聚合报告，指明"是这个容器忘了写 gap"
        var worst = tightPairs.reduce(function (x, y) { return y.d < x.d ? y : x; });
        var suggestGap = worst.text ? 12 : 8; // 给能直接落地的值，而不是刚好卡在阈值上
        var samples = tightPairs.slice(0, 4).map(function (p) {
          return human(p.a) + ' / ' + human(p.b) + ' ' + Math.round(p.d * 10) / 10 + 'px';
        });
        noGapParents.add(parent);
        push({
          rule: 'flex-no-gap',
          severity: tightPairs.length > 2 ? 'critical' : 'warning',
          selector: cssPath(parent),
          label: human(parent),
          measured: Math.round(worst.d * 10) / 10,
          expected: suggestGap,
          unit: 'px',
          childCount: kids.length,
          tightPairs: tightPairs.length,
          message: parent.tagName.toLowerCase() + ' 用了 ' + ps.display + ' 布局，但 gap 为 0，' +
            kids.length + ' 个子元素中有 ' + tightPairs.length + ' 处紧挨（最小 ' +
            (Math.round(worst.d * 10) / 10) + 'px）：' + samples.join('；'),
          hint: '给这个容器加 gap（如 gap: 8px / 12px），并移除子元素上多余的 margin'
        });
      } else {
        // 同一父容器内的同类问题聚合成一条，避免一个导航列表刷出十几条
        var byRule = {};
        tightPairs.forEach(function (p) {
          var rn = p.text ? 'text-block-too-close' : 'sibling-too-close';
          (byRule[rn] = byRule[rn] || []).push(p);
        });
        Object.keys(byRule).forEach(function (rn) {
          var list = byRule[rn];
          var worstP = list.reduce(function (x, y) { return y.d < x.d ? y : x; });
          var wd = Math.round(worstP.d * 10) / 10;
          var sev = worstP.d <= 0 ? 'critical' : 'warning';

          if (list.length === 1) {
            var p0 = list[0];
            push({
              rule: rn,
              severity: sev,
              selector: cssPath(p0.a),
              relatedSelector: cssPath(p0.b),
              label: human(p0.a) + ' / ' + human(p0.b),
              measured: wd,
              expected: p0.limit,
              unit: 'px',
              axis: p0.axis,
              message: human(p0.a) + ' 与 ' + human(p0.b) + ' 的' + (p0.axis === 'v' ? '垂直' : '水平') +
                '间距只有 ' + wd + 'px（建议 ≥ ' + p0.limit + 'px）',
              hint: p0.axis === 'v'
                ? '给后者加 margin-top: ' + p0.limit + 'px，或给父容器加 row-gap: ' + p0.limit + 'px'
                : '给后者加 margin-left: ' + p0.limit + 'px，或给父容器加 column-gap: ' + p0.limit + 'px'
            });
            return;
          }

          var samples = list.slice(0, 3).map(function (p) {
            return human(p.a) + ' / ' + human(p.b) + ' ' + (Math.round(p.d * 10) / 10) + 'px';
          });
          var suggest = worstP.text ? 8 : 4;
          push({
            rule: rn,
            severity: sev,
            selector: cssPath(parent),
            label: human(parent),
            measured: wd,
            expected: worstP.limit,
            unit: 'px',
            count: list.length,
            message: human(parent) + ' 内有 ' + list.length + ' 处' +
              (rn === 'text-block-too-close' ? '文本' : '元素') + '间距过小（最小 ' + wd + 'px）：' +
              samples.join('；') + (list.length > 3 ? ' 等' : ''),
            hint: worstP.axis === 'v'
              ? '给这些子元素统一加 row-gap: ' + suggest + 'px 以上，或把容器改成 flex + gap'
              : '给这些子元素统一加 column-gap: ' + suggest + 'px 以上，或把容器改成 flex + gap'
          });
        });
      }
    }

    // ---------- 规则 3：内容贴容器边缘（padding 不足） ----------
    for (var n = 0; n < all.length; n++) {
      var box = all[n];
      var btag = box.tagName.toLowerCase();
      if (btag === 'body' || btag === 'html' || IGNORE_TAGS[btag] === 1) continue;
      if (!isVisible(box, cache)) continue;
      if (insideTable(box)) continue;
      var bs = style(box, cache);
      var decorated = hasBg(bs) || hasBorder(bs);
      if (!decorated) continue;
      if (textLen(box) < 2) continue;

      var br = box.getBoundingClientRect();
      if (br.width < 28 || br.height < 20) continue; // 徽章/标签之类不算

      var pads = [px(bs.paddingTop), px(bs.paddingRight), px(bs.paddingBottom), px(bs.paddingLeft)];
      var minPad = Math.min.apply(null, pads);
      if (minPad >= C.minPadding) continue;

      // 边框宽度可以提供视觉呼吸，扣除
      var borderMin = Math.min(px(bs.borderTopWidth), px(bs.borderRightWidth), px(bs.borderBottomWidth), px(bs.borderLeftWidth));
      if (minPad + borderMin >= C.minPadding) continue;

      var edges = ['top', 'right', 'bottom', 'left'];
      var worstEdge = edges[pads.indexOf(minPad)];
      push({
        rule: 'content-flush',
        severity: 'warning',
        selector: cssPath(box),
        label: human(box),
        measured: minPad,
        expected: C.minPadding,
        unit: 'px',
        message: human(box) + ' 有背景/边框，但 ' + worstEdge + ' 内边距只有 ' + minPad + 'px，文字贴着边框',
        hint: '给该容器加 padding，例如 padding: ' + (C.minPadding * 2) + 'px ' + (C.minPadding * 3) + 'px'
      });
    }

    // ---------- 规则 4：交互元素间距 / 尺寸 ----------
    var interactive = document.querySelectorAll(
      'a[href], button, input:not([type=hidden]), select, textarea, [role=button], [role=link], [role=tab], [onclick]'
    );
    var taps = [];
    for (var q = 0; q < interactive.length; q++) {
      var t = interactive[q];
      if (!isVisible(t, cache)) continue;
      var td = style(t, cache);
      if (td.display === 'inline' && t.tagName === 'A' && (t.textContent || '').trim().length > 30) {
        // 正文里的长链接不算点击目标
        continue;
      }
      taps.push(t);
    }

    var smallTaps = new Map();
    for (var r = 0; r < taps.length; r++) {
      var el = taps[r];
      var rr = el.getBoundingClientRect();
      if (rr.width < C.minTapSize || rr.height < C.minTapSize) {
        var tapParent = el.parentElement || document.body;
        if (!smallTaps.has(tapParent)) smallTaps.set(tapParent, []);
        smallTaps.get(tapParent).push({ el: el, w: rr.width, h: rr.height });
      }

      // 与同容器内其他交互元素的间距
      var pEl = el.parentElement;
      if (!pEl) continue;
      // 父容器已经报过"flex 忘写 gap"，这里不再重复报同一批按钮
      if (noGapParents.has(pEl)) continue;
      for (var s2 = 0; s2 < pEl.children.length; s2++) {
        var other = pEl.children[s2];
        if (other === el) continue;
        if (other.contains(el) || el.contains(other)) continue;
        if (taps.indexOf(other) === -1) continue;
        if (!isVisible(other, cache)) continue;
        if (isOutOfFlow(other, cache) || isOutOfFlow(el, cache)) continue;
        var d2 = distance(rr, other.getBoundingClientRect());
        if (!d2) continue;
        if (d2.d >= 0 && d2.d < C.minTapGap) {
          push({
            rule: 'tap-targets-too-close',
            severity: 'warning',
            selector: cssPath(el),
            relatedSelector: cssPath(other),
            label: human(el) + ' / ' + human(other),
            measured: Math.round(d2.d * 10) / 10,
            expected: C.minTapGap,
            unit: 'px',
            message: '两个可点击元素的' + (d2.axis === 'v' ? '垂直' : '水平') + '间距只有 ' +
              (Math.round(d2.d * 10) / 10) + 'px，容易误触',
            hint: '给父容器加 gap: ' + C.minTapGap + 'px 以上，或加大按钮间 margin'
          });
        }
      }
    }

    // 过小的点击目标按容器聚合，避免一张页面上二十个图标刷出二十条
    smallTaps.forEach(function (list, parentEl) {
      var minSide = Math.round(Math.min.apply(null, list.map(function (o) {
        return Math.min(o.w, o.h);
      })));
      var first = list[0];
      push({
        rule: 'tap-target-small',
        severity: 'info',
        selector: list.length === 1 ? cssPath(first.el) : cssPath(parentEl),
        label: list.length === 1 ? human(first.el) : human(parentEl) + ' 内 ' + list.length + ' 个',
        measured: minSide,
        expected: C.minTapSize,
        unit: 'px',
        count: list.length,
        message: list.length === 1
          ? human(first.el) + ' 尺寸 ' + Math.round(first.w) + '×' + Math.round(first.h) +
            '，小于可点击下限 ' + C.minTapSize + 'px'
          : human(parentEl) + ' 内有 ' + list.length + ' 个可点击元素小于 ' + C.minTapSize +
            'px（最小 ' + minSide + 'px）',
        hint: '给这些元素加 min-width/min-height: ' + C.minTapSize + 'px，或用 padding 撑开点击区域'
      });
    });

    // ---------- 规则 5：行高过紧 ----------
    for (var u = 0; u < all.length; u++) {
      var tp = all[u];
      var ttag = tp.tagName.toLowerCase();
      if (IGNORE_TAGS[ttag] === 1) continue;
      if (!isVisible(tp, cache)) continue;
      if (!hasOwnText(tp)) continue;
      if (textLen(tp) < 12) continue;
      var tps = style(tp, cache);
      var fs = px(tps.fontSize);
      if (fs < 11) continue;
      if (tps.lineHeight === 'normal' || !tps.lineHeight) continue;
      var lh = px(tps.lineHeight);
      if (!lh) continue;
      var ratio = lh / fs;
      if (ratio >= C.minLineHeight) continue;
      var rr2 = tp.getBoundingClientRect();
      // 只关心多行文本
      if (rr2.height < fs * 1.6) continue;
      push({
        rule: 'line-height-tight',
        severity: 'warning',
        selector: cssPath(tp),
        label: human(tp),
        measured: Math.round(ratio * 100) / 100,
        expected: C.minLineHeight,
        unit: '×',
        message: '多行文本行高只有 ' + (Math.round(ratio * 100) / 100) + '×字号（' + lh + 'px / ' + fs + 'px），行与行挤在一起',
        hint: '设 line-height: ' + C.minLineHeight + ' 或更高（正文 1.5~1.7 更好）'
      });
    }

    // ---------- 规则 6：内容贴视口边缘 ----------
    var vw = window.innerWidth;
    for (var v = 0; v < all.length; v++) {
      var ep = all[v];
      var etag = ep.tagName.toLowerCase();
      if (IGNORE_TAGS[etag] === 1) continue;
      if (!isVisible(ep, cache)) continue;
      if (!hasOwnText(ep) || textLen(ep) < 8) continue;
      var eps = style(ep, cache);
      if (eps.position === 'fixed') continue;
      var epads = [px(eps.paddingRight), px(eps.paddingLeft)];
      if (Math.min.apply(null, epads) >= C.maxEdgeFlush) continue;
      var er = ep.getBoundingClientRect();
      var leftFlush = er.left < C.maxEdgeFlush;
      var rightFlush = (vw - er.right) < C.maxEdgeFlush;
      if (!leftFlush && !rightFlush) continue;
      // 全宽容器（如 header/body 内直接子元素）通常是设计意图，只在两侧都贴时提醒
      if (!(leftFlush && rightFlush)) continue;
      push({
        rule: 'edge-flush',
        severity: 'info',
        selector: cssPath(ep),
        label: human(ep),
        measured: Math.round(er.left * 10) / 10,
        expected: C.maxEdgeFlush,
        unit: 'px',
        message: human(ep) + ' 的文字左右都贴到视口边缘（左边距 ' + Math.round(er.left) +
          'px / 右边距 ' + Math.round(vw - er.right) + 'px）',
        hint: '给页面主容器加 padding: 0 16px，或 max-width + margin: 0 auto'
      });
    }

    // ---------- 汇总 ----------
    var order = { critical: 0, warning: 1, info: 2 };
    issues.sort(function (x, y) {
      if (order[x.severity] !== order[y.severity]) return order[x.severity] - order[y.severity];
      if (x.rule !== y.rule) return x.rule < y.rule ? -1 : 1;
      return (x.measured || 0) - (y.measured || 0);
    });

    var counts = { critical: 0, warning: 0, info: 0 };
    issues.forEach(function (it) { counts[it.severity]++; });

    // 间距尺度采样：帮助发现"到处是 13px 这种随手值"
    var spacingValues = {};
    [].forEach.call(document.querySelectorAll('body *'), function (e2) {
      var s3 = style(e2, cache);
      if (!isVisible(e2, cache)) return;
      var vals = [s3.paddingTop, s3.paddingBottom, s3.paddingLeft, s3.paddingRight,
        s3.marginTop, s3.marginBottom, s3.marginLeft, s3.marginRight];
      if (/flex|grid/.test(s3.display)) {
        if (s3.rowGap !== 'normal') vals.push(s3.rowGap);
        if (s3.columnGap !== 'normal') vals.push(s3.columnGap);
      }
      vals.forEach(function (raw) {
        var n = px(raw);
        if (n > 0 && n < 200) {
          var key = String(Math.round(n * 10) / 10);
          spacingValues[key] = (spacingValues[key] || 0) + 1;
        }
      });
    });
    var topSpacing = Object.keys(spacingValues)
      .map(function (k2) { return [parseFloat(k2), spacingValues[k2]]; })
      .sort(function (a2, b2) { return b2[1] - a2[1]; })
      .slice(0, 12);

    var score = 100 - counts.critical * 8 - counts.warning * 3 - counts.info * 1;
    if (score < 0) score = 0;

    return {
      meta: {
        url: location.href,
        viewport: { w: window.innerWidth, h: window.innerHeight },
        elementCount: all.length,
        shadowHosts: shadowHosts,
        thresholds: C,
        generatedAt: new Date().toISOString()
      },
      summary: {
        score: score,
        verdict: counts.critical > 0 ? 'fail' : (counts.warning > 0 ? 'needs-work' : 'pass'),
        counts: counts,
        total: issues.length
      },
      topSpacingValues: topSpacing,
      issues: issues
    };
  }

  window.__auditSpacing = audit;
})();
