# 红果 loading 对照版 v3

这是用来测试启动 loading 的独立实验模块。原 V2 的文件和安装地址保持不变，
V2 与此版本只能启用一个。这个版本尚未完成设备验证，不能宣称已修复 loading
或保证所有续播场景正常。

## 修改目的与边界

V2 的设备日志已经确认两个 `-lf` 广告 API 被拒绝，随后长时间观看未再出现广告，
但用户观察到一次覆盖在视频上的 loading，需要手动上划。
日志没有 UI 事件和解密响应，尚不能确定该 loading 就由广告请求失败引起。

此版本只改变 `ads3-normal-lf.zijieapi.com` 与
`ads5-normal-lf.zijieapi.com` 的处理方式：

- 移除这两个域名的 TCP 整域拒绝，改用 Shadowrocket 内置 `reject-dict`，
  对两域的 HTTPS 请求立即返回 HTTP 200 与 `{}`。
- 仅对这两个域名增加 MITM 和 UDP 拒绝，使 HTTP/3 有机会回落到可改写的 HTTPS。
- 保留 V2 其他 15 条精确域名规则，无脚本、外部响应文件或新的运行依赖。

`{}` 是语法有效的空 JSON，**不是已经验证的红果“无广告”业务响应**。
这是对“断连导致等待”这一假设的对照测试。App 可能接受、忽略或继续重试，
也可能仍然显示 loading。Shadowrocket 不能直接控制红果原生页面收起或自动上划。

正片 `reading-video.qznovelvod.com` 子域、`api5-normal-lf.fqnovel.com`、
`api5-normal-sinfonlineb.fqnovel.com`、`reading.snssdk.com` 和共享主域不加入
新增规则或 MITM。没有更改播放地址、剧集信息、账号或奖励状态。
规则按域名生效，其他 App 对这两个广告域名的请求也会受到同样处理。

## 安装

```text
https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/codex/hongguo-experimental/dist/hongguo-loading-experimental.module
```

1. 关闭原来的 `iFansClub - Hongguo Experimental`（V2）。不要同时启用两份红果模块，
   否则 V2 的整域拒绝会干扰空响应测试。
2. 添加并启用此模块，确认名称为 `iFansClub - Hongguo Loading Experimental`，
   描述含 `loading 对照版 v3`。
3. 确认 HTTPS 解密已开启，自己的 Shadowrocket CA 已安装并完全信任。
   已配置好证书时无需生成或安装新证书。模块仅追加上述两个 MITM 主机名。
4. 重新应用配置并重启 Shadowrocket 连接，再彻底退出、重开红果。

可保留现有通用去广告、YouTube 和 Spotify 模块。若另有订阅整域拦截这两个
广告 API，需要排除对应冲突后才能观察空 JSON 的效果。未开启解密或握手失败时，
此版不具备 V2 对这两个 HTTPS 域名的硬拦截，不能把它当成无需证书的替代品。

## 验证与回退

先冷启动两三次，再连续播放 5–10 集。出现 loading 时先观察它能否自行消失，
记录大致时间、是否仍需上划、广告是否重新出现，以及切集和自动续播是否正常。
开启 Shadowrocket 请求记录，确认两个广告域名出现 HTTPS 改写及空 JSON 响应；
只看到 `DOMAIN,...,REJECT` 表示仍有整域拒绝规则，不能据此判断本版效果。

若出现持续 loading、无法续播、广告恢复或 TLS 错误，关闭此模块、重新启用 V2，
重新应用配置并重启红果。保留当次日志以核对是否实际命中改写。

如果确认返回 `{}` 后 loading 依旧，下一步应获取实际广告接口的路径与脱敏响应，
再按真实结构处理“无广告”状态。不要继续猜测 `code`、`data`、`status` 字段，
也不要扩大到主业务接口或整个视频 CDN。
