/**
 * JSON 路径提取（零依赖）
 *
 * 语法（兼容旧的「JSONPath」与「字段路径」两种写法）：
 *   $.a.b      / a.b        取嵌套字段（开头的 $ 和 $. 可省略）
 *   a[0] / [0] / a[0][1]    数组下标，从 0 开始
 *   *                       通配：数组取所有元素，对象取所有值
 *   name:正则               过滤，如 data.*.name:/^A/ 或 data.*.name:^A
 *
 * 返回所有命中的值组成的数组；没命中返回空数组。
 *
 * 双挂载：浏览器 window.JSONPath，Node 下 module.exports。
 */
(function (global) {
    'use strict';

    /** 把过滤片段（:/^A/i 或 :^A）编译成 RegExp；无法编译时返回 null */
    function parseFilter(src) {
        src = String(src == null ? '' : src).trim();
        if (!src) return null;
        try {
            const literal = src.match(/^\/([\s\S]*)\/([gimsuy]*)$/);
            return literal ? new RegExp(literal[1], literal[2]) : new RegExp(src);
        } catch (e) {
            return null;
        }
    }

    /**
     * 解析单段路径
     * @param {string} raw 例如 'users[0]'、'*'、'[1]'、'name:/^A/'
     * @returns {{key: string|null, indexes: Array, filter: RegExp|null}}
     */
    function parseSegment(raw) {
        let s = String(raw == null ? '' : raw).trim();
        let filter = null;

        // 优先按字面量形式切分（正则里可能带冒号）：key:/re/flags
        const literal = s.match(/^([\s\S]*?):(\/[\s\S]+\/[gimsuy]*)$/);
        if (literal) {
            filter = parseFilter(literal[2]);
            s = literal[1];
        } else {
            const colon = s.indexOf(':');
            if (colon !== -1) {
                filter = parseFilter(s.slice(colon + 1));
                s = s.slice(0, colon);
            }
        }

        const keyMatch = s.match(/^[^\[\]]*/);
        const rawKey = keyMatch ? keyMatch[0] : '';
        const key = rawKey.trim();
        const indexes = [];
        const re = /\[([^\[\]]*)\]/g;
        let m;
        while ((m = re.exec(s.slice(rawKey.length))) !== null) {
            const token = m[1].trim();
            if (token === '*') {
                indexes.push({ type: 'wildcard' });
            } else if (/^\d+$/.test(token)) {
                indexes.push({ type: 'index', value: parseInt(token, 10) });
            } else {
                throw new Error('不支持的数组下标：[' + token + ']');
            }
        }

        if (key === '' && indexes.length === 0) {
            throw new Error('路径格式错误：空片段');
        }

        return { key: key === '' ? null : key, indexes: indexes, filter: filter };
    }

    /**
     * 解析完整路径
     * @param {string} path
     * @returns {Array} 片段数组；根路径（''、'$'）返回空数组
     */
    function parsePath(path) {
        let p = String(path == null ? '' : path).trim();
        if (!p || p === '$') return [];
        p = p.replace(/^\$\.?/, '');
        if (!p) return [];
        return p.split('.').map(parseSegment);
    }

    /** 通配展开：数组取元素，对象取值，其它为空 */
    function expand(node) {
        if (Array.isArray(node)) return node.slice();
        if (node && typeof node === 'object') return Object.keys(node).map(k => node[k]);
        return [];
    }

    /** 取属性；不存在时返回空数组（不区分 undefined 与缺失） */
    function getProp(node, key) {
        if (node && typeof node === 'object' && Object.prototype.hasOwnProperty.call(node, key)) {
            return [node[key]];
        }
        return [];
    }

    function collect(node, segments, index, out) {
        if (index === segments.length) {
            out.push(node);
            return;
        }

        const seg = segments[index];
        let candidates;
        if (seg.key === null) candidates = [node];
        else if (seg.key === '*') candidates = expand(node);
        else candidates = getProp(node, seg.key);

        for (const candidate of candidates) {
            let values = [candidate];

            for (const idx of seg.indexes) {
                const next = [];
                for (const v of values) {
                    if (idx.type === 'wildcard') next.push(...expand(v));
                    else if (Array.isArray(v) && idx.value < v.length) next.push(v[idx.value]);
                }
                values = next;
            }

            if (seg.filter) {
                values = values.filter(v => seg.filter.test(String(v)));
            }

            for (const v of values) collect(v, segments, index + 1, out);
        }
    }

    /**
     * 按路径提取
     * @param {*} obj 已解析的 JSON 对象
     * @param {string} path 路径表达式
     * @returns {Array} 命中值的数组，未命中为空数组
     */
    function extract(obj, path) {
        const segments = parsePath(path);
        if (segments.length === 0) return [obj];
        const out = [];
        collect(obj, segments, 0, out);
        return out;
    }

    const api = { parsePath: parsePath, parseSegment: parseSegment, extract: extract };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
    if (global) {
        global.JSONPath = api;
    }
})(typeof globalThis !== 'undefined' ? globalThis : (typeof window !== 'undefined' ? window : this));
