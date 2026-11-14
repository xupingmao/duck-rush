// 文本行级 diff 核心逻辑（浏览器与 node 测试共用）。
// 底层差异算法使用 vendored 的 jsdiff（lib/jsdiff/5.2.0/diff.js），
// 这里负责：选项归一化（忽略空白 / 大小写）、行号回填、以及统一输出结构。
//
// 在浏览器中通过 <script src="../../../../lib/jsdiff/5.2.0/diff.js"> 引入全局 Diff；
// 在 node 中通过 require 同一文件获取 Diff 对象。
(function (root, factory) {
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = factory(require('../../../lib/jsdiff/5.2.0/diff.js'));
    } else {
        if (!root.Diff || !root.Diff.diffLines) {
            throw new Error('jsdiff 未正确加载，请确认 lib/jsdiff/5.2.0/diff.js 可被访问。');
        }
        root.TextDiffCore = factory(root.Diff);
    }
}(typeof self !== 'undefined' ? self : this, function (Diff) {
    'use strict';

    // 预处理单行：根据选项归一化用于比较的内容
    function normalizeLine(line, options) {
        var s = line;
        if (options.ignoreWhitespace) {
            s = s.replace(/^\s+|\s+$/g, '');
        }
        if (options.ignoreCase) {
            s = s.toLowerCase();
        }
        return s;
    }

    // 将原始文本按行切分，并对比较用的内容做归一化。
    // 返回 { raw: string[], cmp: string[] }，raw 用于展示，cmp 用于比较。
    function splitAndNormalize(text, options) {
        var raw = text.split('\n');
        var cmp = raw.map(function (l) { return normalizeLine(l, options); });
        return { raw: raw, cmp: cmp };
    }

    // 计算两段文本的差异。输入为字符串数组（按行），返回统一结构的差异行数组。
    // 每行格式：{ type: 'equal'|'added'|'removed', left, right, ln, rn }
    //   ln/rn 为该行在左/右侧文本中的行号（1 起），缺失则为空字符串。
    function computeTextDiff(leftLines, rightLines, options) {
        options = options || {};
        var left = splitAndNormalize(leftLines.join('\n'), options);
        var right = splitAndNormalize(rightLines.join('\n'), options);

        // 用归一化后的内容交给 jsdiff 计算行级差异
        var changes = Diff.diffLines(left.cmp.join('\n'), right.cmp.join('\n'));

        var rows = [];
        var ln = 0; // 左侧已消费到的行号
        var rn = 0; // 右侧已消费到的行号
        changes.forEach(function (ch) {
            var lines = ch.value.split('\n');
            // 末尾的换行会产生一个空串元素，去掉它
            if (lines.length > 0 && lines[lines.length - 1] === '') {
                lines.pop();
            }
            if (ch.added) {
                lines.forEach(function (_, idx) {
                    rows.push({
                        type: 'added',
                        left: '',
                        right: right.raw[rn + idx],
                        ln: '',
                        rn: rn + idx + 1
                    });
                });
                rn += lines.length;
            } else if (ch.removed) {
                lines.forEach(function (_, idx) {
                    rows.push({
                        type: 'removed',
                        left: left.raw[ln + idx],
                        right: '',
                        ln: ln + idx + 1,
                        rn: ''
                    });
                });
                ln += lines.length;
            } else {
                lines.forEach(function (_, idx) {
                    rows.push({
                        type: 'equal',
                        left: left.raw[ln + idx],
                        right: right.raw[rn + idx],
                        ln: ln + idx + 1,
                        rn: rn + idx + 1
                    });
                });
                ln += lines.length;
                rn += lines.length;
            }
        });
        return rows;
    }

    // 便捷入口：直接传入原始文本字符串
    function diffText(leftText, rightText, options) {
        return computeTextDiff(leftText.split('\n'), rightText.split('\n'), options);
    }

    return { normalizeLine, splitAndNormalize, computeTextDiff, diffText };
}));
