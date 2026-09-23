/**
 * text-shell.js 单元测试（仅依赖标准库）
 * 运行: node duck_rush/web-tools/js/text-shell.test.js
 */

const path = require('path');
const TextShell = require(path.resolve(__dirname, 'text-shell.js'));

let passed = 0, failed = 0;
const errors = [];

function assert(cond, msg) {
    if (cond) { passed++; }
    else { failed++; errors.push(msg); console.log('  FAIL:', msg); }
}

function eq(name, got, expected) {
    const g = JSON.stringify(got), e = JSON.stringify(expected);
    assert(g === e, name + ' => ' + g + ' (expected ' + e + ')');
}

/** 跑一条命令，返回 output */
function sh(cmd, input) {
    const r = TextShell.run(cmd, input);
    if (r.error) throw new Error('意外错误: ' + r.error);
    return r.output;
}

const INPUT = 'banana\napple\ncherry\napple\n';

console.log('=== 分词与管道切分 ===');
eq('单引号保留空格', TextShell.tokenize("grep 'a b'"), ['grep', 'a b']);
eq('双引号内的管道符不切分', TextShell.splitPipeline("sed 's/a|b/c/g' | sort"), ["sed 's/a|b/c/g'", 'sort']);
eq('多个管道', TextShell.splitPipeline('sort -u | head -5 | tail -1'), ['sort -u', 'head -5', 'tail -1']);
eq('转义空格', TextShell.tokenize('grep a\\ b'), ['grep', 'a b']);

console.log('\n=== 参数解析 ===');
eq('短选项合并', TextShell.parseArgs(['-ur']).opts, { u: true, r: true });
eq('带值选项 -n5', TextShell.parseArgs(['-n5'], { numberFlag: 'n' }).opts, { n: '5' });
eq('带值选项 -n 5', TextShell.parseArgs(['-n', '5'], { numberFlag: 'n' }).opts, { n: '5' });
eq('纯数字选项 -5', TextShell.parseArgs(['-5'], { numberFlag: 'n' }).opts, { n: '5' });
eq('valueFlags -d,', TextShell.parseArgs(['-d', ','], { valueFlags: ['d'] }).opts, { d: ',' });
eq('位置参数在 args', TextShell.parseArgs(['foo', '-v']).args, ['foo']);

console.log('\n=== 管道串联 ===');
// 上游文本末尾带换行时，结果也保留末尾换行
eq('sort -u | head -2', sh('sort -u | head -2', INPUT), 'apple\nbanana\n');
eq('grep apple | wc -l', sh('grep apple | wc -l', INPUT), '2\n');
eq('三段管道', sh('sort | uniq | head -1', INPUT), 'apple\n');
eq('管道间共享上游', sh('cat | rev', 'ab\n'), 'ba\n');

console.log('\n=== sort / uniq ===');
eq('sort', sh('sort', 'b\na\nc\n'), 'a\nb\nc\n');
eq('sort -u', sh('sort -u', INPUT), 'apple\nbanana\ncherry\n');
eq('sort -n', sh('sort -n', '10\n9\n2\n'), '2\n9\n10\n');
eq('sort -r', sh('sort -r', 'a\nb\n'), 'b\na\n');
eq('sort -f', sh('sort -f', 'B\na\n'), 'a\nB\n');
eq('uniq 去连续重复', sh('uniq', 'a\na\nb\n'), 'a\nb\n');
eq('uniq -c 计数', sh('uniq -c', 'a\na\nb\n'), '      2 a\n      1 b\n');
eq('uniq -d 仅重复', sh('uniq -d', 'a\na\nb\n'), 'a\n');

console.log('\n=== head / tail / grep ===');
eq('head 默认 10', sh('head', '1\n2\n3\n'), '1\n2\n3\n');
eq('head -2', sh('head -2', '1\n2\n3\n'), '1\n2\n');
eq('head -n 2', sh('head -n 2', '1\n2\n3\n'), '1\n2\n');
eq('tail -2', sh('tail -2', '1\n2\n3\n'), '2\n3\n');
eq('grep 命中', sh('grep app', INPUT), 'apple\napple\n');
eq('grep -v 反选', sh('grep -v app', INPUT), 'banana\ncherry\n');
eq('grep -i 忽略大小写', sh('grep -i APPLE', INPUT), 'apple\napple\n');
eq('grep -c 计数', sh('grep -c apple', INPUT), '2\n');
eq('grep -n 行号', sh('grep -n cherry', INPUT), '3:cherry\n');
eq('grep 正则', sh('grep ^a', INPUT), 'apple\napple\n');

console.log('\n=== sed / awk / cut / tr ===');
eq("sed s///g", sh("sed 's/a/X/g'", 'banana\n'), 'bXnXnX\n');
eq("sed 只替换首个", sh("sed 's/a/X/'", 'banana\n'), 'bXnana\n');
eq("sed 其他分隔符", sh("sed 's#a#X#g'", 'banana\n'), 'bXnXnX\n');
eq("sed /模式/d 删除", sh("sed '/app/d'", INPUT), 'banana\ncherry\n');
eq("sed 捕获组", sh("sed 's/(a)(p)/[$2$1]/g'", 'apple\n'), '[pa]ple\n');
eq("awk $1", sh("awk '{print $1}'", 'a 1\nb 2\n'), 'a\nb\n');
eq("awk $2", sh("awk '{print $2}'", 'a 1\nb 2\n'), '1\n2\n');
eq("awk $0", sh("awk '{print $0}'", 'a 1\n'), 'a 1\n');
eq("awk 多字段", sh("awk '{print $1, $2}'", 'a 1\n'), 'a 1\n');
eq("awk NR", sh("awk '{print NR}'", 'a\nb\n'), '1\n2\n');
eq("awk NF", sh("awk '{print NF}'", 'a b c\n'), '3\n');
eq("awk 拼接字符串", sh("awk '{print $1 \"-\" $2}'", 'a 1\n'), 'a-1\n');
eq('cut -d -f', sh('cut -d , -f 2', 'a,b,c\n'), 'b\n');
eq('cut -f 范围', sh('cut -d , -f 1-2', 'a,b,c\n'), 'a,b\n');
eq('tr 大小写', sh('tr a-z A-Z', 'abc\n'), 'ABC\n');
eq('tr -d 删除', sh('tr -d a', 'banana\n'), 'bnn\n');

console.log('\n=== 其它内置命令 ===');
eq('wc 默认', sh('wc', 'a b\nc\n'), '2 3 6\n');
eq('wc -l', sh('wc -l', 'a\nb\n'), '2\n');
eq('wc -w', sh('wc -w', 'a b\nc\n'), '3\n');
eq('cat -n', sh('cat -n', 'a\nb\n'), '1\ta\n2\tb\n');
eq('nl', sh('nl', 'a\n'), '     1\ta\n');
eq('tac 反序', sh('tac', 'a\nb\n'), 'b\na\n');
eq('rev 反转', sh('rev', 'abc\n'), 'cba\n');
eq('trim', sh('trim', '  a  \n'), 'a\n');
eq('echo 忽略输入', sh('echo hello', 'x\n'), 'hello\n');
eq('末尾无换行时保持', sh('sort', 'b\na'), 'a\nb');

console.log('\n=== ctx 与管道 API ===');
TextShell.register('upper', function (ctx) {
    ctx.pipe.write(ctx.lines.map(l => l.toUpperCase()));
}, { usage: 'upper', desc: '转大写' });

TextShell.register('count', function (ctx) {
    return String(ctx.pipe.read().length) + '\n';
}, { usage: 'count', desc: '统计行数' });

eq('自定义命令参与管道', sh('upper | head -1', 'a\nb\n'), 'A\n');
eq('ctx.pipe.read 可用', sh('count', 'a\nb\n'), '2\n');
eq('注册后出现在命令表', TextShell.names().indexOf('upper') !== -1, true);
eq('命令清单含用法', TextShell.list().some(c => c.usage === 'upper'), true);

// log 不进入管道
TextShell.register('noisy', function (ctx) {
    ctx.log('诊断信息');
    ctx.pipe.write(ctx.lines);
});
const noisy = TextShell.run('noisy', 'a\n');
eq('log 不污染输出', noisy.output, 'a\n');
eq('log 单独收集', noisy.log, ['诊断信息']);

console.log('\n=== 错误处理 ===');
const unknown = TextShell.run('nope', 'a\n');
eq('未知命令 exitCode', unknown.exitCode, 127);
eq('未知命令有提示', unknown.error.indexOf('未知命令') === 0, true);
eq('未知命令清空输出', unknown.output, '');
const bad = TextShell.run('grep', 'a\n');
eq('缺少参数 exitCode', bad.exitCode, 1);
eq('缺少参数有提示', bad.error.indexOf('grep:') === 0, true);
const empty = TextShell.run('   ', 'a\n');
eq('空命令 exitCode', empty.exitCode, 1);
const unclosed = TextShell.run("grep 'a", 'a\n');
eq('引号未闭合 exitCode', unclosed.exitCode, 2);
eq('执行到的命令被记录', sh('sort -u | head -1', INPUT) !== undefined &&
    TextShell.run('sort | head', INPUT).commands, ['sort', 'head']);

console.log('\n---------------------------------');
console.log(`passed: ${passed}, failed: ${failed}`);
if (failed > 0) {
    console.log('failed cases:');
    errors.forEach(e => console.log('  - ' + e));
    process.exit(1);
}
