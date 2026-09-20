/**
 * text-codec.js — 常见文本编解码（零外部依赖）
 *
 * 支持的编解码器：
 *   url      URL 百分号编码（encodeURIComponent / encodeURI）
 *   base64   Base64（按 UTF-8 字节编码，正确处理中文/emoji；可选 URL 安全字符集）
 *   html     HTML 实体（&amp; &lt; 等命名实体与 &#123; &#x1F600; 数字实体）
 *   unicode  Unicode 转义（\uXXXX，支持代理对与 \u{...} / \xXX）
 *   hex      十六进制（按 UTF-8 字节转为 16 进制串）
 *   json     JSON 字符串转义（\n \" 等）
 *
 * 每个编解码器形如：
 *   { id, name, encode(text, opts), decode(text, opts), options: [...], sample }
 * options 用于驱动页面上的动态选项，形如：
 *   { id, label, type: 'checkbox', default: false }
 *
 * 暴露方式：
 *   浏览器：window.TextCodec
 *   Node  ：module.exports
 *
 * 注意：加解码失败时统一抛出带中文说明的 Error，页面会捕获并展示。
 */
(function (global) {
    'use strict';

    // ============================================================
    // 基础：UTF-8 字节转换
    // ============================================================

    /** 字符串 -> UTF-8 字节数组 */
    function utf8Encode(str) {
        if (typeof TextEncoder !== 'undefined') {
            try {
                return new TextEncoder().encode(str);
            } catch (e) { /* 降级到手写实现 */ }
        }
        var bytes = [];
        for (var i = 0; i < str.length; i++) {
            var cp = str.charCodeAt(i);
            // 高代理项：拼成完整码点
            if (cp >= 0xD800 && cp <= 0xDBFF && i + 1 < str.length) {
                var lo = str.charCodeAt(i + 1);
                if (lo >= 0xDC00 && lo <= 0xDFFF) {
                    cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
                    i++;
                } else {
                    cp = 0xFFFD; // 孤立高代理项
                }
            } else if (cp >= 0xD800 && cp <= 0xDFFF) {
                cp = 0xFFFD; // 孤立代理项
            }
            if (cp < 0x80) {
                bytes.push(cp);
            } else if (cp < 0x800) {
                bytes.push(0xC0 | (cp >> 6), 0x80 | (cp & 0x3F));
            } else if (cp < 0x10000) {
                bytes.push(0xE0 | (cp >> 12), 0x80 | ((cp >> 6) & 0x3F), 0x80 | (cp & 0x3F));
            } else {
                bytes.push(
                    0xF0 | (cp >> 18),
                    0x80 | ((cp >> 12) & 0x3F),
                    0x80 | ((cp >> 6) & 0x3F),
                    0x80 | (cp & 0x3F)
                );
            }
        }
        return new Uint8Array(bytes);
    }

    /** UTF-8 字节数组 -> 字符串（非法序列替换为 U+FFFD） */
    function utf8Decode(bytes) {
        if (typeof TextDecoder !== 'undefined') {
            try {
                return new TextDecoder('utf-8', { fatal: false }).decode(bytes);
            } catch (e) { /* 降级到手写实现 */ }
        }
        var out = '';
        var i = 0;
        var n = bytes.length;
        function next() { return i < n ? bytes[i++] : 0; }
        while (i < n) {
            var b = bytes[i++];
            var cp;
            if (b < 0x80) {
                cp = b;
            } else if (b >= 0xC0 && b < 0xE0) {
                cp = ((b & 0x1F) << 6) | (next() & 0x3F);
            } else if (b >= 0xE0 && b < 0xF0) {
                cp = ((b & 0x0F) << 12) | (next() << 6 & 0xFC0) | (next() & 0x3F);
            } else if (b >= 0xF0 && b < 0xF8) {
                cp = ((b & 0x07) << 18) | ((next() & 0x3F) << 12) | ((next() & 0x3F) << 6) | (next() & 0x3F);
            } else {
                cp = 0xFFFD;
            }
            out += String.fromCodePoint ? String.fromCodePoint(cp) : String.fromCharCode(cp);
        }
        return out;
    }

    // ============================================================
    // 基础：Base64 / Hex
    // ============================================================

    function bytesToBase64(bytes) {
        if (typeof Buffer !== 'undefined') {
            return Buffer.from(bytes).toString('base64');
        }
        var bin = '';
        var CHUNK = 0x8000; // 分块避免 apply 参数过多
        for (var i = 0; i < bytes.length; i += CHUNK) {
            bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
        }
        return btoa(bin);
    }

    function base64ToBytes(b64) {
        if (typeof Buffer !== 'undefined') {
            var buf = Buffer.from(b64, 'base64');
            // Buffer 会忽略非法字符，这里简单校验字符集
            if (!/^[A-Za-z0-9+/=_-]*$/.test(b64)) {
                throw new Error('Base64 输入包含非法字符');
            }
            return new Uint8Array(buf);
        }
        if (!/^[A-Za-z0-9+/=_-]*$/.test(b64)) {
            throw new Error('Base64 输入包含非法字符');
        }
        var bin;
        try {
            bin = atob(b64);
        } catch (e) {
            throw new Error('Base64 格式不正确，无法解码');
        }
        var out = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
        return out;
    }

    function bytesToHex(bytes, opts) {
        var upper = !!(opts && opts.uppercase);
        var spaced = !!(opts && opts.spaced);
        var parts = [];
        for (var i = 0; i < bytes.length; i++) {
            var h = bytes[i].toString(16);
            if (upper) h = h.toUpperCase();
            else h = h.toLowerCase();
            parts.push(h.length === 1 ? '0' + h : h);
        }
        return parts.join(spaced ? ' ' : '');
    }

    function hexToBytes(hex) {
        var clean = String(hex).replace(/[\s,:]/g, '');
        if (clean === '') return new Uint8Array(0);
        if (!/^[0-9a-fA-F]+$/.test(clean)) {
            throw new Error('十六进制输入包含非法字符（只允许 0-9 / a-f）');
        }
        if (clean.length % 2 !== 0) {
            throw new Error('十六进制长度必须为偶数（每两个字符表示一个字节）');
        }
        var out = new Uint8Array(clean.length / 2);
        for (var i = 0; i < out.length; i++) {
            out[i] = parseInt(clean.substr(i * 2, 2), 16);
        }
        return out;
    }

    // ============================================================
    // HTML 实体
    // ============================================================

    var HTML_ESCAPE_MAP = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    };

    // 常见命名实体（解码用）— 覆盖 HTML4 中最常用的一批
    var HTML_NAMED_ENTITIES = {
        amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: '\u00A0',
        iexcl: '\u00A1', cent: '\u00A2', pound: '\u00A3', curren: '\u00A4',
        yen: '\u00A5', brvbar: '\u00A6', sect: '\u00A7', uml: '\u00A8',
        copy: '\u00A9', ordf: '\u00AA', laquo: '\u00AB', not: '\u00AC',
        reg: '\u00AE', macr: '\u00AF', deg: '\u00B0', plusmn: '\u00B1',
        sup2: '\u00B2', sup3: '\u00B3', acute: '\u00B4', micro: '\u00B5',
        para: '\u00B6', middot: '\u00B7', cedil: '\u00B8', sup1: '\u00B9',
        ordm: '\u00BA', raquo: '\u00BB', frac14: '\u00BC', frac12: '\u00BD',
        frac34: '\u00BE', iquest: '\u00BF',
        Agrave: '\u00C0', Aacute: '\u00C1', Acirc: '\u00C2', Atilde: '\u00C3',
        Auml: '\u00C4', Aring: '\u00C5', AElig: '\u00C6', Ccedil: '\u00C7',
        Egrave: '\u00C8', Eacute: '\u00C9', Ecirc: '\u00CA', Euml: '\u00CB',
        Igrave: '\u00CC', Iacute: '\u00CD', Icirc: '\u00CE', Iuml: '\u00CF',
        ETH: '\u00D0', Ntilde: '\u00D1', Ograve: '\u00D2', Oacute: '\u00D3',
        Ocirc: '\u00D4', Otilde: '\u00D5', Ouml: '\u00D6', times: '\u00D7',
        Oslash: '\u00D8', Ugrave: '\u00D9', Uacute: '\u00DA', Ucirc: '\u00DB',
        Uuml: '\u00DC', Yacute: '\u00DD', THORN: '\u00DE', szlig: '\u00DF',
        agrave: '\u00E0', aacute: '\u00E1', acirc: '\u00E2', atilde: '\u00E3',
        auml: '\u00E4', aring: '\u00E5', aelig: '\u00E6', ccedil: '\u00E7',
        egrave: '\u00E8', eacute: '\u00E9', ecirc: '\u00EA', euml: '\u00EB',
        igrave: '\u00EC', iacute: '\u00ED', icirc: '\u00EE', iuml: '\u00EF',
        eth: '\u00F0', ntilde: '\u00F1', ograve: '\u00F2', oacute: '\u00F3',
        ocirc: '\u00F4', otilde: '\u00F5', ouml: '\u00F6', divide: '\u00F7',
        oslash: '\u00F8', ugrave: '\u00F9', uacute: '\u00FA', ucirc: '\u00FB',
        uuml: '\u00FC', yacute: '\u00FD', thorn: '\u00FE', yuml: '\u00FF',
        // 常用符号
        hellip: '\u2026', prime: '\u2032', Prime: '\u2033', oline: '\u203E',
        euro: '\u20AC', trade: '\u2122', larr: '\u2190', uarr: '\u2191',
        rarr: '\u2192', darr: '\u2193', harr: '\u2194', crarr: '\u21B5',
        lArr: '\u21D0', uArr: '\u21D1', rArr: '\u21D2', dArr: '\u21D3',
        forall: '\u2200', part: '\u2202', empty: '\u2205', isin: '\u2208',
        notin: '\u2209', sum: '\u2211', radic: '\u221A', prop: '\u221D',
        infin: '\u221E', and: '\u2227', or: '\u2228', cap: '\u2229',
        cup: '\u222A', ne: '\u2260', equiv: '\u2261', le: '\u2264',
        ge: '\u2265', sub: '\u2282', sup: '\u2283', nsub: '\u2284',
        spades: '\u2660', clubs: '\u2663', hearts: '\u2665', diams: '\u2666'
    };

    /** HTML 实体编码 */
    function htmlEncode(text, opts) {
        var all = !!(opts && opts.encodeAll);
        if (!all) {
            return String(text).replace(/[&<>"']/g, function (ch) {
                return HTML_ESCAPE_MAP[ch];
            });
        }
        // 全部非 ASCII 与特殊字符转为数字实体
        var out = '';
        var str = String(text);
        for (var i = 0; i < str.length; i++) {
            var ch = str[i];
            if (/[a-zA-Z0-9 ]/.test(ch)) {
                out += ch;
            } else if (HTML_ESCAPE_MAP[ch]) {
                out += HTML_ESCAPE_MAP[ch];
            } else {
                out += '&#' + str.charCodeAt(i) + ';';
            }
        }
        return out;
    }

    /** HTML 实体解码 */
    function htmlDecode(text) {
        return String(text).replace(/&(#x[0-9a-fA-F]+|#[0-9]+|[a-zA-Z][a-zA-Z0-9]*);/g,
            function (match, body) {
                if (body.charAt(0) === '#') {
                    var isHex = body.charAt(1) === 'x' || body.charAt(1) === 'X';
                    var cp = parseInt(isHex ? body.slice(2) : body.slice(1), isHex ? 16 : 10);
                    if (isNaN(cp) || cp < 0 || cp > 0x10FFFF) return match;
                    return String.fromCodePoint ? String.fromCodePoint(cp) : String.fromCharCode(cp);
                }
                if (Object.prototype.hasOwnProperty.call(HTML_NAMED_ENTITIES, body)) {
                    return HTML_NAMED_ENTITIES[body];
                }
                return match; // 未识别的实体原样保留
            });
    }

    // ============================================================
    // Unicode 转义
    // ============================================================

    function pad4(h) {
        return ('0000' + h).slice(-4);
    }

    /** Unicode 转义：非 ASCII 默认转为 \uXXXX */
    function unicodeEncode(text, opts) {
        var onlyNonAscii = !(opts && opts.escapeAllChars); // 默认只转义非 ASCII
        var upper = !(opts && opts.lowercaseHex);
        var out = '';
        var str = String(text);
        for (var i = 0; i < str.length; i++) {
            var ch = str[i];
            var cp = str.charCodeAt(i);
            var lo = i + 1 < str.length ? str.charCodeAt(i + 1) : 0;
            // 代理对（如 emoji）：按 \uXXXX\uXXXX 成对输出，兼容性最好
            if (cp >= 0xD800 && cp <= 0xDBFF && lo >= 0xDC00 && lo <= 0xDFFF) {
                out += '\\u' + fmtHex(pad4(cp.toString(16)), upper) +
                    '\\u' + fmtHex(pad4(lo.toString(16)), upper);
                i++;
                continue;
            }
            if (onlyNonAscii && cp < 128) {
                out += ch;
                continue;
            }
            out += '\\u' + fmtHex(pad4(cp.toString(16)), upper);
        }
        return out;
    }

    function fmtHex(h, upper) {
        return upper ? h.toUpperCase() : h.toLowerCase();
    }

    /** Unicode 反转义：支持 \uXXXX、\u{...}、\xXX */
    function unicodeDecode(text) {
        return String(text).replace(
            /\\u\{([0-9a-fA-F]+)\}|\\u([0-9a-fA-F]{4})|\\x([0-9a-fA-F]{2})/g,
            function (match, braced, u4, x2) {
                var cp = parseInt(braced || u4 || x2, 16);
                if (isNaN(cp) || cp > 0x10FFFF) return match;
                return String.fromCodePoint ? String.fromCodePoint(cp) : String.fromCharCode(cp);
            }
        );
    }

    // ============================================================
    // 编解码器注册表
    // ============================================================

    var CODECS = [
        {
            id: 'url',
            name: 'URL 编码',
            placeholder: 'https://example.com/搜索?q=a b',
            sample: 'https://example.com/搜索?q=你好 world',
            options: [
                { id: 'keepStructure', label: '保留 URL 结构（用 encodeURI，不转义 : / ? & 等）', type: 'checkbox', default: false }
            ],
            encode: function (text, opts) {
                return opts && opts.keepStructure ? encodeURI(text) : encodeURIComponent(text);
            },
            decode: function (text) {
                try {
                    return decodeURIComponent(String(text).replace(/\+/g, ' '));
                } catch (e) {
                    throw new Error('URL 解码失败：输入的百分号编码格式不正确');
                }
            }
        },
        {
            id: 'base64',
            name: 'Base64',
            placeholder: '待编码的文本 / 待解码的 Base64',
            sample: '你好，Duck Rush!',
            options: [
                { id: 'urlSafe', label: 'URL 安全字符集（+ / 替换为 - _，去掉 = 补位）', type: 'checkbox', default: false }
            ],
            encode: function (text, opts) {
                var b64 = bytesToBase64(utf8Encode(String(text)));
                if (opts && opts.urlSafe) {
                    b64 = b64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
                }
                return b64;
            },
            decode: function (text, opts) {
                var b64 = String(text).trim();
                if (opts && opts.urlSafe) {
                    b64 = b64.replace(/-/g, '+').replace(/_/g, '/');
                    while (b64.length % 4 !== 0) b64 += '=';
                }
                return utf8Decode(base64ToBytes(b64));
            }
        },
        {
            id: 'html',
            name: 'HTML 实体',
            placeholder: '<div class="a">文本 & 符号</div>',
            sample: '<div class="tip">你好 & "world"</div>',
            options: [
                { id: 'encodeAll', label: '转义全部非字母数字字符（输出数字实体）', type: 'checkbox', default: false }
            ],
            encode: htmlEncode,
            decode: htmlDecode
        },
        {
            id: 'unicode',
            name: 'Unicode 转义',
            placeholder: '中文 → \\u4E2D\\u6587',
            sample: '你好 😀 Duck',
            options: [
                { id: 'escapeAllChars', label: '同时转义 ASCII 字符', type: 'checkbox', default: false },
                { id: 'lowercaseHex', label: '十六进制用小写（\\u4e2d）', type: 'checkbox', default: false }
            ],
            encode: unicodeEncode,
            decode: unicodeDecode
        },
        {
            id: 'hex',
            name: '十六进制 Hex',
            placeholder: 'e4bda0e5a5bd',
            sample: '你好 Duck',
            options: [
                { id: 'uppercase', label: '大写十六进制', type: 'checkbox', default: false },
                { id: 'spaced', label: '字节之间加空格', type: 'checkbox', default: false }
            ],
            encode: function (text, opts) {
                return bytesToHex(utf8Encode(String(text)), opts);
            },
            decode: function (text) {
                return utf8Decode(hexToBytes(text));
            }
        },
        {
            id: 'json',
            name: 'JSON 转义',
            placeholder: '第一行\\n第二行 "引号"',
            sample: '第一行\n第二行 "引号" \\ 反斜杠',
            options: [],
            encode: function (text) {
                // JSON.stringify 会在首尾加引号，这里只取中间的转义内容
                return JSON.stringify(String(text)).slice(1, -1);
            },
            decode: function (text) {
                try {
                    return JSON.parse('"' + String(text) + '"');
                } catch (e) {
                    throw new Error('JSON 反转义失败：输入的转义序列不合法');
                }
            }
        }
    ];

    var CODEC_MAP = {};
    CODECS.forEach(function (c) { CODEC_MAP[c.id] = c; });

    function getCodec(id) {
        var codec = CODEC_MAP[id];
        if (!codec) throw new Error('未知的编解码类型：' + id);
        return codec;
    }

    /** 统一入口：direction 为 'encode' 或 'decode' */
    function transform(id, text, direction, options) {
        var codec = getCodec(id);
        var fn = direction === 'decode' ? codec.decode : codec.encode;
        if (typeof fn !== 'function') throw new Error(codec.name + ' 不支持该操作');
        return fn(text, options || {});
    }

    var TextCodec = {
        codecs: CODECS,
        getCodec: getCodec,
        encode: function (id, text, options) { return transform(id, text, 'encode', options); },
        decode: function (id, text, options) { return transform(id, text, 'decode', options); },
        transform: transform,
        // 导出底层工具便于测试
        utf8Encode: utf8Encode,
        utf8Decode: utf8Decode
    };

    if (typeof global !== 'undefined') {
        global.TextCodec = TextCodec;
    }
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = TextCodec;
    }

    return TextCodec;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
