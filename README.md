# 去广告

Shadowrocket 自用去广告模块。

## 订阅

- 去广告：`https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/main/dist/adblock.module`
- YouTube：`https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/main/dist/youtube.module`
- Spotify：`https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/main/dist/spotify.module`
- Spotify 歌词：`https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/main/dist/spotify-lyric.module`

这些模块可以同时启用。

## 使用

导入订阅后重新应用配置。需要处理 HTTPS 响应的功能必须开启 HTTPS 解密，并信任自己设备生成的 Shadowrocket CA 证书。

Spotify 歌词需要填写自己的百度翻译 API 凭据，歌词内容会发送至百度翻译。

所有运行脚本均镜像在本仓并固定到不可变提交，不直接加载其他仓库的脚本。第三方来源与许可证保存在 `third_party`。
