#!/usr/bin/env node
/**
 * run-audit.js —— 元素间距检查器入口（真实渲染测量）
 *
 * 用法:
 *   node run-audit.js --url http://localhost:5173/
 *   node run-audit.js --file ./index.html --shot
 *   node run-audit.js --url http://localhost:3000 --viewport 1440x900,390x844 --min-severity warning
 *   node run-audit.js --help
 *
 * 输出:
 *   stdout 打印 Markdown 报告
 *   --out 指定 JSON 报告路径（默认 ./spacing-audit.json）
 *   --shot 生成一张标注了问题元素的全页截图（默认 ./spacing-audit.png）
 */

'use strict';

const path = require('path');
const fs = require('fs');
const os = require('os');

const PROBE = path.join(__dirname, 'probe-spacing.js');

// ---------------------------------------------------------------- 参数解析

function parseArgs(argv) {
  const opts = {
    url: null,
    file: null,
    out: path.resolve(process.cwd(), 'spacing-audit.json'),
    md: null,
    shot: false,
    shotPath: path.resolve(process.cwd(), 'spacing-audit.png'),
    viewports: [{ w: 1440, h: 900, name: 'desktop' }],
    minSeverity: 'info',
    ignore: [],
    jsonOnly: false,
    timeout: 30000,
    wait: 400,
    thresholds: {}
  };

  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    switch (a) {
      case '-h':
      case '--help':
        opts.help = true;
        break;
      case '--url': opts.url = next(); break;
      case '--file': opts.file = next(); break;
      case '--out': opts.out = path.resolve(next()); break;
      case '--md': opts.md = path.resolve(next()); break;
      case '--shot': opts.shot = true; break;
      case '--shot-path': opts.shotPath = path.resolve(next()); break;
      case '--viewport': opts.viewports = parseViewports(next()); break;
      case '--min-severity': opts.minSeverity = next(); break;
      case '--ignore': opts.ignore.push(...String(next()).split(',')); break;
      case '--json': opts.jsonOnly = true; break;
      case '--timeout': opts.timeout = parseInt(next(), 10) || 30000; break;
      case '--wait': opts.wait = parseInt(next(), 10) || 0; break;
      case '--threshold':
        // --threshold minSiblingGap=8,minTextGap=12
        String(next()).split(',').forEach(pair => {
          const [k, v] = pair.split('=');
          if (k && v !== undefined) opts.thresholds[k.trim()] = parseFloat(v);
        });
        break;
      default:
        if (a.startsWith('-')) {
          console.error(`未知参数: ${a}`);
          opts.help = true;
        }
    }
  }
  return opts;
}

function parseViewports(str) {
  const named = {
    desktop: { w: 1440, h: 900 },
    laptop: { w: 1366, h: 768 },
    tablet: { w: 834, h: 1112 },
    mobile: { w: 390, h: 844 }
  };
  return String(str).split(',').map(s => {
    s = s.trim();
    if (named[s]) return { ...named[s], name: s };
    const m = s.match(/^(\d+)x(\d+)$/);
    if (!m) throw new Error(`视口格式错误: ${s}（应为 1440x900 或 desktop/mobile）`);
    return { w: +m[1], h: +m[2], name: s };
  });
}

const HELP = `
元素间距检查器 —— 在真实浏览器里测量元素间距，找出紧挨/贴边/重叠/拥挤

用法:
  node run-audit.js --url <地址> [选项]
  node run-audit.js --file <html路径> [选项]

选项:
  --url <url>              要检查的页面地址（推荐，贴近真实环境）
  --file <path>            本地 HTML 文件（自动转 file://）
  --viewport <list>        视口，逗号分隔。支持 desktop/laptop/tablet/mobile 或 1440x900
                           默认: desktop
  --min-severity <level>   只报告该级别及以上: critical | warning | info（默认 info）
  --ignore <rules>         忽略指定规则，逗号分隔（如 flex-no-gap,edge-flush）
  --threshold <k=v,...>    覆盖阈值，如 minSiblingGap=8,minTextGap=12
  --out <path>             JSON 报告路径（默认 ./spacing-audit.json）
  --md <path>              另外把 Markdown 报告写入文件
  --shot                   生成全页截图，问题元素用红框标出
  --shot-path <path>       截图路径（默认 ./spacing-audit.png）
  --json                   只在 stdout 输出 JSON，不打印 Markdown
  --wait <ms>              页面加载后额外等待，等动画/异步渲染（默认 400）
  --timeout <ms>           页面加载超时（默认 30000）
  -h, --help               显示本帮助

规则:
  flex-no-gap            flex/grid 容器 gap 为 0，子元素紧挨
  sibling-too-close      相邻块级元素间距过小
  text-block-too-close   标题/段落之间间距过小
  sibling-overlap        兄弟元素重叠（可能压字）
  content-flush          有背景/边框的容器内边距不足，文字贴边
  tap-targets-too-close  相邻可点击元素距离过近（易误触）
  tap-target-small       可点击元素尺寸过小
  line-height-tight      多行文本行高过紧
  edge-flush             文字左右贴到视口边缘

退出码: 0 未发现 critical；1 发现 critical；2 环境/参数错误
`;

// ---------------------------------------------------------------- 环境定位

function loadPlaywright() {
  const home = os.homedir();
  const candidates = [
    process.env.PLAYWRIGHT_CORE_PATH,
    path.join(home, '.workbuddy', 'binaries', 'node', 'workspace', 'node_modules', 'playwright-core'),
    'playwright-core',
    'playwright'
  ].filter(Boolean);

  const errors = [];
  for (const c of candidates) {
    try {
      return { pw: require(c), from: c };
    } catch (e) {
      errors.push(`${c}: ${e.code || e.message}`);
    }
  }
  throw new Error(
    '找不到 playwright-core。安装方式（任选其一）：\n' +
    '  npm i -g playwright-core  并设置 PLAYWRIGHT_CORE_PATH\n' +
    '  或在本目录 npm link playwright-core\n\n' +
    '尝试过的路径:\n  ' + errors.join('\n  ')
  );
}

function findChrome() {
  if (process.env.CHROME_PATH && fs.existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  const home = os.homedir();
  const roots = [
    path.join(home, 'AppData', 'Local', 'ms-playwright'),
    path.join(home, '.cache', 'ms-playwright'),
    path.join(home, 'Library', 'Caches', 'ms-playwright')
  ];
  const rels = process.platform === 'win32'
    ? ['chrome-win64/chrome.exe', 'chrome-win/chrome.exe']
    : process.platform === 'darwin'
      ? ['chrome-mac/Chromium.app/Contents/MacOS/Chromium', 'chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium']
      : ['chrome-linux/chrome', 'chrome-linux64/chrome'];

  for (const root of roots) {
    if (!fs.existsSync(root)) continue;
    const dirs = fs.readdirSync(root)
      .filter(d => d.startsWith('chromium-'))
      .sort()
      .reverse();
    for (const d of dirs) {
      for (const rel of rels) {
        const p = path.join(root, d, rel);
        if (fs.existsSync(p)) return p;
      }
    }
  }
  return null;
}

function toFileUrl(p) {
  let abs = path.resolve(p).replace(/\\/g, '/');
  if (!abs.startsWith('/')) abs = '/' + abs;
  return 'file://' + encodeURI(abs).replace(/#/g, '%23').replace(/\?/g, '%3F');
}

// ---------------------------------------------------------------- 报告渲染

const SEV_LABEL = { critical: '严重', warning: '警告', info: '提示' };
const SEV_ICON = { critical: '🔴', warning: '🟠', info: '🟡' };

function cssPatch(issue) {
  if (issue.rule === 'flex-no-gap') {
    const cls = (issue.selector.match(/\.([A-Za-z0-9_-]+)/g) || []).pop();
    const name = cls ? cls.replace('.', '') : null;
    const gap = issue.expected || 8;
    return name
      ? `.${name} {\n  gap: ${gap}px;\n}`
      : `/* ${issue.selector} */\n{\n  gap: ${gap}px;\n}`;
  }
  return null;
}

function renderMarkdown(runs, opts, source) {
  const lines = [];
  const total = runs.reduce((acc, r) => {
    ['critical', 'warning', 'info'].forEach(k => { acc[k] += r.result.summary.counts[k]; });
    return acc;
  }, { critical: 0, warning: 0, info: 0 });

  const worstScore = Math.min(...runs.map(r => r.result.summary.score));
  const verdict = total.critical > 0 ? '不通过' : (total.warning > 0 ? '需要修' : '通过');

  lines.push('# 元素间距检查报告');
  lines.push('');
  lines.push(`- 目标: \`${source}\``);
  lines.push(`- 视口: ${runs.map(r => `${r.viewport.name} ${r.viewport.w}×${r.viewport.h}`).join('、')}`);
  lines.push(`- 最低得分: **${worstScore}/100**（${verdict}）`);
  lines.push(`- 问题: ${SEV_ICON.critical} ${total.critical} 严重 · ${SEV_ICON.warning} ${total.warning} 警告 · ${SEV_ICON.info} ${total.info} 提示`);
  lines.push('');

  if (total.critical + total.warning + total.info === 0) {
    lines.push('没有发现元素紧挨、贴边、重叠或行高过紧的问题。');
    lines.push('');
    return lines.join('\n');
  }

  for (const run of runs) {
    const issues = run.result.issues;
    if (!issues.length) continue;
    lines.push(`## 视口 ${run.viewport.name} (${run.viewport.w}×${run.viewport.h})`);
    lines.push(`得分 ${run.result.summary.score}/100 · ${issues.length} 个问题`);
    lines.push('');
    lines.push('| # | 级别 | 规则 | 元素 | 实测 | 建议 |');
    lines.push('|---|------|------|------|------|------|');
    issues.forEach((it, idx) => {
      const sel = '`' + (it.selector.length > 46 ? '…' + it.selector.slice(-46) : it.selector) + '`';
      const unit = it.unit || 'px';
      const measure = (!it.expected)
        ? `${it.measured}${unit}`
        : `${it.measured}${unit} / ≥${it.expected}${unit}`;
      lines.push(`| ${idx + 1} | ${SEV_ICON[it.severity]} | \`${it.rule}\` | ${sel} | ${measure} | ${(it.hint || '').split('\n')[0]} |`);
    });
    lines.push('');

    for (const sev of ['critical', 'warning', 'info']) {
      const group = issues.filter(i => i.severity === sev);
      if (!group.length) continue;
      lines.push(`### ${SEV_ICON[sev]} ${SEV_LABEL[sev]}`);
      lines.push('');
      group.forEach((it, idx) => {
        lines.push(`**${idx + 1}. ${it.message}**`);
        lines.push('');
        lines.push(`- 选择器: \`${it.selector}\``);
        if (it.relatedSelector) lines.push(`- 相邻元素: \`${it.relatedSelector}\``);
        if (it.tightPairs !== undefined) lines.push(`- 紧挨处: ${it.tightPairs} / ${it.childCount} 个子元素`);
        const patch = cssPatch(it);
        if (patch) {
          lines.push('- 直接可用:');
          lines.push('  ```css');
          patch.split('\n').forEach(l => lines.push('  ' + l));
          lines.push('  ```');
        } else {
          lines.push(`- 修复: ${it.hint}`);
        }
        lines.push('');
      });
    }
  }

  if (runs[0] && runs[0].result.topSpacingValues && runs[0].result.topSpacingValues.length) {
    lines.push('## 页面上出现的间距值（频次）');
    lines.push('');
    lines.push(runs[0].result.topSpacingValues.map(([v, n]) => `${v}px×${n}`).join(' · '));
    lines.push('');
    lines.push('如果出现 13/17/23 这类非 4 或 8 倍数的值，说明间距是逐个手写的，建议收进 4/8/12/16/24/32 的刻度。');
    lines.push('');
  }

  return lines.join('\n');
}

// ---------------------------------------------------------------- 主流程

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help) {
    process.stdout.write(HELP);
    process.exit(0);
  }

  let source;
  if (opts.url) {
    source = opts.url;
  } else if (opts.file) {
    if (!fs.existsSync(opts.file)) {
      console.error(`文件不存在: ${opts.file}`);
      process.exit(2);
    }
    source = toFileUrl(opts.file);
  } else {
    console.error('必须指定 --url 或 --file\n');
    process.stdout.write(HELP);
    process.exit(2);
  }

  let chromium;
  try {
    const { pw } = loadPlaywright();
    chromium = pw.chromium;
  } catch (e) {
    console.error(e.message);
    process.exit(2);
  }

  const executablePath = findChrome();
  if (!executablePath) {
    console.error(
      '找不到 Chromium 内核。安装方式：\n' +
      '  npx playwright install chromium\n' +
      '或设置环境变量 CHROME_PATH 指向已有的 chrome.exe'
    );
    process.exit(2);
  }

  const probeSrc = fs.readFileSync(PROBE, 'utf8');
  const minRank = { critical: 0, warning: 1, info: 2 }[opts.minSeverity] ?? 2;
  const runs = [];

  let browser;
  try {
    browser = await chromium.launch({ executablePath, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  } catch (e) {
    console.error(`启动浏览器失败: ${e.message}`);
    process.exit(2);
  }

  for (const vp of opts.viewports) {
    const page = await browser.newPage({
      viewport: { width: vp.w, height: vp.h },
      deviceScaleFactor: 1
    });
    const consoleErrors = [];
    page.on('pageerror', err => consoleErrors.push(String(err.message).slice(0, 200)));

    try {
      await page.goto(source, { waitUntil: 'networkidle', timeout: opts.timeout });
    } catch (e) {
      try {
        await page.goto(source, { waitUntil: 'domcontentloaded', timeout: opts.timeout });
      } catch (e2) {
        console.error(`[${vp.name}] 页面加载失败: ${e2.message.split('\n')[0]}`);
        await page.close();
        continue;
      }
    }

    if (opts.wait > 0) await page.waitForTimeout(opts.wait);

    await page.addScriptTag({ content: probeSrc });
    let result = await page.evaluate(cfg => window.__auditSpacing(cfg), opts.thresholds);

    // 规则过滤与级别过滤
    result.issues = result.issues
      .filter(it => !opts.ignore.includes(it.rule))
      .filter(it => ({ critical: 0, warning: 1, info: 2 }[it.severity] ?? 2) <= minRank);

    const counts = { critical: 0, warning: 0, info: 0 };
    result.issues.forEach(it => counts[it.severity]++);
    result.summary.counts = counts;
    result.summary.total = result.issues.length;
    result.summary.score = Math.max(0, 100 - counts.critical * 8 - counts.warning * 3 - counts.info * 1);
    result.summary.verdict = counts.critical > 0 ? 'fail' : (counts.warning > 0 ? 'needs-work' : 'pass');
    if (consoleErrors.length) result.meta.pageErrors = consoleErrors;

    // 截图：给问题元素加红框后全页截
    if (opts.shot && result.issues.length) {
      try {
        const selectors = [...new Set(result.issues.map(i => i.selector).filter(Boolean))];
        await page.evaluate(sels => {
          const style = document.createElement('style');
          style.id = '__spacing_audit_style';
          const rules = sels.map(s => {
            try { document.querySelector(s); } catch (e) { return ''; }
            return `${s}{outline:2px solid #e5484d !important;outline-offset:1px !important;}`;
          }).join('');
          style.textContent = rules;
          document.head.appendChild(style);
        }, selectors);
        const shotFile = opts.viewports.length > 1
          ? opts.shotPath.replace(/\.png$/, `-${vp.name}.png`)
          : opts.shotPath;
        await page.screenshot({ path: shotFile, fullPage: true });
        result.meta.screenshot = shotFile;
      } catch (e) {
        result.meta.screenshotError = e.message.slice(0, 200);
      }
    }

    runs.push({ viewport: vp, result });
    await page.close();
  }

  await browser.close();

  if (!runs.length) {
    console.error('所有视口都加载失败，未产生报告');
    process.exit(2);
  }

  // JSON 落盘
  const payload = {
    source,
    chrome: executablePath,
    options: { minSeverity: opts.minSeverity, ignore: opts.ignore, thresholds: opts.thresholds },
    generatedAt: new Date().toISOString(),
    runs
  };
  try {
    fs.writeFileSync(opts.out, JSON.stringify(payload, null, 2), 'utf8');
  } catch (e) {
    console.error(`写 JSON 失败: ${e.message}`);
  }

  const md = renderMarkdown(runs, opts, source);
  if (opts.md) {
    try { fs.writeFileSync(opts.md, md, 'utf8'); } catch (e) { console.error(`写 Markdown 失败: ${e.message}`); }
  }

  if (opts.jsonOnly) {
    process.stdout.write(JSON.stringify(payload, null, 2) + '\n');
  } else {
    process.stdout.write(md + '\n');
    if (opts.out) process.stdout.write(`JSON 报告: ${opts.out}\n`);
    const shots = runs.map(r => r.result.meta.screenshot).filter(Boolean);
    if (shots.length) process.stdout.write(`截图: ${shots.join(', ')}\n`);
  }

  const hasCritical = runs.some(r => r.result.summary.counts.critical > 0);
  process.exit(hasCritical ? 1 : 0);
}

main().catch(e => {
  console.error('未预期错误:', e && e.stack || e);
  process.exit(2);
});
