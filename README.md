# Shadowrocket 模块

Shadowrocket 自用模块。

## 模块订阅

| 模块 | 功能 | 订阅 |
| --- | --- | --- |
| 去广告 | 通用广告拦截 | [点击订阅](https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/main/dist/adblock.module) |
| YouTube | 去广告、画中画与后台播放 | [点击订阅](https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/main/dist/youtube.module) |
| Spotify | 去播放广告与播放限制（部分功能） | [点击订阅](https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/main/dist/spotify.module) |

这些模块可以同时启用。

## 使用

导入订阅后重新应用配置。需要处理 HTTPS 响应的功能必须开启 HTTPS 解密，并信任自己设备生成的 Shadowrocket CA 证书。

所有运行脚本均镜像在本仓并固定到不可变提交，不直接加载其他仓库的脚本。第三方来源与许可证保存在 `third_party`。
