# Shadowrocket 模块

Shadowrocket 自用模块。

## 模块链接

点击链接框右上角的复制按钮，显示复制成功后在 Shadowrocket 中自行添加。

**去广告** · 通用广告拦截

```text
https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/main/dist/adblock.module
```

**YouTube** · 去广告、画中画与后台播放

```text
https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/main/dist/youtube.module
```

**Spotify** · 去播放广告与播放限制（部分功能）

```text
https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/main/dist/spotify.module
```

**微博** · 去开屏广告（测试）

```text
https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/main/dist/weibo.module
```

这些模块可以同时启用。

## 使用

导入订阅后重新应用配置。需要处理 HTTPS 响应的功能必须开启 HTTPS 解密，并信任自己设备生成的 Shadowrocket CA 证书。

所有运行脚本均镜像在本仓并固定到不可变提交，不直接加载其他仓库的脚本。第三方来源与许可证保存在 `third_party`。
