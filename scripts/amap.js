const { status, headers } = $response;
let { body } = $response;
const obj = JSON.parse(body);

if ($request.url.includes('valueadded/alimama/splash_screen')) {
  if (obj.data && obj.data.ad) {
    for (const ad of obj.data.ad) {
      ad.set.setting.display_time = 0;
      ad.creative[0].start_time = 2240150400;
      ad.creative[0].end_time = 2240150400;
    }
  }

  body = JSON.stringify(obj);
} else if ($request.url.includes('faas/amap-navigation/main-page')) {
  if (obj.data?.cardList) {
    obj.data.cardList = Object.values(obj.data.cardList).filter((card) =>
      ['LoginCard', 'FrequentLocation'].includes(card.dataType)
    );
  }
  if (obj.data?.pull3?.msgs) {
    obj.data.pull3.msgs = [];
  }
  if (obj.data?.business_position) {
    obj.data.business_position = [];
  }
  if (obj.data?.mapBizList) {
    obj.data.mapBizList = [];
  }
  body = JSON.stringify(obj);
} else if ($request.url.includes('profile/index/node')) {
  delete obj.data.tipData;
  if (obj.data?.cardList) {
    obj.data.cardList = Object.values(obj.data.cardList).filter((card) =>
      ['GdRecommendCard', 'MyOrderCard'].includes(card.dataType)
    );
  }
  body = JSON.stringify(obj);
} else if ($request.url.includes('new_hotword')) {
  if (obj.data?.header_hotword) {
    obj.data.header_hotword = [];
  }
  body = JSON.stringify(obj);
} else if ($request.url.includes('ws/promotion-web/resource')) {
  const elements = ['icon', 'banner', 'tips', 'popup', 'bubble', 'other'];
  for (const element of elements) {
    if (obj.data?.[element]) {
      obj.data[element] = [];
    }
  }
  body = JSON.stringify(obj);
} else if ($request.url.includes('ws/msgbox/pull')) {
  if (obj.msgs) {
    obj.msgs = [];
  }
  if (obj.pull3?.msgs) {
    obj.pull3.msgs = [];
  }
  body = JSON.stringify(obj);
} else if ($request.url.includes('ws/message/notice/list')) {
  if (obj.data?.noticeList) {
    obj.data.noticeList = [];
  }
  body = JSON.stringify(obj);
} else if ($request.url.includes('ws/shield/frogserver/aocs')) {
  const targets = ['gd_notch_logo', 'home_business_position_config', 'his_input_tip', 'operation_layer'];
  for (const target of targets) {
    if (obj.data?.[target]) {
      obj.data[target] = { status: 1, version: '', value: '' };
    }
  }
  body = JSON.stringify(obj);
} else if ($request.url.includes('search/nearbyrec_smart')) {
  const itemsToRemove = ['coupon', 'scene', 'activity', 'commodity_rec', 'operation_activity'];
  if (obj.data) {
    itemsToRemove.forEach((item) => {
      delete obj.data[item];
    });
    if (obj.data.modules) {
      obj.data.modules = obj.data.modules.filter((module) => !itemsToRemove.includes(module));
    }
  }
  body = JSON.stringify(obj);
}

$done({ status, headers, body: JSON.stringify(obj) });
