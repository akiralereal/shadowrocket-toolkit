# Third-party notices

All generated modules load their JavaScript from the commit-pinned mirror in
`akiralereal/shadowrocket-toolkit`. Original provenance is retained here:

- Six mirrored files from `app2smile/rules` at commit
  `df6366a7024e0b3f0aa3510c5b791eea6f3cba89`, licensed under the MIT License.
  Local changes to `scripts/spotify-proto.js` stop overriding the
  `audio-quality` and `high-bitrate` account attributes.
- The mirrored `scripts/youtube-response.js` is based on
  `Script/Youtube/youtube.response.js`
  from `Maasea/sgmodule` at commit
  `65075cdb388fc5e3094afd7e7314c67b243f3525`, licensed under the Apache License
  2.0. Local changes replace user-facing branding and preserve the original
  background playback renderer when YouTube already enables it.
- The mirrored `scripts/amap.js` is based on `Shadowrocket/Scripts/AMap.js`
  from `ofwh/Profiles` at commit
  `1fbd9181bd2b743aeec239b6f661febdca31b320`, licensed under the MIT License.
  Local changes validate response status, JSON and field shapes, and preserve
  the original response when parsing or processing fails.

The corresponding license texts are preserved in `third_party`. Runtime and
upstream hashes, source locations, and local modifications are recorded in
`third_party/scripts.json`.

A curated subset of `Filters/AWAvenue-Ads-Rule-Surge-RULE-SET.list` from
`TG-Twilight/AWAvenue-Ads-Rule` at commit
`d77f249050b440989cc9a640eabdb18573dc7c90` is stored locally in
`src/core/rule.list` under GPL-3.0. Functional, high-risk, and existing
path-level matches were excluded, and the highest-priority `pre-matching`
modifier was removed.

The opt-in Hongguo experimental modules in `src/apps/hongguo/rule.list`
and `src/apps/hongguo/loading/rule.list`
reuses exact advertising SDK hosts already present in this repository's core
rules and rewrites. Five additional exact advertising hosts (`ads3-normal`
and `ads5-normal.zijieapi.com`, plus `p3/p6/p9-ad-sign.byteimg.com`) were
selected from `surge/hongguo-lite.sgmodule` and `README.md` in
[`k6nfmm7dbr-commits/hongguo-lite`](https://github.com/k6nfmm7dbr-commits/hongguo-lite/tree/1a51ba09a6fdfb99ac763b8a3cf9eeaa412c1231)
at commit `1a51ba09a6fdfb99ac763b8a3cf9eeaa412c1231`, licensed under MIT.
The license is preserved in `third_party/hongguo-lite-LICENSE.txt`.
The upstream keyword, suffix, regex, telemetry and MITM rules were not copied;
the selected hosts use this repository's exact-domain Shadowrocket syntax.
No remote runtime dependency is introduced. A device connection log confirms
that an advertising asset host is rejected; complete ad removal and playback
behavior remain unverified.

Hongguo v2 adds `ads3-normal-lf.zijieapi.com` and
`ads5-normal-lf.zijieapi.com`, observed as direct connections in a user-provided
diagnostic log. Their advertising classification was cross-checked against
`TG-Twilight/AWAvenue-Ads-Rule`'s `AWAvenue-Ads-Rule.txt` (Git blob
`81f4432281d961a889da8ef0f1558646501eaccb`). Only the two observed exact hosts
were added; the private diagnostic log is not included in this repository.

The loading comparison variant uses locally authored URL Rewrite and MITM
configuration for just those two observed advertising API hosts. It uses
Shadowrocket's built-in empty-JSON response, without introducing a script or
copying an unverified application response schema. The normal-viewing baseline
remains available as the separate V2 module.
