/**
 * json-path.js 单元测试（仅依赖标准库）
 * 运行: node duck_rush/web-tools/js/json-path.test.js
 */

const path = require('path');
const JSONPath = require(path.resolve(__dirname, 'json-path.js'));

const { extract, parsePath } = JSONPath;
const parse = JSON.parse;

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

const DATA = parse(`{
  "name": "张三",
  "age": 30,
  "data": {
    "user": { "name": "李四", "age": 25 },
    "users": [
      { "name": "Alice", "age": 18 },
      { "name": "Bob", "age": 20 }
    ],
    "matrix": [[1, 2], [3, 4]]
  }
}`);

console.log('=== 基本取值（两种写法等价）===');
eq('点路径 name', extract(DATA, 'name'), ['张三']);
eq('JSONPath $.name', extract(DATA, '$.name'), ['张三']);
eq('嵌套 data.user.name', extract(DATA, 'data.user.name'), ['李四']);
eq('嵌套 $.data.user.name', extract(DATA, '$.data.user.name'), ['李四']);
eq('取对象 data.user', extract(DATA, 'data.user'), [{ name: '李四', age: 25 }]);
eq('数字字段', extract(DATA, 'age'), [30]);

console.log('\n=== 根路径 ===');
eq('空路径返回根', extract(DATA, ''), [DATA]);
eq('$ 返回根', extract(DATA, '$'), [DATA]);

console.log('\n=== 数组下标 ===');
eq('users[0].name', extract(DATA, 'data.users[0].name'), ['Alice']);
eq('$.data.users[1].age', extract(DATA, '$.data.users[1].age'), [20]);
eq('多维下标 matrix[1][0]', extract(DATA, 'data.matrix[1][0]'), [3]);
eq('纯下标 [$] 作用于根数组', extract([10, 20, 30], '[1]'), [20]);
eq('越界下标返回空', extract(DATA, 'data.users[9]'), []);
eq('下标越界后续不再递归', extract(DATA, 'data.users[9].name'), []);

console.log('\n=== 通配符 ===');
// * 只展开「当前这一层」：data 的三个成员是 user 对象、users 数组、matrix 数组，
// 数组本身没有 name，所以只有 user 命中；要取数组元素需显式写 users[*]
eq('data.*.name（不自动下钻数组）', extract(DATA, 'data.*.name'), ['李四']);
eq('users[*].age', extract(DATA, 'data.users[*].age'), [18, 20]);
eq('users[*].name', extract(DATA, 'data.users[*].name'), ['Alice', 'Bob']);
eq('根通配 * 取全部成员', extract(DATA, '*').length, 3);
eq('数组根通配 *', extract([1, 2, 3], '*'), [1, 2, 3]);
eq('通配不命中返回空', extract(DATA, 'data.nope.*'), []);

console.log('\n=== 正则过滤 ===');
eq('name:^A 过滤', extract(DATA, 'data.users[*].name:^A'), ['Alice']);
eq('name:/^B/ 字面量', extract(DATA, 'data.users[*].name:/^B/'), ['Bob']);
eq('带 flags 忽略大小写', extract(DATA, 'data.users[*].name:/^a/i'), ['Alice']);
eq('过滤后无命中', extract(DATA, 'data.users[*].name:^Z'), []);
eq('数字字段也能过滤', extract(DATA, 'data.users[*].age:^2'), [20]);

console.log('\n=== 未命中与异常 ===');
eq('字段不存在', extract(DATA, 'data.nope'), []);
eq('中间层缺失', extract(DATA, 'nope.deep.value'), []);
eq('对标量继续取值', extract(DATA, 'name.foo'), []);
eq('非法下标抛错', (function () {
    try { extract(DATA, 'data.users[a]'); return 'no-throw'; }
    catch (e) { return 'throw'; }
})(), 'throw');
eq('空片段抛错', (function () {
    try { extract(DATA, 'data..name'); return 'no-throw'; }
    catch (e) { return 'throw'; }
})(), 'throw');

console.log('\n=== parsePath 结构 ===');
eq('根路径片段为空', parsePath('$').length, 0);
assert(parsePath('users[0]')[0].key === 'users' &&
    parsePath('users[0]')[0].indexes[0].value === 0, 'users[0] 解析出 key 与下标');
assert(parsePath('*')[0].key === '*', '* 解析为通配');
assert(parsePath('[1]')[0].key === null, '纯下标 key 为 null');
assert(parsePath('name:/^A/i')[0].filter instanceof RegExp, '过滤片段编译为 RegExp');

console.log('\n---------------------------------');
console.log(`passed: ${passed}, failed: ${failed}`);
if (failed > 0) {
    console.log('failed cases:');
    errors.forEach(e => console.log('  - ' + e));
    process.exit(1);
}
