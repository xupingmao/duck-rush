/**
 * json-int64.js 单元测试（仅依赖标准库）
 * 运行: node duck_rush/web-tools/js/json-int64.test.js
 */

const path = require('path');
const JSONInt64 = require(path.resolve(__dirname, 'json-int64.js'));

const { parse, stringify } = JSONInt64;

let passed = 0, failed = 0;
const errors = [];

function assert(cond, msg) {
    if (cond) { passed++; }
    else { failed++; errors.push(msg); console.log('  FAIL:', msg); }
}

/** 比较时统一把 bigint 转成带 n 后缀的字符串，避免 === 误判 */
function norm(v) {
    return typeof v === 'bigint' ? v.toString() + 'n' : JSON.stringify(v);
}

function eq(name, got, expected) {
    assert(norm(got) === norm(expected),
        name + ' => ' + norm(got) + ' (expected ' + norm(expected) + ')');
}

const MAX_INT64 = '9223372036854775807';
const MIN_INT64 = '-9223372036854775808';
const MAX_UINT64 = '18446744073709551615';

console.log('=== int64 精确保留 ===');
eq('int64 最大值', parse(MAX_INT64), BigInt(MAX_INT64));
eq('int64 最小值', parse(MIN_INT64), BigInt(MIN_INT64));
eq('uint64 最大值', parse(MAX_UINT64), BigInt(MAX_UINT64));
eq('对象内 int64', parse('{"id":' + MAX_INT64 + '}').id, BigInt(MAX_INT64));
eq('数组内 int64', parse('[1,' + MAX_INT64 + ',3]')[1], BigInt(MAX_INT64));
eq('嵌套 int64', parse('{"a":{"b":[' + MIN_INT64 + ']}}').a.b[0], BigInt(MIN_INT64));
eq('负号整数 -1', parse('-1'), -1);

console.log('\n=== 与原生 JSON 的边界 ===');
eq('安全范围内仍是 number', parse('9007199254740991'), 9007199254740991);
eq('NS_MAX+1 转 bigint', parse('9007199254740992'), BigInt('9007199254740992'));
eq('-(NS_MAX+1) 转 bigint', parse('-9007199254740992'), BigInt('-9007199254740992'));
eq('浮点数不变', parse('3.14'), 3.14);
eq('科学计数法', parse('1.5e10'), 1.5e10);
eq('负零', parse('-0'), -0);

console.log('\n=== 基础类型与结构 ===');
const obj = parse('{"s":"hi\\u0041","t":true,"f":false,"n":null,"e":{},"ea":[]}');
eq('转义字符串', obj.s, 'hiA');
eq('布尔 true', obj.t, true);
eq('布尔 false', obj.f, false);
eq('null', obj.n, null);
eq('空对象', obj.e, {});
eq('空数组', obj.ea, []);
eq('unicode 代理对 😀', parse('"\\uD83D\\uDE00"'), '😀');
eq('中文', parse('"中文"'), '中文');
eq('常见转义字符', parse('"a\\nb\\tc\\\\d\\"e"'), 'a\nb\tc\\d"e');

console.log('\n=== 与原生 JSON.parse 结果一致 ===');
['42', '-0.5', '"x"', '[1,2,3]', '{"k":[true,false,null,1.5]}', '  { "x" : 1 }  ', '[{"a":1},{"b":2}]']
    .forEach(function (s) { eq('native 一致: ' + s, parse(s), JSON.parse(s)); });

console.log('\n=== stringify ===');
eq('bigint 无引号输出', stringify(BigInt(MAX_INT64)), MAX_INT64);
eq('普通对象', stringify({ a: 1, b: 'x' }), '{"a":1,"b":"x"}');
eq('嵌套含 bigint', stringify({ id: BigInt(MAX_INT64) }), '{"id":' + MAX_INT64 + '}');
eq('缩进格式化', stringify({ a: BigInt(MAX_INT64) }, null, 2),
    '{\n  "a": ' + MAX_INT64 + '\n}');
eq('数组含 bigint', stringify([1, BigInt(MAX_INT64)]), '[1,' + MAX_INT64 + ']');

console.log('\n=== 往返（round-trip）===');
function roundTrip(name, text) {
    const once = stringify(parse(text));
    eq(name + ' 往返一致', stringify(parse(once)), stringify(parse(text)));
    // 输出必须是合法 JSON，且原生解析不报错
    assert((function () { try { JSON.parse(once); return true; } catch (e) { return false; } })(),
        name + ' 输出为合法 JSON: ' + once);
    return once;
}
roundTrip('int64 对象', '{"id":' + MAX_INT64 + ',"name":"x","arr":[1,2,3]}');
roundTrip('混合结构', '[{"a":' + MIN_INT64 + '},{"b":1.5,"c":[null,true,"s"]}]');
eq('往返后仍有 bigint', typeof parse(stringify(parse('{"id":' + MAX_INT64 + '}'))).id, 'bigint');

console.log('\n=== 错误处理 ===');
function expectThrow(name, text) {
    let threw = false;
    try { parse(text); } catch (e) { threw = true; }
    assert(threw, name + ' 应抛出解析错误: ' + text);
}
expectThrow('非法 JSON', '{bad}');
expectThrow('未闭合对象', '{"a":1');
expectThrow('尾随逗号', '{"a":1,}');
expectThrow('未闭合字符串', '"abc');
expectThrow('空输入', '');

console.log('\n=== 导出 ===');
assert(typeof parse === 'function', '导出 parse 函数');
assert(typeof stringify === 'function', '导出 stringify 函数');

console.log('\n=== 汇总 ===');
console.log('通过:', passed, '/', passed + failed);
if (failed > 0) {
    console.log('\n失败详情:');
    errors.forEach(function (e) { console.log('  -', e); });
    process.exit(1);
} else {
    console.log('全部测试通过!');
}
