/*
 * 图片拼接核心布局计算（纯函数，可在 node 中测试，不依赖 DOM/Canvas）
 *
 * 设计目标：
 *  - computeLayout 只算坐标与画布尺寸，不碰 Canvas，便于单元测试；
 *  - 渲染层（页面）拿到布局后自行 drawImage。
 */
(function (global) {
  'use strict';

  // 根据缩放策略计算单张图渲染后的尺寸
  // scale: 'none' | 'fit-width' | 'fit-height'
  // base:  fit-width 时的目标宽度 / fit-height 时的目标高度
  function effectiveSize(img, scale, base) {
    const w = img.width || 0;
    const h = img.height || 0;
    if (scale === 'fit-width' && w > 0) {
      const r = base / w;
      return { width: Math.round(base), height: Math.round(h * r) };
    }
    if (scale === 'fit-height' && h > 0) {
      const r = base / h;
      return { width: Math.round(w * r), height: Math.round(base) };
    }
    return { width: w, height: h };
  }

  // 交叉轴方向的对齐偏移：track 为轨道尺寸，size 为元素尺寸
  // align: 'start' | 'center' | 'end'
  function crossOffset(track, size, align) {
    if (align === 'end') return track - size;
    if (align === 'center') return (track - size) / 2;
    return 0; // start
  }

  /*
   * 计算拼接布局
   * @param {Array<{width:number,height:number}>} images 每张图的（旋转/原始）尺寸
   * @param {object} opts
   *   mode:    'horizontal' | 'vertical' | 'grid'
   *   columns: grid 模式的列数（>=1）
   *   gap:     图片间留白（px）
   *   scale:   'none' | 'fit-width' | 'fit-height'
   *   base:    scale 非 none 时的基准尺寸（px）
   *   align:   'start' | 'center' | 'end'
   * @returns {{canvasWidth:number, canvasHeight:number,
   *            items: Array<{index:number,x:number,y:number,w:number,h:number}>}}
   */
  function computeLayout(images, opts) {
    opts = opts || {};
    const mode = opts.mode || 'horizontal';
    const gap = opts.gap || 0;
    const scale = opts.scale || 'none';
    const base = opts.base || 0;
    const align = opts.align || 'start';
    const columns = Math.max(1, opts.columns || 1);

    const sizes = (images || []).map(function (img) {
      return effectiveSize(img, scale, base);
    });

    let canvasWidth = 0;
    let canvasHeight = 0;
    const items = [];

    if (mode === 'vertical') {
      const colW = sizes.reduce(function (m, s) { return Math.max(m, s.width); }, 0);
      let y = 0;
      for (let i = 0; i < sizes.length; i++) {
        const s = sizes[i];
        const x = crossOffset(colW, s.width, align);
        items.push({ index: i, x: Math.round(x), y: Math.round(y), w: s.width, h: s.height });
        y += s.height + gap;
      }
      canvasWidth = colW;
      canvasHeight = Math.max(0, y - gap);
    } else if (mode === 'grid') {
      const n = sizes.length;
      const rows = Math.ceil(n / columns);
      const colW = [];
      for (let c = 0; c < columns; c++) {
        let mx = 0;
        for (let r = 0; r < rows; r++) {
          const idx = r * columns + c;
          if (idx < n) mx = Math.max(mx, sizes[idx].width);
        }
        colW.push(mx);
      }
      const rowH = [];
      for (let r = 0; r < rows; r++) {
        let mx = 0;
        for (let c = 0; c < columns; c++) {
          const idx = r * columns + c;
          if (idx < n) mx = Math.max(mx, sizes[idx].height);
        }
        rowH.push(mx);
      }
      const colX = [];
      let cx = 0;
      for (let c = 0; c < columns; c++) { colX.push(cx); cx += colW[c] + gap; }
      const rowY = [];
      let ry = 0;
      for (let r = 0; r < rows; r++) { rowY.push(ry); ry += rowH[r] + gap; }
      for (let i = 0; i < n; i++) {
        const r = Math.floor(i / columns);
        const c = i % columns;
        const s = sizes[i];
        const x = colX[c] + crossOffset(colW[c], s.width, align);
        const y = rowY[r] + crossOffset(rowH[r], s.height, align);
        items.push({ index: i, x: Math.round(x), y: Math.round(y), w: s.width, h: s.height });
      }
      canvasWidth = Math.max(0, cx - gap);
      canvasHeight = Math.max(0, ry - gap);
    } else { // horizontal（默认）
      const rowH = sizes.reduce(function (m, s) { return Math.max(m, s.height); }, 0);
      let x = 0;
      for (let i = 0; i < sizes.length; i++) {
        const s = sizes[i];
        const y = crossOffset(rowH, s.height, align);
        items.push({ index: i, x: Math.round(x), y: Math.round(y), w: s.width, h: s.height });
        x += s.width + gap;
      }
      canvasWidth = Math.max(0, x - gap);
      canvasHeight = rowH;
    }

    return {
      canvasWidth: Math.round(canvasWidth),
      canvasHeight: Math.round(canvasHeight),
      items: items
    };
  }

  const api = { effectiveSize: effectiveSize, computeLayout: computeLayout };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    global.ImageStitchCore = api;
  }
})(typeof window !== 'undefined' ? window : this);
