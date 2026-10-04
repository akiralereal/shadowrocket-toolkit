const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const scriptRoot = path.join(__dirname, '..', 'scripts');
const amap = fs.readFileSync(path.join(scriptRoot, 'amap.js'), 'utf8');

function run(body, endpoint = 'valueadded/alimama/splash_screen', status = 200) {
  const calls = [];
  vm.runInNewContext(amap, {
    $request: { url: `https://m5.amap.com/ws/${endpoint}` },
    $response: { status, headers: {}, body },
    $done: (result) => calls.push(JSON.parse(JSON.stringify(result))),
    console: { log() {} },
  }, { timeout: 1000 });
  assert.equal(calls.length, 1, 'each response must finish exactly once');
  return calls[0];
}

test('all shipped scripts parse', () => {
  for (const file of fs.readdirSync(scriptRoot).filter((file) => file.endsWith('.js'))) {
    assert.doesNotThrow(() => new vm.Script(fs.readFileSync(path.join(scriptRoot, file), 'utf8')), file);
  }
});

test('AMap leaves non-200 and non-JSON responses untouched', () => {
  for (const body of ['', undefined, '<html>error</html>', 'null', '[]', '42', '"text"']) {
    assert.deepEqual(run(body), {});
  }
  assert.deepEqual(run('{"data":{"ad":[]}}', undefined, 503), {});
});

test('AMap tolerates missing fields at every matched endpoint', () => {
  const endpoints = [
    'valueadded/alimama/splash_screen', 'faas/amap-navigation/main-page',
    'shield/dsp/profile/index/nodefaasv3', 'shield/search/new_hotword',
    'promotion-web/resource', 'msgbox/pull', 'message/notice/list',
    'shield/frogserver/aocs/updatable', 'shield/search/nearbyrec_smart',
  ];
  for (const endpoint of endpoints) {
    for (const body of ['{}', '{"data":null}', '{"data":[]}']) {
      assert.deepEqual(run(body, endpoint), {}, endpoint);
    }
  }
});

test('AMap suppresses valid splash ads and preserves incomplete entries', () => {
  const body = { data: { ad: [null, {}, { set: {} }, {
    set: { setting: { display_time: 3, other: 'keep' } },
    creative: [{ start_time: 1, end_time: 2, image: 'keep' }],
  }] }, useful: 'keep' };
  const result = JSON.parse(run(JSON.stringify(body)).body);
  assert.deepEqual(result.data.ad.slice(0, 3), body.data.ad.slice(0, 3));
  assert.equal(result.data.ad[3].set.setting.display_time, 0);
  assert.equal(result.data.ad[3].creative[0].start_time, 2240150400);
  assert.equal(result.data.ad[3].creative[0].end_time, 2240150400);
  assert.equal(result.data.ad[3].creative[0].image, 'keep');
  assert.equal(result.useful, 'keep');
  assert.deepEqual(run('{"data":{"ad":{}}}'), {});
  assert.deepEqual(run('{"data":{"ad":[{}]}}'), {});
});

test('AMap keeps functional cards and unrelated response fields', () => {
  const result = JSON.parse(run(JSON.stringify({ data: {
    cardList: [{ dataType: 'LoginCard' }, { dataType: 'FrequentLocation' }, { dataType: 'AdCard' }, null],
    pull3: { msgs: [1], cursor: 'keep' }, business_position: [1], mapBizList: [1], weather: 'keep',
  } }), 'faas/amap-navigation/main-page').body);
  assert.deepEqual(result.data.cardList, [{ dataType: 'LoginCard' }, { dataType: 'FrequentLocation' }]);
  assert.deepEqual(result.data.pull3, { msgs: [], cursor: 'keep' });
  assert.deepEqual(result.data.business_position, []);
  assert.deepEqual(result.data.mapBizList, []);
  assert.equal(result.data.weather, 'keep');
});

test('AMap filters profile cards without touching orders', () => {
  const result = JSON.parse(run(JSON.stringify({ data: {
    tipData: {}, cardList: { order: { dataType: 'MyOrderCard', id: 1 }, ad: { dataType: 'AdCard' } },
    orders: [1],
  } }), 'shield/dsp/profile/index/nodefaasv3').body);
  assert.equal('tipData' in result.data, false);
  assert.deepEqual(result.data.cardList, [{ dataType: 'MyOrderCard', id: 1 }]);
  assert.deepEqual(result.data.orders, [1]);
});

test('AMap preserves unexpected collection types', () => {
  assert.deepEqual(run('{"data":{"modules":{},"weather":"keep"}}', 'shield/search/nearbyrec_smart'), {});
  assert.deepEqual(run('{"data":{"cardList":"keep","business_position":{}}}', 'faas/amap-navigation/main-page'), {});
  assert.deepEqual(run('{"data":{"banner":"keep"}}', 'promotion-web/resource'), {});
  assert.deepEqual(run('{"data":{"noticeList":{}}}', 'message/notice/list'), {});
});

test('AMap removes nearby promotions while retaining useful modules', () => {
  const result = JSON.parse(run(JSON.stringify({ data: {
    coupon: {}, scene: {}, modules: ['coupon', 'weather', 'commodity_rec', 'navigation'], weather: 'keep',
  } }), 'shield/search/nearbyrec_smart').body);
  assert.equal('coupon' in result.data, false);
  assert.equal('scene' in result.data, false);
  assert.deepEqual(result.data.modules, ['weather', 'navigation']);
  assert.equal(result.data.weather, 'keep');
});

test('AMap cleans known promotion collections and preserves unrelated fields', () => {
  const cases = [
    ['shield/search/new_hotword', { data: { header_hotword: ['ad'], useful: 1 } }, { data: { header_hotword: [], useful: 1 } }],
    ['promotion-web/resource', { data: { banner: ['ad'], icon: ['ad'], useful: 1 } }, { data: { banner: [], icon: [], useful: 1 } }],
    ['msgbox/pull', { msgs: ['ad'], pull3: { msgs: ['ad'], useful: 1 } }, { msgs: [], pull3: { msgs: [], useful: 1 } }],
    ['message/notice/list', { data: { noticeList: ['ad'], useful: 1 } }, { data: { noticeList: [], useful: 1 } }],
    ['shield/frogserver/aocs/updatable', { data: { gd_notch_logo: { value: 'ad' }, useful: 1 } }, { data: { gd_notch_logo: { status: 1, version: '', value: '' }, useful: 1 } }],
  ];
  for (const [endpoint, body, expected] of cases) {
    assert.deepEqual(JSON.parse(run(JSON.stringify(body), endpoint).body), expected, endpoint);
  }
});

test('AMap leaves unknown endpoints and unchanged responses untouched', () => {
  assert.deepEqual(run('{"data":{"ad":[{}]}}', 'unrelated'), {});
  assert.deepEqual(run('{"data":{"cardList":[{"dataType":"LoginCard"}]}}', 'faas/amap-navigation/main-page'), {});
});
