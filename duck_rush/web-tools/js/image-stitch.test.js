/*
 * image-stitch 纯函数测试（node 直接运行，无需浏览器/Canvas）
 * 运行: node duck_rush/web-tools/js/image-stitch.test.js
 */
const assert = require('assert');
const { computeLayout, effectiveSize } = require('./image-stitch-core.js');

let passed = 0;
function test(name, fn) {
  fn();
  passed++;
  console.log('  \u2713 ' + name);
}

// ── effectiveSize ──
test('effectiveSize none 保持原尺寸', function () {
  assert.deepStrictEqual(effectiveSize({ width: 100, height: 50 }, 'none', 0), { width: 100, height: 50 });
});
test('effectiveSize fit-width 按比例缩放宽度', function () {
  const s = effectiveSize({ width: 200, height: 100 }, 'fit-width', 400);
  assert.strictEqual(s.width, 400);
  assert.strictEqual(s.height, 200);
});
test('effectiveSize fit-height 按比例缩放高度', function () {
  const s = effectiveSize({ width: 200, height: 100 }, 'fit-height', 50);
  assert.strictEqual(s.width, 100);
  assert.strictEqual(s.height, 50);
});

// ── horizontal ──
test('horizontal 累计宽度并计入间距', function () {
  const r = computeLayout(
    [{ width: 100, height: 50 }, { width: 100, height: 80 }],
    { mode: 'horizontal', gap: 10, align: 'start' }
  );
  assert.strictEqual(r.canvasWidth, 210);
  assert.strictEqual(r.canvasHeight, 80);
  assert.strictEqual(r.items[0].x, 0);
  assert.strictEqual(r.items[1].x, 110);
});
test('horizontal align center 垂直居中', function () {
  const r = computeLayout(
    [{ width: 100, height: 50 }, { width: 100, height: 80 }],
    { mode: 'horizontal', gap: 0, align: 'center' }
  );
  // 行高 80，第一张高 50 -> y = 15
  assert.strictEqual(r.items[0].y, 15);
  assert.strictEqual(r.items[1].y, 0);
});
test('horizontal 空列表画布为 0', function () {
  const r = computeLayout([], { mode: 'horizontal' });
  assert.strictEqual(r.canvasWidth, 0);
  assert.strictEqual(r.canvasHeight, 0);
  assert.strictEqual(r.items.length, 0);
});

// ── vertical ──
test('vertical 累计高度并计入间距', function () {
  const r = computeLayout(
    [{ width: 100, height: 50 }, { width: 200, height: 50 }],
    { mode: 'vertical', gap: 10, align: 'start' }
  );
  assert.strictEqual(r.canvasWidth, 200);
  assert.strictEqual(r.canvasHeight, 110);
  assert.strictEqual(r.items[1].y, 60);
});
test('vertical align end 右对齐较窄图', function () {
  const r = computeLayout(
    [{ width: 100, height: 50 }, { width: 200, height: 50 }],
    { mode: 'vertical', gap: 0, align: 'end' }
  );
  assert.strictEqual(r.items[0].x, 100); // 列宽 200 - 宽 100
  assert.strictEqual(r.items[1].x, 0);
});

// ── grid ──
test('grid 2 列规整布局', function () {
  const imgs = [{ width: 100, height: 100 }, { width: 100, height: 100 }, { width: 100, height: 100 }];
  const r = computeLayout(imgs, { mode: 'grid', columns: 2, gap: 10, align: 'center' });
  assert.strictEqual(r.canvasWidth, 210);
  assert.strictEqual(r.canvasHeight, 210);
  assert.deepStrictEqual([r.items[0].x, r.items[0].y], [0, 0]);
  assert.deepStrictEqual([r.items[1].x, r.items[1].y], [110, 0]);
  assert.deepStrictEqual([r.items[2].x, r.items[2].y], [0, 110]);
});
test('grid 不等尺寸按行列最大值对齐', function () {
  const imgs = [{ width: 100, height: 200 }, { width: 300, height: 50 }, { width: 50, height: 50 }];
  const r = computeLayout(imgs, { mode: 'grid', columns: 2, gap: 0, align: 'start' });
  // 列宽: c0 max(100,50)=100; c1 max(300)=300 -> 400
  // 行高: r0 max(200,50)=200; r1 max(50)=50 -> 250
  assert.strictEqual(r.canvasWidth, 400);
  assert.strictEqual(r.canvasHeight, 250);
  assert.deepStrictEqual([r.items[1].x, r.items[1].y], [100, 0]); // 第2张在 c1, x=100
});
test('grid 列数大于图片数时退化为单列行', function () {
  const r = computeLayout([{ width: 50, height: 50 }], { mode: 'grid', columns: 5, gap: 0 });
  assert.strictEqual(r.canvasWidth, 50);
  assert.strictEqual(r.canvasHeight, 50);
});

console.log('\nimage-stitch: 全部 ' + passed + ' 个测试通过。');
