/**
 * json-embedded.js — 自动解析字符串中的 JSON 字段
 *
 * 很多接口返回的 JSON 里，某些字段值是「字符串形式」的 JSON（被转义或包裹），
 * 例如:
 *   { "payload": "{\\"a\\":1,\\"b\\":[1,2,3]}", "list": "[1,2,3]" }
 *
 * 本模块把这类字符串字段递归地解析成真正的嵌套结构。
 *
 * 设计约束:
 *   - 默认只转换「以 { 或 [ 开头」的字符串（对象/数组 JSON），
 *     避免把 "123" / "true" 这类裸值意外转成数字/布尔。
 *   - 解析后对每个结果继续递归，从而解开多层嵌套的字符串 JSON。
 *   - 复用 JSONInt64 进行解析，保证 int64 不丢精度。
 *
 * 零外部依赖（仅在 Node 下 require json-int64.js）。
 *
 * 暴露方式:
 *   浏览器：window.JSONEmbedded = { parseEmbeddedJson }
 *   Node  ：module.exports  = { parseEmbeddedJson }
 */
(function (global) {
    'use strict';

    // 浏览器中由 json-int64.js 注入全局 JSONInt64；Node 下回退到 require
    var JSONInt64 = (typeof global !== 'undefined' && global.JSONInt64)
        ? global.JSONInt64
        : (typeof require !== 'undefined' ? require('./json-int64.js') : null);

    /**
     * 递归地把对象/数组中「值为字符串 JSON」的字段解析成嵌套结构。
     * @param {*} value 任意已解析的 JSON 值
     * @returns {*} 解析后的新值（不会原地修改入参）
     */
    function parseEmbeddedJson(value) {
        // 字符串：尝试作为 JSON 解析（仅当看起来是对象/数组时）
        if (typeof value === 'string') {
            var trimmed = value.trim();
            if (trimmed.charAt(0) === '{' || trimmed.charAt(0) === '[') {
                try {
                    var parsed = JSONInt64.parse(trimmed);
                    // 对解析结果继续递归，解开多层嵌套
                    return parseEmbeddedJson(parsed);
                } catch (e) {
                    // 不是合法 JSON，原样保留
                    return value;
                }
            }
            return value;
        }

        // 数组：逐元素递归
        if (Array.isArray(value)) {
            return value.map(parseEmbeddedJson);
        }

        // 普通对象：逐字段递归
        if (value && typeof value === 'object') {
            var out = {};
            var keys = Object.keys(value);
            for (var i = 0; i < keys.length; i++) {
                out[keys[i]] = parseEmbeddedJson(value[keys[i]]);
            }
            return out;
        }

        // 数字 / 布尔 / null 等原样返回
        return value;
    }

    var api = { parseEmbeddedJson: parseEmbeddedJson };

    if (typeof global !== 'undefined') {
        global.JSONEmbedded = api;
        // 同时挂一个裸全局函数，方便页面直接调用（与 json.js 的 extractAllJSONFromText 一致）
        global.parseEmbeddedJson = parseEmbeddedJson;
    }
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }

    return api;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
