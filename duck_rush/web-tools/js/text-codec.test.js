/**
 * text-codec.js 单元测试（仅依赖标准库）
 * 运行: node duck_rush/web-tools/js/text-codec.test.js
 */

const path = require('path');
const TextCodec = require(path.resolve(__dirname, 'text-codec.js'));

let passed = 0, failed = 0;
const errors = [];

function assert(cond, msg) {
    if (cond) { passed++; }
    else { failed++; errors.push(msg); console.log('  FAIL:', msg); }
}

function eq(name, got, expected) {
    const g = JSON.stringify(got);
    const e = JSON.stringify(expected);
    assert(g === e, name + ' => ' + g + ' (expected ' + e + ')');
}

/** 编解码往返：encode 后再 decode 应还原原文本 */
function roundTrip(name, id, text, opts) {
    opts = opts || {};
    let encoded;
    try {
        encoded = TextCodec.encode(id, text, opts);
    } catch (e) {
        failed++; errors.push(name + ' encode 抛错: ' + e.message);
        console.log('  FAIL:', name, 'encode 抛错:', e.message);
        return;
    }
    let decoded;
    try {
        decoded = TextCodec.decode(id, encoded, opts);
    } catch (e) {
        failed++; errors.push(name + ' decode 抛错: ' + e.message);
        console.log('  FAIL:', name, 'decode 抛错:', e.message);
        return;
    }
    eq(name + ' 往返', decoded, text);
}

console.log('=== 编解码器注册 ===');
assert(TextCodec.codecs.length === 6, '注册 6 个编解码器 (实际 ' + TextCodec.codecs.length + ')');
assert(typeof TextCodec.encode === 'function', '导出 encode');
assert(typeof TextCodec.decode === 'function', '导出 decode');
assert(typeof TextCodec.getCodec === 'function', '导出 getCodec');
TextCodec.codecs.forEach(function (c) {
    assert(typeof c.encode === 'function' && typeof c.decode === 'function',
        c.id + ' 具备 encode/decode');
    assert(typeof c.name === 'string' && c.name.length > 0, c.id + ' 有名称');
});

console.log('\n=== URL 编码 ===');
eq('中文', TextCodec.encode('url', '你好'), '%E4%BD%A0%E5%A5%BD');
eq('空格', TextCodec.encode('url', 'a b'), 'a%20b');
eq('特殊符号', TextCodec.encode('url', 'a&b=c'), 'a%26b%3Dc');
eq('保留结构 keepStructure', TextCodec.encode('url', 'https://a.com/你?q=1', { keepStructure: true }),
    'https://a.com/%E4%BD%A0?q=1');
eq('默认不保留结构', TextCodec.encode('url', 'https://a.com/你'),
    'https%3A%2F%2Fa.com%2F%E4%BD%A0');
eq('解码', TextCodec.decode('url', '%E4%BD%A0%E5%A5%BD'), '你好');
eq('解码把 + 还原为空格', TextCodec.decode('url', 'a+b'), 'a b');
roundTrip('url 中文', 'url', '你好，Duck Rush!');
roundTrip('url 混合', 'url', 'q=a b&c=1#frag');

console.log('\n=== Base64 ===');
eq('英文', TextCodec.encode('base64', 'Duck'), 'RHVjaw==');
eq('中文按 UTF-8', TextCodec.encode('base64', '你好'), '5L2g5aW9');
eq('emoji', TextCodec.encode('base64', '\u{1F600}'), '8J+YgA==');
eq('解码中文', TextCodec.decode('base64', '5L2g5aW9'), '你好');
eq('URL 安全字符集', TextCodec.encode('base64', '??>>??>>', { urlSafe: true }),
    TextCodec.encode('base64', '??>>??>>').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''));
eq('URL 安全往返', TextCodec.decode('base64',
    TextCodec.encode('base64', '你好??', { urlSafe: true }), { urlSafe: true }), '你好??');
roundTrip('base64 中文', 'base64', '你好，Duck Rush!');
roundTrip('base64 emoji', 'base64', 'hi \u{1F600} 鸭');
roundTrip('base64 多行', 'base64', '第一行\n第二行\ttab');

console.log('\n=== HTML 实体 ===');
eq('转义 5 个基础字符', TextCodec.encode('html', '<a href="x">a & b</a>'),
    '&lt;a href=&quot;x&quot;&gt;a &amp; b&lt;/a&gt;');
eq("单引号转数字实体", TextCodec.encode('html', "it's"), 'it&#39;s');
eq('解码命名实体', TextCodec.decode('html', '&lt;div&gt;&amp;&quot;&#39;&nbsp;'),
    '<div>&"\' ');
eq('解码数字实体', TextCodec.decode('html', '&#20320;&#22909;'), '你好');
eq('解码十六进制实体', TextCodec.decode('html', '&#x4F60;&#x597D;'), '你好');
eq('未识别实体原样保留', TextCodec.decode('html', '&notreal;x'), '&notreal;x');
eq('encodeAll 输出数字实体', TextCodec.encode('html', 'a你', { encodeAll: true }),
    'a&#20320;');
roundTrip('html 基础', 'html', '<div class="tip">你好 & "world"</div>');
roundTrip('html 特殊字符', 'html', "a & b < c > d \" e ' f");

console.log('\n=== Unicode 转义 ===');
eq('中文转 \\u', TextCodec.encode('unicode', '你好'), '\\u4F60\\u597D');
eq('默认保留 ASCII', TextCodec.encode('unicode', 'Duck 你好'), 'Duck \\u4F60\\u597D');
eq('emoji 代理对', TextCodec.encode('unicode', '\u{1F600}'), '\\uD83D\\uDE00');
eq('小写选项', TextCodec.encode('unicode', '你好', { lowercaseHex: true }), '\\u4f60\\u597d');
eq('escapeAllChars', TextCodec.encode('unicode', 'ab', { escapeAllChars: true }),
    '\\u0061\\u0062');
eq('解码 \\uXXXX', TextCodec.decode('unicode', '\\u4F60\\u597D'), '你好');
eq('解码代理对', TextCodec.decode('unicode', '\\uD83D\\uDE00'), '\u{1F600}');
eq('解码 \\u{...}', TextCodec.decode('unicode', '\\u{1F600}'), '\u{1F600}');
eq('解码 \\xXX', TextCodec.decode('unicode', '\\x48\\x69'), 'Hi');
roundTrip('unicode 中文', 'unicode', '你好，世界！');
roundTrip('unicode emoji', 'unicode', 'Duck \u{1F600} 鸭');
roundTrip('unicode 小写选项', 'unicode', '你好 Duck', { lowercaseHex: true });
roundTrip('unicode escapeAll', 'unicode', 'abc 你好', { escapeAllChars: true });

console.log('\n=== Hex 十六进制 ===');
eq('中文 UTF-8 字节', TextCodec.encode('hex', '你好'), 'e4bda0e5a5bd');
eq('ASCII', TextCodec.encode('hex', 'Hi'), '4869');
eq('大写选项', TextCodec.encode('hex', '你好', { uppercase: true }), 'E4BDA0E5A5BD');
eq('空格分隔', TextCodec.encode('hex', '你好', { spaced: true }), 'e4 bd a0 e5 a5 bd');
eq('解码中文', TextCodec.decode('hex', 'e4bda0e5a5bd'), '你好');
eq('解码忽略空白/冒号', TextCodec.decode('hex', 'e4:bd:a0 e5a5bd'), '你好');
eq('空串', TextCodec.decode('hex', ''), '');
roundTrip('hex 中文', 'hex', '你好 Duck');
roundTrip('hex emoji', 'hex', '\u{1F600}');
roundTrip('hex 大写+空格', 'hex', '你好鸭', { uppercase: true, spaced: true });

console.log('\n=== JSON 转义 ===');
eq('转义换行', TextCodec.encode('json', 'a\nb'), 'a\\nb');
eq('转义引号', TextCodec.encode('json', 'say "hi"'), 'say \\"hi\\"');
eq('转义反斜杠', TextCodec.encode('json', 'a\\b'), 'a\\\\b');
eq('保留中文原样', TextCodec.encode('json', '你好'), '你好');
eq('解码', TextCodec.decode('json', 'a\\nb\\tc'), 'a\nb\tc');
roundTrip('json 混合', 'json', '第一行\n第二行 "引号" \\ 反斜杠\ttab');

console.log('\n=== UTF-8 边界 ===');
eq('单字节', TextCodec.utf8Encode('A').length, 1);
eq('中文 3 字节', TextCodec.utf8Encode('你').length, 3);
eq('emoji 4 字节', TextCodec.utf8Encode('\u{1F600}').length, 4);
eq('utf8 往返中文', TextCodec.utf8Decode(TextCodec.utf8Encode('你好鸭')), '你好鸭');
eq('utf8 往返 emoji', TextCodec.utf8Decode(TextCodec.utf8Encode('\u{1F600}')), '\u{1F600}');
eq('utf8 往返混合', TextCodec.utf8Decode(TextCodec.utf8Encode('a你\u{1F600}')), 'a你\u{1F600}');

console.log('\n=== 错误处理 ===');
function expectThrow(name, fn) {
    let threw = false, msg = '';
    try { fn(); } catch (e) { threw = true; msg = e.message; }
    assert(threw, name + ' 应抛错' + (threw ? '（已抛：' + msg + '）' : '（未抛）'));
}
expectThrow('base64 非法字符', function () { TextCodec.decode('base64', '@@@@'); });
expectThrow('hex 奇数长度', function () { TextCodec.decode('hex', 'abc'); });
expectThrow('hex 非法字符', function () { TextCodec.decode('hex', 'zz'); });
expectThrow('url 非法百分号', function () { TextCodec.decode('url', '%E4%'); });
expectThrow('json 非法转义', function () { TextCodec.decode('json', 'a\\qb'); });
expectThrow('未知编解码类型', function () { TextCodec.encode('nope', 'x'); });

console.log('\n=== 汇总 ===');
console.log('通过:', passed, '/', passed + failed);
if (failed > 0) {
    console.log('\n失败详情:');
    errors.forEach(function (e) { console.log('  -', e); });
    process.exit(1);
} else {
    console.log('全部测试通过!');
}
