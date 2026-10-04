// Leave unsuccessful or unfamiliar responses untouched.
function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function clearArrays(object, keys) {
  if (!isObject(object)) return false;
  let changed = false;
  for (const key of keys) {
    if (Array.isArray(object[key]) && object[key].length) {
      object[key] = [];
      changed = true;
    }
  }
  return changed;
}

function filterCards(data, allowed) {
  if (!isObject(data) || (!Array.isArray(data.cardList) && !isObject(data.cardList))) {
    return false;
  }
  const cards = Object.values(data.cardList);
  const kept = cards.filter((card) => isObject(card) && allowed.includes(card.dataType));
  if (kept.length === cards.length) return false;
  data.cardList = kept;
  return true;
}

function cleanResponse(url, obj) {
  const data = isObject(obj.data) ? obj.data : null;
  let changed = false;
  if (url.includes('valueadded/alimama/splash_screen')) {
    if (!Array.isArray(data?.ad)) return false;
    for (const ad of data.ad) {
      if (!isObject(ad?.set?.setting) || !Array.isArray(ad?.creative) || !isObject(ad.creative[0])) {
        continue;
      }
      ad.set.setting.display_time = 0;
      ad.creative[0].start_time = 2240150400;
      ad.creative[0].end_time = 2240150400;
      changed = true;
    }
  } else if (url.includes('faas/amap-navigation/main-page')) {
    changed = filterCards(data, ['LoginCard', 'FrequentLocation']);
    changed = clearArrays(data?.pull3, ['msgs']) || changed;
    changed = clearArrays(data, ['business_position', 'mapBizList']) || changed;
  } else if (url.includes('profile/index/node')) {
    if (data && Object.prototype.hasOwnProperty.call(data, 'tipData')) {
      delete data.tipData;
      changed = true;
    }
    changed = filterCards(data, ['GdRecommendCard', 'MyOrderCard']) || changed;
  } else if (url.includes('new_hotword')) {
    changed = clearArrays(data, ['header_hotword']);
  } else if (url.includes('ws/promotion-web/resource')) {
    changed = clearArrays(data, ['icon', 'banner', 'tips', 'popup', 'bubble', 'other']);
  } else if (url.includes('ws/msgbox/pull')) {
    changed = clearArrays(obj, ['msgs']);
    changed = clearArrays(obj.pull3, ['msgs']) || changed;
  } else if (url.includes('ws/message/notice/list')) {
    changed = clearArrays(data, ['noticeList']);
  } else if (url.includes('ws/shield/frogserver/aocs')) {
    for (const target of ['gd_notch_logo', 'home_business_position_config', 'his_input_tip', 'operation_layer']) {
      if (isObject(data?.[target])) {
        data[target] = { status: 1, version: '', value: '' };
        changed = true;
      }
    }
  } else if (url.includes('search/nearbyrec_smart') && data) {
    const targets = ['coupon', 'scene', 'activity', 'commodity_rec', 'operation_activity'];
    for (const target of targets) {
      if (Object.prototype.hasOwnProperty.call(data, target)) {
        delete data[target];
        changed = true;
      }
    }
    if (Array.isArray(data.modules)) {
      const kept = data.modules.filter((module) => !targets.includes(module));
      if (kept.length !== data.modules.length) {
        data.modules = kept;
        changed = true;
      }
    }
  }
  return changed;
}

let result = {};
try {
  const status = Number($response.status ?? $response.statusCode);
  if (status === 200 && typeof $response.body === 'string' && $response.body.trim()) {
    const obj = JSON.parse($response.body);
    if (isObject(obj) && cleanResponse($request.url, obj)) {
      result = { body: JSON.stringify(obj) };
    }
  }
} catch (error) {
  console.log(`AMap: response left unchanged (${error.name})`);
}
$done(result);
