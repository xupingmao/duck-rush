/* global Decimal */

const path = require('path');
const Decimal = require(path.resolve(__dirname, '../../lib/decimal-10.6.0.min.js'));
const { calcExpr } = require(path.resolve(__dirname, 'math-calculator.js'));

let passed = 0, failed = 0, errors = [];

function assert(cond, msg) {
    if (!cond) { failed++; errors.push(msg); console.log('  FAIL:', msg); }
    else { passed++; console.log('  PASS:', msg); }
}

function test(name, expr, expected) {
    try {
        let result = calcExpr(expr).toString();
        assert(result === expected, name + ' = ' + result + ' (expected ' + expected + ')');
    } catch (e) {
        failed++; errors.push(name + ' threw: ' + e.message);
        console.log('  FAIL:', name, '-', e.message);
    }
}

function testError(name, expr, expected) {
    try {
        let result = calcExpr(expr).toString();
        assert(result === expected, name + ' = ' + result + ' (expected ' + expected + ')');
    } catch (e) {
        failed++; errors.push(name + ' should not throw: ' + e.message);
        console.log('  FAIL:', name, '-', e.message);
    }
}

function testVar(name, expr, history, expected) {
    try {
        let result = calcExpr(expr, history).toString();
        assert(result === expected, name + ' = ' + result + ' (expected ' + expected + ')');
    } catch (e) {
        failed++; errors.push(name + ' threw: ' + e.message);
        console.log('  FAIL:', name, '-', e.message);
    }
}

console.log('\n=== 基础运算 ===');
test('0.1 + 0.2', '0.1+0.2', '0.3');
test('0.3 - 0.1', '0.3-0.1', '0.2');
test('2 * 3', '2*3', '6');
test('10 % 3', '10%3', '1');

console.log('\n=== 大数运算 ===');
test('大数加法', '12345678901234567890+98765432109876543210', '111111111011111111100');
test('大数乘法', '12345678901234567890*98765432109876543210', '1219326311370217952237463801111263526900');

console.log('\n=== 大数取模 (原 bug) ===');
test('大数取模 1', '12345678901234567891%1024', '723');
test('大数取模 2', '12345678901234567890%1024', '722');
test('大数取模 3', '12345678901234567892%1024', '724');

console.log('\n=== 优先级 ===');
test('乘优先', '2+3*4', '14');
test('括号优先', '2*(3+4)', '14');
test('多层括号', '(1+2)*(3+4)', '21');

console.log('\n=== 幂运算 ===');
test('2^10', '2^10', '1024');
test('2^-3', '2^-3', '0.125');
test('(-2)^3', '(-2)^3', '-8');
test('幂右结合 2^2^3', '2^2^3', '256');

console.log('\n=== 一元运算符 ===');
test('正号', '+5', '5');
test('负号', '-5', '-5');
test('负号加括号', '-(3+4)', '-7');
test('连续负号', '--5', '5');

console.log('\n=== 函数 ===');
test('sqrt', 'sqrt(16)', '4');
test('abs', 'abs(-5)', '5');
test('round', 'round(3.5)', '4');
test('round 负', 'round(-3.5)', '-4');
test('floor', 'floor(3.7)', '3');
test('floor 负', 'floor(-3.7)', '-4');
test('ceil', 'ceil(3.2)', '4');
test('ceil 负', 'ceil(-3.2)', '-3');
test('max', 'max(5,3,9,1)', '9');
test('min', 'min(5,3,9,1)', '1');

console.log('\n=== 三角函数 (Math 兜底) ===');
test('sin(0)', 'sin(0)', '0');
test('cos(0)', 'cos(0)', '1');
test('tan(0)', 'tan(0)', '0');

console.log('\n=== 对数 ===');
test('log10(1000)', 'log(1000)', '3');
test('ln(e)', 'ln(e)', '1');

console.log('\n=== 常数 ===');
test('pi', 'pi', '3.1415926535897932384626433832795028841971693993751');
test('e', 'e', '2.7182818284590452353602874713526624977572470937');

console.log('\n=== 变量引用 ===');
let hist = [{ result: '10' }, { result: '20' }];
testVar('$1 + $2', '$1+$2', hist, '30');
testVar('$1 * $2', '$1*$2', hist, '200');

console.log('\n=== 错误处理 ===');
testError('除零返回 Infinity', '1/0', 'Infinity');
testError('模零返回 NaN', '1%0', 'NaN');
testError('负数开平方返回 NaN', 'sqrt(-1)', 'NaN');
test('变量不存在', '$999', 'NaN');

console.log('\n=== 汇总 ===');
console.log('通过:', passed, '/', passed + failed);
if (failed > 0) {
    console.log('\n失败详情:');
    errors.forEach(function(e) { console.log('  -', e); });
    process.exit(1);
} else {
    console.log('全部测试通过!');
}
