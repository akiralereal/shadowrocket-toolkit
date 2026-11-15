# Shadowrocket 模块

Shadowrocket 自用模块。

## 模块链接

这些模块可以同时启用；点击链接框右上角的复制按钮，复制后在 Shadowrocket 中自行添加。

<div><strong>🔵 去广告</strong> · 通用广告拦截，含高德地图、直播吧、微博开屏</div>

```text
https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/main/dist/adblock.module
```

<div><strong>🔴 YouTube</strong> · 去广告、画中画与后台播放</div>

```text
https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/main/dist/youtube.module
```

<div><strong>🟢 Spotify</strong> · 去播放广告与播放限制（部分功能）；如频繁切歌，请让 Spotify 直连或使用与账号同地区的节点</div>

```text
https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/main/dist/spotify.module
```

<div><strong>🟠 红果短剧（实验版 v2）</strong> · 独立开关，补齐 -lf 广告域名，无需 HTTPS 解密，效果待复测</div>

```text
https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/codex/hongguo-experimental/dist/hongguo-experimental.module
```

红果实验模块未并入通用去广告模块。规则也会影响其他 App 对相同广告域名的请求。
安装后重新应用配置、彻底退出并重开红果，连续播放 5–10 集，观察广告及自动续播；
如出现黑屏、转圈或无法切集，关闭此模块后重新应用配置并重启红果。
详细范围、对比方法及反馈内容见 [红果实验说明](src/apps/hongguo/README.md)。

## 使用

导入订阅后重新应用配置。需要处理 HTTPS 响应的功能必须开启 HTTPS 解密，并信任自己设备生成的 Shadowrocket CA 证书。

所有运行脚本均镜像在本仓并固定到不可变提交，不直接加载其他仓库的脚本。第三方来源与许可证保存在 `third_party`。

## 本地校验

需要 Python 3.9+、Node.js 22+ 和完整 Git 历史。

```sh
python3 tools/build.py --check
python3 tools/validate.py
python3 -m unittest discover -s tests -v
node --test tests/runtime.test.js
python3 tools/audit_scripts.py --local-only
```

本地审计核对脚本哈希、固定提交中的脚本内容，以及源码和发布模块的引用。省略 `--local-only` 可进一步联网核对远端镜像和上游来源。

更新运行脚本时，先运行 JavaScript 测试并提交脚本，再将 `third_party/scripts.json` 的提交和哈希、`src` 中的脚本引用更新到该提交；上游原始哈希保持不变，并记录本地修改。运行 `python3 tools/build.py --update-date 模块名` 重新生成受影响模块，完成上述校验后提交发布文件。
