/**
 * json-int64.js — 支持 int64 的 JSON 解析与序列化
 *
 * 问题背景：
 *   浏览器/JS 原生的 JSON.parse 会把所有数字解析为 IEEE-754 Number，
 *   整数一旦超过 2^53 (Number.MAX_SAFE_INTEGER) 就会丢失精度，
 *   典型的 int64 值（如 9223372036854775807）会被悄悄篡改。
 *
 * 本模块：
 *   - parse(text)   与 JSON.parse 兼容；整数值在超出安全范围时用 BigInt 保存，
 *                   其余数字、字符串、布尔、null、对象、数组行为与原生一致。
 *   - stringify(v) 与 JSON.stringify 兼容；BigInt 以无引号的纯整数字面量输出，
 *                   因此序列化结果仍是合法 JSON，可被任意 JSON 解析器读取。
 *
 * 零外部依赖，纯 JS 实现，可直接复制到任意项目使用。
 *
 * 暴露方式：
 *   浏览器：window.JSONInt64 = { parse, stringify }
 *   Node  ：module.exports = JSONInt64
 */
(function (global) {
    'use strict';

    var MAX_SAFE = '9007199254740991'; // Number.MAX_SAFE_INTEGER 的字符串形式

    // 判断一个整数（不允许出现 . 或 e/E）是否在 Number 安全范围内
    function isSafeInteger(raw) {
        var abs = raw.charAt(0) === '-' ? raw.slice(1) : raw;
        if (abs.length < 16) return true;          // <= 15 位数字一定安全
        if (abs.length === 16) return abs <= MAX_SAFE; // 16 位需逐位比较
        return false;                              // > 16 位一定不安全
    }

    function parse(text) {
        if (typeof text !== 'string' && !(text instanceof String)) {
            text = String(text);
        }
        var src = text;
        var i = 0;
        var n = src.length;

        function skipWs() {
            while (i < n) {
                var c = src.charCodeAt(i);
                // 空格、制表、换行、回车
                if (c === 0x20 || c === 0x09 || c === 0x0a || c === 0x0d) {
                    i++;
                } else {
                    break;
                }
            }
        }

        function parseValue() {
            skipWs();
            if (i >= n) throw new Error('JSON 输入意外结束');
            var c = src.charAt(i);
            if (c === '{') return parseObject();
            if (c === '[') return parseArray();
            if (c === '"') return parseString();
            if (c === '-' || (c >= '0' && c <= '9')) return parseNumber();
            if (c === 't') return parseLiteral('true', true);
            if (c === 'f') return parseLiteral('false', false);
            if (c === 'n') return parseLiteral('null', null);
            throw new Error('位置 ' + i + ' 出现非法字符 ' + JSON.stringify(c));
        }

        function parseLiteral(lit, val) {
            if (src.substr(i, lit.length) === lit) {
                i += lit.length;
                return val;
            }
            throw new Error('位置 ' + i + ' 出现非法字面量');
        }

        function parseObject() {
            i++; // 跳过 {
            var obj = {};
            skipWs();
            if (i < n && src.charAt(i) === '}') { i++; return obj; }
            while (true) {
                skipWs();
                if (src.charAt(i) !== '"') throw new Error('位置 ' + i + ' 期望字符串形式的键');
                var key = parseString();
                skipWs();
                if (src.charAt(i) !== ':') throw new Error('位置 ' + i + ' 期望 ":"');
                i++;
                obj[key] = parseValue();
                skipWs();
                if (i >= n) throw new Error('JSON 输入意外结束');
                if (src.charAt(i) === ',') { i++; continue; }
                if (src.charAt(i) === '}') { i++; break; }
                throw new Error('位置 ' + i + ' 期望 "," 或 "}"');
            }
            return obj;
        }

        function parseArray() {
            i++; // 跳过 [
            var arr = [];
            skipWs();
            if (i < n && src.charAt(i) === ']') { i++; return arr; }
            while (true) {
                arr.push(parseValue());
                skipWs();
                if (i >= n) throw new Error('JSON 输入意外结束');
                if (src.charAt(i) === ',') { i++; continue; }
                if (src.charAt(i) === ']') { i++; break; }
                throw new Error('位置 ' + i + ' 期望 "," 或 "]"');
            }
            return arr;
        }

        function parseString() {
            i++; // 跳过起始 "
            var result = '';
            while (i < n) {
                var c = src.charAt(i);
                if (c === '"') { i++; return result; }
                if (c === '\\') {
                    i++;
                    if (i >= n) throw new Error('转义字符未结束');
                    var e = src.charAt(i);
                    i++;
                    switch (e) {
                        case '"': result += '"'; break;
                        case '\\': result += '\\'; break;
                        case '/': result += '/'; break;
                        case 'b': result += '\b'; break;
                        case 'f': result += '\f'; break;
                        case 'n': result += '\n'; break;
                        case 'r': result += '\r'; break;
                        case 't': result += '\t'; break;
                        case 'u':
                            if (i + 4 > n) throw new Error('非法的 Unicode 转义');
                            var hex = src.substr(i, 4);
                            if (!/^[0-9a-fA-F]{4}$/.test(hex)) {
                                throw new Error('非法的 Unicode 转义');
                            }
                            var cp = parseInt(hex, 16);
                            i += 4;
                            // 处理 UTF-16 代理对
                            if (cp >= 0xD800 && cp <= 0xDBFF) {
                                if (i + 6 <= n && src.charAt(i) === '\\' && src.charAt(i + 1) === 'u') {
                                    var hex2 = src.substr(i + 2, 4);
                                    if (/^[0-9a-fA-F]{4}$/.test(hex2)) {
                                        var cp2 = parseInt(hex2, 16);
                                        if (cp2 >= 0xDC00 && cp2 <= 0xDFFF) {
                                            cp = 0x10000 + ((cp - 0xD800) << 10) + (cp2 - 0xDC00);
                                            i += 6;
                                        }
                                    }
                                }
                            }
                            result += String.fromCodePoint(cp);
                            break;
                        default:
                            throw new Error('非法的转义字符 \\' + e);
                    }
                } else {
                    result += c;
                    i++;
                }
            }
            throw new Error('字符串未结束');
        }

        function parseNumber() {
            var start = i;
            if (src.charAt(i) === '-') i++;
            while (i < n && src.charAt(i) >= '0' && src.charAt(i) <= '9') i++;
            var isFloat = false;
            if (i < n && src.charAt(i) === '.') {
                isFloat = true;
                i++;
                while (i < n && src.charAt(i) >= '0' && src.charAt(i) <= '9') i++;
            }
            if (i < n && (src.charAt(i) === 'e' || src.charAt(i) === 'E')) {
                isFloat = true;
                i++;
                if (i < n && (src.charAt(i) === '+' || src.charAt(i) === '-')) i++;
                while (i < n && src.charAt(i) >= '0' && src.charAt(i) <= '9') i++;
            }
            var raw = src.substring(start, i);
            if (!isFloat) {
                if (isSafeInteger(raw)) {
                    return parseInt(raw, 10);
                }
                // 超出安全范围的整型 → BigInt（int64 / uint64 等）
                try {
                    return BigInt(raw);
                } catch (err) {
                    return Number(raw); // 极端非法输入兜底
                }
            }
            return Number(raw);
        }

        var result = parseValue();
        skipWs();
        if (i < n) {
            throw new Error('位置 ' + i + ' 之后存在多余字符');
        }
        return result;
    }

    function quoteString(s) {
        return '"' + s
            .replace(/[\\"]/g, '\\$&')
            .replace(/[\u0000-\u001f]/g, function (c) {
                switch (c) {
                    case '\b': return '\\b';
                    case '\f': return '\\f';
                    case '\n': return '\\n';
                    case '\r': return '\\r';
                    case '\t': return '\\t';
                    default:
                        return '\\u' + ('0000' + c.charCodeAt(0).toString(16)).slice(-4);
                }
            }) + '"';
    }

    function stringify(value, replacer, space) {
        var indent = '';
        if (typeof space === 'number' && space > 0) {
            indent = ' '.repeat(Math.min(space, 10));
        } else if (typeof space === 'string' && space.length > 0) {
            indent = space.slice(0, 10);
        }

        function serialize(v, key, level) {
            if (typeof replacer === 'function') {
                v = replacer.call(null, key, v);
            }

            if (v === null) return 'null';
            if (v === undefined) return undefined;

            var t = typeof v;
            if (t === 'bigint') return String(v); // 无引号纯整数字面量
            if (t === 'number') {
                if (!isFinite(v)) return 'null';  // 与原生 JSON.stringify 行为一致
                return String(v);
            }
            if (t === 'boolean') return String(v);
            if (t === 'string') return quoteString(v);

            var gap = indent === '' ? '' : indent.repeat(level);
            var childGap = indent === '' ? '' : indent.repeat(level + 1);
            // 与原生 JSON.stringify 一致：无缩进时冒号后不加空格
            var colon = indent === '' ? ':' : ': ';

            if (Array.isArray(v)) {
                if (v.length === 0) return '[]';
                var arrParts = [];
                for (var a = 0; a < v.length; a++) {
                    var av = serialize(v[a], a, level + 1);
                    arrParts.push(childGap + (av === undefined ? 'null' : av));
                }
                return indent === ''
                    ? '[' + arrParts.join(',') + ']'
                    : '[\n' + arrParts.join(',\n') + '\n' + gap + ']';
            }

            if (t === 'object') {
                var keys = Object.keys(v);
                if (keys.length === 0) return '{}';
                var objParts = [];
                for (var k = 0; k < keys.length; k++) {
                    var ov = serialize(v[keys[k]], keys[k], level + 1);
                    if (ov === undefined) continue; // 跳过 undefined 值
                    objParts.push(childGap + quoteString(keys[k]) + colon + ov);
                }
                return indent === ''
                    ? '{' + objParts.join(',') + '}'
                    : '{\n' + objParts.join(',\n') + '\n' + gap + '}';
            }

            return undefined; // 函数等不可序列化类型
        }

        var out = serialize(value, '', 0);
        return out === undefined ? undefined : out;
    }

    var JSONInt64 = { parse: parse, stringify: stringify };

    // 浏览器全局
    if (typeof global !== 'undefined') {
        global.JSONInt64 = JSONInt64;
    }
    // Node 模块导出（便于测试）
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = JSONInt64;
    }

    return JSONInt64;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
