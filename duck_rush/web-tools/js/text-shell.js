/**
 * 纯前端 Shell 管道模拟（零依赖，浏览器 / Node 双挂载）
 *
 * 用法：
 *   TextShell.run('sort -u | head -5', 'b\na\nb\n')
 *   // => { output: 'a\nb\n', error: '', exitCode: 0, log: [], commands: ['sort', 'head'] }
 *
 * 命令注册：
 *   TextShell.register('upper', function (ctx) {
 *       ctx.pipe.write(ctx.lines.map(l => l.toUpperCase()));
 *   }, { usage: 'upper', desc: '转为大写' });
 *
 * 命令实现统一为 func(ctx)，ctx 内容：
 *   name     命令名
 *   argv     完整参数数组（含命令名）
 *   args     位置参数（如 grep 的 pattern）
 *   opts     选项对象，如 head -n 5 => { n: '5' }；sort -u => { u: true }
 *   input    上游文本
 *   lines    上游按行切分后的数组（不含末尾空行）
 *   pipe     管道：read() 取上游行、readText() 取上游文本、write(文本|行数组) 写下游
 *   out      等价于 pipe.write
 *   log(msg) 写诊断信息（收集到 result.log，不进入管道）
 *   trailing 上游文本末尾是否带换行
 *
 * 命令可以直接 return 字符串或行数组作为下游输入；
 * 若 return undefined，则以 pipe.write 写入的内容作为输出。
 */
(function (global) {
    'use strict';

    /** 命令表：name -> { name, fn, meta, args } */
    const registry = new Map();

    /**
     * 注册命令
     * @param {string} name
     * @param {(ctx: object) => (string|string[]|void)} fn
     * @param {{usage?: string, desc?: string, valueFlags?: string[], numberFlag?: string}} [meta]
     *        valueFlags 需要取值的短选项（如 -d , -f 1）
     *        numberFlag 把 -5 这类数字选项解析成 opts[numberFlag]（head/tail 用）
     */
    function register(name, fn, meta) {
        if (typeof fn !== 'function') throw new Error('命令实现必须是函数: ' + name);
        registry.set(name, {
            name: name,
            fn: fn,
            meta: meta || {},
            usage: (meta && meta.usage) || name,
            desc: (meta && meta.desc) || ''
        });
        return registry.get(name);
    }

    /** 批量注册：{ name: fn } 或 { name: { fn, meta } } */
    function registerAll(map) {
        Object.keys(map).forEach(name => {
            const item = map[name];
            if (typeof item === 'function') register(name, item);
            else register(name, item.fn, item.meta);
        });
    }

    function get(name) { return registry.get(name) || null; }
    function has(name) { return registry.has(name); }
    function names() { return Array.from(registry.keys()); }

    /** 命令清单（按注册顺序），供 UI 生成帮助 */
    function list() {
        return Array.from(registry.values()).map(c => ({
            name: c.name, usage: c.usage, desc: c.desc
        }));
    }

    // ---------------------------------------------------------------- 词法

    /** Shell 风格分词：支持单/双引号与反斜杠转义 */
    function tokenize(line) {
        const tokens = [];
        let cur = '';
        let hasCur = false;
        let quote = null;

        for (let i = 0; i < line.length; i++) {
            const ch = line[i];

            if (ch === '\\' && i + 1 < line.length) {
                cur += line[++i];
                hasCur = true;
                continue;
            }

            if (quote) {
                if (ch === quote) quote = null;
                else cur += ch;
                continue;
            }

            if (ch === '"' || ch === "'") { quote = ch; hasCur = true; continue; }

            if (ch === ' ' || ch === '\t') {
                if (hasCur) { tokens.push(cur); cur = ''; hasCur = false; }
                continue;
            }

            cur += ch;
            hasCur = true;
        }

        if (quote) throw new Error('引号未闭合');
        if (hasCur) tokens.push(cur);
        return tokens;
    }

    /** 按 | 切分管道（引号与转义中的 | 不切分） */
    function splitPipeline(line) {
        const parts = [];
        let cur = '';
        let quote = null;

        for (let i = 0; i < line.length; i++) {
            const ch = line[i];

            if (ch === '\\' && i + 1 < line.length) {
                cur += ch + line[++i];
                continue;
            }
            if (quote) {
                cur += ch;
                if (ch === quote) quote = null;
                continue;
            }
            if (ch === '"' || ch === "'") { quote = ch; cur += ch; continue; }
            if (ch === '|') { parts.push(cur); cur = ''; continue; }
            cur += ch;
        }

        if (quote) throw new Error('引号未闭合');
        parts.push(cur);

        return parts.map(p => p.trim()).filter(p => p !== '');
    }

    /**
     * 解析参数
     * @param {string[]} argv 不含命令名的参数
     * @param {{valueFlags?: string[], numberFlag?: string}} [options]
     */
    function parseArgs(argv, options) {
        options = options || {};
        const valueFlags = (options.valueFlags || []).slice();
        const numberFlag = options.numberFlag || null;
        // -n5 / -n 5 都要求该字母可带值
        if (numberFlag && valueFlags.indexOf(numberFlag) === -1) valueFlags.push(numberFlag);
        const args = [];
        const opts = Object.create(null);

        for (let i = 0; i < argv.length; i++) {
            const token = argv[i];

            if (token === '--') {
                args.push(...argv.slice(i + 1));
                break;
            }

            if (token.indexOf('--') === 0 && token.length > 2) {
                const body = token.slice(2);
                const eq = body.indexOf('=');
                if (eq !== -1) {
                    opts[body.slice(0, eq)] = body.slice(eq + 1);
                } else if (valueFlags.indexOf(body) !== -1 && i + 1 < argv.length) {
                    opts[body] = argv[++i];
                } else {
                    opts[body] = true;
                }
                continue;
            }

            if (token.length > 1 && token[0] === '-' && !/^-\d/.test(token)) {
                const chars = token.slice(1);
                for (let c = 0; c < chars.length; c++) {
                    const ch = chars[c];
                    if (valueFlags.indexOf(ch) !== -1) {
                        const rest = chars.slice(c + 1);
                        if (rest) opts[ch] = rest;
                        else if (i + 1 < argv.length) opts[ch] = argv[++i];
                        else opts[ch] = true;
                        break;
                    }
                    opts[ch] = true;
                }
                continue;
            }

            if (numberFlag && /^-\d+$/.test(token)) {
                opts[numberFlag] = token.slice(1);
                continue;
            }

            args.push(token);
        }

        return { args: args, opts: opts };
    }

    /** 文本切行；返回行数组与末尾是否带换行 */
    function splitLines(text) {
        const raw = String(text == null ? '' : text);
        if (raw === '') return { lines: [], trailing: false };
        const lines = raw.split('\n');
        if (lines[lines.length - 1] === '') {
            lines.pop();
            return { lines: lines, trailing: true };
        }
        return { lines: lines, trailing: false };
    }

    function toLines(data) {
        if (data == null) return [];
        if (Array.isArray(data)) return data.map(v => String(v));
        return splitLines(String(data)).lines;
    }

    function joinLines(lines, trailing) {
        if (lines.length === 0) return '';
        return lines.join('\n') + (trailing ? '\n' : '');
    }

    // ---------------------------------------------------------------- 执行

    function createContext(cmd, argv, input) {
        const parsed = splitLines(input);
        const state = { written: [], logs: [] };

        const pipe = {
            /** 上游行（副本） */
            read: () => parsed.lines.slice(),
            /** 上游原始文本 */
            readText: () => String(input == null ? '' : input),
            /** 上游行（只读引用） */
            lines: parsed.lines,
            /** 写入下游：接受字符串或行数组 */
            write: (data) => { toLines(data).forEach(l => state.written.push(l)); },
            writeLine: (line) => { state.written.push(String(line)); }
        };

        const flags = parseArgs(argv.slice(1), {
            valueFlags: cmd.meta.valueFlags || [],
            numberFlag: cmd.meta.numberFlag || null
        });

        return {
            name: cmd.name,
            argv: argv,
            args: flags.args,
            opts: flags.opts,
            input: String(input == null ? '' : input),
            lines: parsed.lines,
            trailing: parsed.trailing,
            pipe: pipe,
            out: pipe.write,
            log: (msg) => { state.logs.push(String(msg)); },
            meta: cmd.meta,
            _state: state
        };
    }

    /** 命令返回值 → 下游文本 */
    function finalize(returned, ctx) {
        if (returned !== undefined && returned !== null) {
            if (Array.isArray(returned)) return joinLines(returned.map(String), ctx.trailing && returned.length > 0);
            return String(returned);
        }
        return joinLines(ctx._state.written, ctx.trailing);
    }

    /**
     * 执行一条管道命令
     * @param {string} commandLine 如 'sort -u | head -5'
     * @param {string} input 输入文本
     * @returns {{output: string, error: string, exitCode: number, log: string[], commands: string[]}}
     */
    function run(commandLine, input) {
        const result = { output: '', error: '', exitCode: 0, log: [], commands: [] };
        const line = String(commandLine == null ? '' : commandLine).trim();

        if (!line) {
            result.error = '命令为空';
            result.exitCode = 1;
            return result;
        }

        let segments;
        try {
            segments = splitPipeline(line);
        } catch (e) {
            result.error = e.message;
            result.exitCode = 2;
            return result;
        }

        if (segments.length === 0) {
            result.error = '命令为空';
            result.exitCode = 1;
            return result;
        }

        let current = String(input == null ? '' : input);

        for (const segment of segments) {
            let argv;
            try {
                argv = tokenize(segment);
            } catch (e) {
                result.error = e.message;
                result.exitCode = 2;
                result.output = '';
                return result;
            }

            const name = argv[0];
            const cmd = registry.get(name);
            if (!cmd) {
                result.error = '未知命令: ' + name + '（可用: ' + names().join(', ') + '）';
                result.exitCode = 127;
                result.output = '';
                return result;
            }

            const ctx = createContext(cmd, argv, current);
            let returned;
            try {
                returned = cmd.fn(ctx);
            } catch (e) {
                result.error = name + ': ' + e.message;
                result.exitCode = 1;
                result.output = '';
                result.log = result.log.concat(ctx._state.logs);
                return result;
            }

            result.log = result.log.concat(ctx._state.logs);
            result.commands.push(name);
            current = finalize(returned, ctx);
        }

        result.output = current;
        return result;
    }

    // ---------------------------------------------------------------- 内置命令

    function num(value, fallback) {
        const n = parseInt(value, 10);
        return isNaN(n) ? fallback : n;
    }

    /** 把 -n 5 / -5 / 默认 10 统一成数字 */
    function takeCount(opts, fallback) {
        if (opts.n !== undefined) return num(opts.n, fallback);
        if (opts.c !== undefined) return num(opts.c, fallback);
        return fallback;
    }

    function toRegExp(pattern, ignoreCase) {
        try {
            return new RegExp(pattern, ignoreCase ? 'i' : '');
        } catch (e) {
            // 非法正则按字面量处理
            const escaped = pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            return new RegExp(escaped, ignoreCase ? 'i' : '');
        }
    }

    registerAll({
        cat: {
            fn: ctx => { ctx.pipe.write(ctx.lines.map((l, i) => ctx.opts.n ? (i + 1) + '\t' + l : l)); },
            meta: { usage: 'cat [-n]', desc: '原样输出（-n 显示行号）' }
        },
        echo: {
            fn: ctx => ctx.args.join(' ') + (ctx.opts.n ? '' : '\n'),
            meta: { usage: 'echo 文本', desc: '输出参数文本，忽略上游输入' }
        },
        head: {
            fn: ctx => { ctx.pipe.write(ctx.lines.slice(0, Math.max(0, takeCount(ctx.opts, 10)))); },
            meta: { usage: 'head -n 5', desc: '取前 N 行（默认 10）', numberFlag: 'n' }
        },
        tail: {
            fn: ctx => {
                const n = takeCount(ctx.opts, 10);
                ctx.pipe.write(n <= 0 ? [] : ctx.lines.slice(-n));
            },
            meta: { usage: 'tail -n 5', desc: '取后 N 行（默认 10）', numberFlag: 'n' }
        },
        grep: {
            fn: ctx => {
                const pattern = ctx.args[0];
                if (pattern === undefined) throw new Error('缺少匹配模式');
                const re = toRegExp(pattern, !!ctx.opts.i);
                const invert = !!ctx.opts.v;
                const matched = ctx.lines.filter(l => (re.test(l) !== invert));
                if (ctx.opts.c) return String(matched.length) + '\n';
                ctx.pipe.write(ctx.opts.n
                    ? ctx.lines.map((l, i) => (re.test(l) !== invert) ? (i + 1) + ':' + l : null).filter(Boolean)
                    : matched);
            },
            meta: { usage: "grep [-v] [-i] [-n] [-c] 模式", desc: '筛选匹配行（-v 反选、-i 忽略大小写、-n 带行号、-c 只计数）' }
        },
        sed: {
            fn: ctx => {
                const script = ctx.args[0];
                if (script === undefined) throw new Error('缺少 sed 脚本');

                const sub = parseSubstitute(script);
                if (sub) {
                    const flags = sub.flags.replace(/[^gimsuy]/g, '');
                    const re = new RegExp(sub.pattern, flags);
                    const replacement = sub.replacement.replace(/\\n/g, '\n').replace(/\\t/g, '\t');
                    ctx.pipe.write(ctx.lines.map(l => l.replace(re, replacement)));
                    return;
                }

                const del = script.match(/^\/([\s\S]+)\/d$/);
                if (del) {
                    const re = toRegExp(del[1], false);
                    ctx.pipe.write(ctx.lines.filter(l => !re.test(l)));
                    return;
                }

                throw new Error('仅支持 s/查找/替换/标志 与 /模式/d');
            },
            meta: { usage: "sed 's/foo/bar/g'", desc: '替换或删除行（支持 s///g、/模式/d）' }
        },
        sort: {
            fn: ctx => {
                let lines = ctx.lines.slice();
                const numeric = !!ctx.opts.n;
                const fold = !!ctx.opts.f;
                lines.sort((a, b) => {
                    if (numeric) return (parseFloat(a) || 0) - (parseFloat(b) || 0);
                    const x = fold ? a.toLowerCase() : a;
                    const y = fold ? b.toLowerCase() : b;
                    return x < y ? -1 : x > y ? 1 : 0;
                });
                if (ctx.opts.r) lines.reverse();
                if (ctx.opts.u) lines = lines.filter((l, i) => i === 0 || l !== lines[i - 1]);
                ctx.pipe.write(lines);
            },
            meta: { usage: 'sort [-u] [-n] [-r] [-f]', desc: '排序（-u 去重、-n 数值、-r 倒序、-f 忽略大小写）' }
        },
        uniq: {
            fn: ctx => {
                const out = [];
                const groups = [];
                ctx.lines.forEach(l => {
                    const last = groups[groups.length - 1];
                    if (last && last.value === l) last.count++;
                    else groups.push({ value: l, count: 1 });
                });
                groups.forEach(g => {
                    if (ctx.opts.d && g.count < 2) return;
                    if (ctx.opts.u && g.count > 1) return;
                    out.push(ctx.opts.c ? String(g.count).padStart(7, ' ') + ' ' + g.value : g.value);
                });
                ctx.pipe.write(out);
            },
            meta: { usage: 'uniq [-c] [-d] [-u]', desc: '去除连续重复行（-c 计数、-d 仅重复、-u 仅唯一）' }
        },
        wc: {
            fn: ctx => {
                const text = ctx.input;
                const lines = ctx.lines.length;
                const words = text.split(/\s+/).filter(Boolean).length;
                const chars = text.length;
                const only = [];
                if (ctx.opts.l) only.push(lines);
                if (ctx.opts.w) only.push(words);
                if (ctx.opts.c) only.push(chars);
                const parts = only.length ? only : [lines, words, chars];
                return parts.join(' ') + '\n';
            },
            meta: { usage: 'wc [-l] [-w] [-c]', desc: '统计行数/词数/字符数' }
        },
        awk: {
            fn: ctx => {
                const script = ctx.args.join(' ') || '{print $0}';
                const m = script.match(/\{\s*print\s+([\s\S]*?)\s*\}/);
                if (!m) throw new Error("仅支持形如 {print $1} 的脚本");
                const exprs = splitFields(m[1]);
                const out = ctx.lines.map((line, idx) => exprs.map(e => evalAwk(e, line, idx + 1)).join(' '));
                ctx.pipe.write(out);
            },
            meta: { usage: "awk '{print $1}'", desc: '取字段（支持 $0/$1..$9、NF、NR、字符串）' }
        },
        cut: {
            fn: ctx => {
                const delim = String(ctx.opts.d || '\t').replace(/\\t/g, '\t');
                const spec = String(ctx.opts.f || '1');
                const wanted = new Set();
                spec.split(',').forEach(part => {
                    const range = part.match(/^(\d+)-(\d+)$/);
                    if (range) {
                        for (let i = +range[1]; i <= +range[2]; i++) wanted.add(i);
                    } else if (/^\d+$/.test(part)) {
                        wanted.add(+part);
                    }
                });
                const max = Math.max(...wanted);
                ctx.pipe.write(ctx.lines.map(l => {
                    const parts = l.split(delim);
                    return Array.from(wanted).sort((a, b) => a - b)
                        .filter(i => i <= parts.length)
                        .map(i => parts[i - 1]).join(delim);
                }));
                void max;
            },
            meta: { usage: 'cut -d , -f 1,3', desc: '按分隔符取字段', valueFlags: ['d', 'f'] }
        },
        tr: {
            fn: ctx => {
                if (ctx.opts.d) {
                    const set = expandSet(ctx.args[0] || '');
                    ctx.pipe.write(ctx.lines.map(l => l.split('').filter(c => set.indexOf(c) === -1).join('')));
                    return;
                }
                const from = expandSet(ctx.args[0] || '');
                const to = expandSet(ctx.args[1] || '');
                ctx.pipe.write(ctx.lines.map(l => l.split('').map(c => {
                    const i = from.indexOf(c);
                    return i === -1 ? c : (to[i] !== undefined ? to[i] : to[to.length - 1]);
                }).join('')));
            },
            meta: { usage: "tr a-z A-Z | tr -d x", desc: '字符替换或删除（-d 删除）' }
        },
        rev: {
            fn: ctx => { ctx.pipe.write(ctx.lines.map(l => l.split('').reverse().join(''))); },
            meta: { usage: 'rev', desc: '反转每行字符顺序' }
        },
        tac: {
            fn: ctx => { ctx.pipe.write(ctx.lines.slice().reverse()); },
            meta: { usage: 'tac', desc: '反转行的顺序' }
        },
        nl: {
            fn: ctx => { ctx.pipe.write(ctx.lines.map((l, i) => String(i + 1).padStart(6, ' ') + '\t' + l)); },
            meta: { usage: 'nl', desc: '给每行加行号' }
        },
        trim: {
            fn: ctx => { ctx.pipe.write(ctx.lines.map(l => l.trim())); },
            meta: { usage: 'trim', desc: '去除每行首尾空白' }
        }
    });

    /**
     * 解析 sed 的 s/查找/替换/标志
     * 分隔符可以是任意非空白字符（如 s#a#b#g），段内可用 \ 转义分隔符
     */
    function parseSubstitute(script) {
        if (script[0] !== 's') return null;
        const sep = script[1];
        if (!sep || /\s/.test(sep) || sep === '\\') return null;

        const parts = [];
        let cur = '';
        for (let i = 2; i < script.length; i++) {
            const ch = script[i];
            if (ch === '\\' && i + 1 < script.length) { cur += ch + script[++i]; continue; }
            if (ch === sep) { parts.push(cur); cur = ''; continue; }
            cur += ch;
        }
        parts.push(cur);

        if (parts.length < 2) return null;
        return { pattern: parts[0], replacement: parts[1], flags: parts[2] || '' };
    }

    /** 按逗号切分 awk 的 print 参数（引号感知） */
    function splitFields(expr) {
        const out = [];
        let cur = '';
        let quote = null;
        for (let i = 0; i < expr.length; i++) {
            const ch = expr[i];
            if (quote) {
                cur += ch;
                if (ch === quote) quote = null;
                continue;
            }
            if (ch === '"' || ch === "'") { quote = ch; cur += ch; continue; }
            if (ch === ',') { out.push(cur.trim()); cur = ''; continue; }
            cur += ch;
        }
        if (cur.trim()) out.push(cur.trim());
        return out;
    }

    /** 求值 awk 表达式片段（模板替换式，支持 $n / NF / NR / 字符串 / 拼接） */
    function evalAwk(expr, line, nr) {
        const fields = line.trim() ? line.trim().split(/\s+/) : [];
        let out = '';
        let i = 0;
        while (i < expr.length) {
            const ch = expr[i];
            // awk 的拼接是「并置」，表达式里的空白只是分隔，不参与输出
            // （字符串内的空白在下面的分支里被整段消费，不会走到这里）
            if (ch === ' ' || ch === '\t') { i++; continue; }
            if (ch === '"' || ch === "'") {
                const end = expr.indexOf(ch, i + 1);
                if (end === -1) { out += expr.slice(i + 1); break; }
                out += expr.slice(i + 1, end);
                i = end + 1;
                continue;
            }
            if (ch === '$') {
                const m = expr.slice(i).match(/^\$(\d+|NF|0)/);
                if (m) {
                    if (m[1] === '0') out += line;
                    else if (m[1] === 'NF') out += String(fields[fields.length - 1] !== undefined ? fields[fields.length - 1] : '');
                    else out += String(fields[+m[1] - 1] !== undefined ? fields[+m[1] - 1] : '');
                    i += m[0].length;
                    continue;
                }
                out += ch; i++; continue;
            }
            const word = expr.slice(i).match(/^(NF|NR)/);
            if (word) {
                out += String(word[1] === 'NF' ? fields.length : nr);
                i += word[0].length;
                continue;
            }
            out += ch;
            i++;
        }
        return out;
    }

    /** 展开字符集：a-z、0-9 */
    function expandSet(spec) {
        let out = '';
        for (let i = 0; i < spec.length; i++) {
            if (i + 2 < spec.length && spec[i + 1] === '-') {
                const from = spec.charCodeAt(i);
                const to = spec.charCodeAt(i + 2);
                for (let c = from; c <= to; c++) out += String.fromCharCode(c);
                i += 2;
                continue;
            }
            out += spec[i];
        }
        return out;
    }

    const api = {
        register: register,
        registerAll: registerAll,
        get: get,
        has: has,
        names: names,
        list: list,
        run: run,
        tokenize: tokenize,
        splitPipeline: splitPipeline,
        parseArgs: parseArgs,
        splitLines: splitLines
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    if (global) global.TextShell = api;
})(typeof globalThis !== 'undefined' ? globalThis : (typeof window !== 'undefined' ? window : this));
