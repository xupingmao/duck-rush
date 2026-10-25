const assert = require('assert');
const JSONInt64 = require('./json-int64.js');
const { parseEmbeddedJson } = require('./json-embedded.js');

let passed = 0;
function test(name, fn) {
    try {
        fn();
        passed++;
        console.log('  ok  - ' + name);
    } catch (e) {
        console.error('  FAIL- ' + name);
        console.error('       ' + e.message);
        process.exitCode = 1;
    }
}

function transform(raw) {
    return parseEmbeddedJson(JSONInt64.parse(raw));
}

console.log('json-embedded.test.js');

test('single object string field parsed to object', () => {
    const out = transform('{"payload": "{\\"a\\":1,\\"b\\":2}"}');
    assert.deepStrictEqual(out, { payload: { a: 1, b: 2 } });
});

test('string JSON inside array elements parsed', () => {
    const out = transform('["{\\"x\\":1}", "[2,3]", "plain"]');
    assert.deepStrictEqual(out, [{ x: 1 }, [2, 3], 'plain']);
});

test('deeply nested string JSON recursed', () => {
    const raw = String.raw`{"b": "{\"a\": \"{\\\"name\\\": \\\"l3\\\"}\"}"}`;
    const out = transform(raw);
    assert.deepStrictEqual(out, { b: { a: { name: 'l3' } } });
});

test('non-JSON string preserved', () => {
    const out = transform('{"s": "hello world"}');
    assert.deepStrictEqual(out, { s: 'hello world' });
});

test('bare value strings not converted', () => {
    const out = transform('{"n": "123", "b": "true", "arr": "[1]"}');
    assert.deepStrictEqual(out, { n: '123', b: 'true', arr: [1] });
});

test('int64 precision preserved in nested string JSON', () => {
    const big = '9223372036854775807';
    const out = transform('{"v": "{\\"id\\":' + big + '}"}');
    assert.strictEqual(typeof out.v.id, 'bigint');
    assert.strictEqual(out.v.id.toString(), big);
});

test('plain object/array unchanged', () => {
    const src = { a: 1, b: [1, 2, { c: 3 }], d: 'text' };
    const out = parseEmbeddedJson(src);
    assert.deepStrictEqual(out, src);
});

test('top-level array string JSON', () => {
    const out = transform('"[1,2,3]"');
    assert.deepStrictEqual(out, [1, 2, 3]);
});

test('bare string input returned as-is', () => {
    assert.strictEqual(parseEmbeddedJson('just a string'), 'just a string');
});

test('input object not mutated', () => {
    const src = JSONInt64.parse('{"p": "{\\"a\\":1}"}');
    const snapshot = JSONInt64.stringify(src);
    parseEmbeddedJson(src);
    assert.strictEqual(JSONInt64.stringify(src), snapshot);
});

test('invalid JSON string preserved', () => {
    const out = transform('{"x": "{not valid json"}');
    assert.deepStrictEqual(out, { x: '{not valid json' });
});

console.log('\npassed ' + passed + ' cases');
