# 红果短剧去广告实验模块

独立入口：`profiles/hongguo-experimental.json`，构建产物：
`dist/hongguo-experimental.module`。不并入通用 `adblock.module`。

第一版包含 15 条精确域名拦截规则，无脚本、URL 重写或 MITM，
单独使用时无需开启 HTTPS 解密，也无需安装证书。
目标是减少开屏和剧集插播广告的加载；当前仅完成静态校验，
尚未验证具体 iOS / 红果版本，不能保证广告消失或自动继续播放。

## 规则范围

| 范围 | 处理方式 |
| --- | --- |
| 穿山甲 `api-access` 广告 API、`gromore`、`lf3/lf6-ad-union-sdk` | 精确域名拒绝 |
| `ads3-normal.zijieapi.com`、`ads5-normal.zijieapi.com` | 精确域名拒绝 |
| `p3/p6/p9-ad-sign.byteimg.com` | 精确域名拒绝 |
| 正片 CDN、共享 API 主域和普通图片域名 | 不做整域拦截 |
| 埋点、账号、签到、奖励及会员状态 | 不增加相关规则或响应改写 |

这些规则按域名生效，不按 App 隔离；其他 App 请求相同广告域名也会被拦截。
广告加载失败可能出现空白、重试或无法续播，也可能影响依赖广告完成的奖励入口。
已经缓存的广告仍可能出现，广告请求被拒绝也不代表倒计时或广告页面一定消失。

与通用去广告模块可一起测试，其中若干规则会重复命中同一广告域名。
本模块额外将 `api-access.pangolin-sdk-toutiao.com` 和
`api-access.pangolin-sdk-toutiao1.com` 从通用模块的路径拦截扩大为精确域名拦截。
关闭本模块后，通用模块的已有拦截仍然生效。

## 安装与对比测试

实验分支订阅地址：

```text
https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/codex/hongguo-experimental/dist/hongguo-experimental.module
```

1. 在 Shadowrocket 中新增此模块，启用并重新应用配置；使用规则模式。
2. 保持其他模块、节点和网络不变，分别关闭、开启本模块测试。
   每轮先彻底退出红果，再重新打开，观察开屏并连续播放 5–10 集。
3. 记录开屏、剧集间插播是否减少，切集和自动续播是否正常，
   是否出现空白广告页、持续转圈或明显变慢。
4. 如有广告，查看 Shadowrocket 请求记录，确认上述域名是否命中 `REJECT`。
   若命中其他直连或代理规则，先检查模块是否启用、配置是否应用及规则优先级。
5. 出现异常时，关闭此实验模块、重新应用配置并重启红果，观察是否恢复。

反馈时提供 iOS、红果和 Shadowrocket 版本、广告类型、模块开关前后的表现，
以及广告出现前后约 30 秒的相关域名、命中规则和时间即可。
第一轮不需要解密响应，也不需要完整 URL、Cookie、令牌或账号信息。

## 来源

广告 SDK 域名取自本仓 `src/core/rule.list` 和 `src/core/url-rewrite.list`。
字节广告 API 和广告素材域名参考
[HongGuo Lite 的固定版本](https://github.com/k6nfmm7dbr-commits/hongguo-lite/tree/1a51ba09a6fdfb99ac763b8a3cf9eeaa412c1231)。
仅选取明确列出的域名，没有采用它的关键词、后缀、正则和埋点拦截。
这属于规则来源核对，不代表本项目已完成设备实测。
来源说明和许可证保存在 `third_party`。
