from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from modulelib import (  # noqa: E402
    ModuleData,
    ModuleError,
    _merge_rules,
    all_profiles,
    collect,
    read_entries,
    render,
)
from build import update_profile_dates  # noqa: E402
from validate import (  # noqa: E402
    parse_script,
    validate_data,
    validate_header_rewrite,
    validate_hostname,
    validate_rewrite,
    validate_rule,
)


class ModuleTests(unittest.TestCase):
    def test_generated_files_are_current(self) -> None:
        for profile in all_profiles():
            self.assertTrue(profile.output.exists(), profile.output)
            self.assertEqual(profile.output.read_text(encoding="utf-8"), render(profile))

    def test_dist_has_no_orphaned_modules(self) -> None:
        expected = {profile.output.resolve() for profile in all_profiles()}
        actual = {
            path.resolve()
            for path in (ROOT / "dist").iterdir()
            if path.is_file() and not path.name.startswith(".")
        }
        self.assertEqual(actual, expected)

    def test_module_names_and_update_dates(self) -> None:
        profiles = {profile.output.name: profile for profile in all_profiles()}
        expected = {
            "adblock.module": "iFansClub - ADBlock",
            "spotify-lyric.module": "iFansClub - Spotify Lyrics",
            "spotify.module": "iFansClub - Spotify",
            "youtube.module": "iFansClub - Youtube",
        }
        for output, name in expected.items():
            with self.subTest(output=output):
                profile = profiles[output]
                self.assertEqual(profile.name, name)
                self.assertRegex(profile.updated, r"^\d{4}-\d{2}-\d{2}$")
                self.assertTrue(
                    render(profile).startswith(
                        f"#!name={name}\n#!desc=更新时间：{profile.updated} | "
                    )
                )

    def test_release_date_stamping_is_selective(self) -> None:
        profiles = {profile.path.stem: profile for profile in all_profiles()}
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            copied = []
            for name, profile in profiles.items():
                path = temporary / f"{name}.json"
                payload = json.loads(profile.path.read_text(encoding="utf-8"))
                payload["updated"] = "2026-01-01"
                path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                copied.append(replace(profile, path=path, updated="2026-01-01"))

            changed = update_profile_dates(copied, ["youtube"], "2026-07-23")
            self.assertEqual(changed, [temporary / "youtube.json"])
            self.assertEqual(
                json.loads((temporary / "adblock.json").read_text())["updated"],
                "2026-01-01",
            )
            self.assertEqual(
                json.loads((temporary / "youtube.json").read_text())["updated"],
                "2026-07-23",
            )

            with self.assertRaises(ModuleError):
                update_profile_dates(copied, ["missing"], "2026-07-23")

    def test_profile_arguments_render_as_local_placeholders(self) -> None:
        youtube = next(
            profile for profile in all_profiles() if profile.output.name == "youtube.module"
        )
        parameterized = replace(
            youtube,
            arguments="appid:,securityKey:",
            arguments_description="仅保存在本机",
        )
        content = render(parameterized)
        self.assertIn("#!arguments=appid:,securityKey:\n", content)
        self.assertIn("#!arguments-desc=仅保存在本机\n", content)

    def test_all_profiles_validate(self) -> None:
        for profile in all_profiles():
            validate_data(collect(profile))

    def test_no_external_branding_in_generated_modules(self) -> None:
        banned = (
            "#!author=",
            "#!homepage=",
            "#!icon=",
            "app2smile",
            "maasea",
            "yfamily",
        )
        contents = [render(profile) for profile in all_profiles()]
        for content in contents:
            content = content.lower()
            for marker in banned:
                self.assertNotIn(marker.lower(), content)

    def test_runtime_scripts_are_self_hosted_and_commit_pinned(self) -> None:
        lock = json.loads((ROOT / "third_party/scripts.json").read_text(encoding="utf-8"))
        repository = "akiralereal/shadowrocket-toolkit"
        self.assertEqual(set(lock), {repository})

        def assert_locked(script_path: str) -> None:
            match = re.fullmatch(
                r"https://raw\.githubusercontent\.com/([^/]+/[^/]+)/([0-9a-f]{40})/(.+)",
                script_path,
            )
            self.assertIsNotNone(match, script_path)
            dependency, commit, relative_path = match.groups()
            self.assertEqual(dependency, repository)
            self.assertEqual(lock[dependency]["commit"], commit)
            self.assertIn(relative_path, lock[dependency]["files"])

        for script_list in sorted((ROOT / "src").glob("**/script.list")):
            for line in read_entries(script_list):
                _, fields = parse_script(line)
                assert_locked(fields["script-path"])

        for rewrite_list in sorted((ROOT / "src").glob("**/url-rewrite.list")):
            for line in read_entries(rewrite_list):
                parts = line.split()
                if len(parts) != 4 or parts[1:3] != ["url", "script-response-body"]:
                    continue
                self.assertFalse(parts[3].endswith(",append"), line)
                assert_locked(parts[3])

        record = lock[repository]
        self.assertEqual(
            set(record["files"]),
            {
                "scripts/amap.js",
                "scripts/baidu-map.js",
                "scripts/qidian.js",
                "scripts/spotify-json.js",
                "scripts/spotify-lyric.js",
                "scripts/spotify-proto.js",
                "scripts/tieba-json.js",
                "scripts/tieba-proto.js",
                "scripts/youtube-response.js",
            },
        )
        self.assertEqual(set(record["provenance"]), set(record["files"]))
        for license_file in record["license_files"]:
            self.assertTrue((ROOT / license_file).is_file())
        for relative_path, origin in record["provenance"].items():
            self.assertEqual(len(origin["commit"]), 40, relative_path)
            self.assertEqual(len(origin["sha256"]), 64, relative_path)
            self.assertTrue((ROOT / origin["license_file"]).is_file())

    def test_profile_architecture(self) -> None:
        profiles = {profile.output.name: profile for profile in all_profiles()}
        self.assertNotIn("amap.module", profiles)
        self.assertIn("apps/amap", profiles["adblock.module"].components)
        self.assertNotIn("apps/youtube", profiles["adblock.module"].components)
        self.assertEqual(profiles["youtube.module"].components, ("apps/youtube",))
        self.assertEqual(
            profiles["spotify.module"].components,
            ("apps/spotify/vip",),
        )
        self.assertEqual(
            profiles["spotify-lyric.module"].components,
            ("apps/spotify/lyric",),
        )
        self.assertFalse(profiles["youtube.module"].mitm_h2)
        self.assertFalse(profiles["spotify.module"].mitm_h2)
        self.assertFalse(profiles["spotify-lyric.module"].mitm_h2)
        self.assertFalse(profiles["adblock.module"].mitm_h2)

    def test_zhibo8_config_rule(self) -> None:
        lines = read_entries(ROOT / "src/apps/zhibo8/url-rewrite.list")
        pattern = re.compile(lines[0].split()[0])
        self.assertRegex("https://a.qiumibao.com/activities/config.php", pattern)
        self.assertRegex("https://a.qiumibao.com/activities/config.php?platform=ios", pattern)
        self.assertNotRegex("https://example.com/activities/config.php", pattern)
        self.assertNotRegex("https://a.qiumibao.com/activities/config.phpx", pattern)

    def test_zhibo8_content_ad_rule_is_host_limited(self) -> None:
        lines = read_entries(ROOT / "src/apps/zhibo8/url-rewrite.list")
        pattern_text = lines[2].split()[0]
        pattern = re.compile(pattern_text)
        self.assertNotIn(".+?", pattern_text)
        self.assertRegex(
            "http://118.178.168.156:8091/allOne.php?ad_name=main_splash",
            pattern,
        )
        self.assertRegex(
            "http://47.111.8.123:8091/allOne.php?ad_name=top_comment&pk=1",
            pattern,
        )
        self.assertNotRegex(
            "http://example.com/allOne.php?ad_name=main_splash",
            pattern,
        )

    def test_amap_component_is_separate_from_core(self) -> None:
        core_lines = (
            read_entries(ROOT / "src/core/url-rewrite.list")
            + read_entries(ROOT / "src/core/script.list")
            + read_entries(ROOT / "src/core/mitm.list")
        )
        self.assertFalse(any("amap" in line.lower() for line in core_lines))

        amap_lines = read_entries(ROOT / "src/apps/amap/url-rewrite.list")
        self.assertEqual(len(amap_lines), 6)
        scripts = read_entries(ROOT / "src/apps/amap/script.list")
        self.assertEqual(len(scripts), 1)
        _, fields = parse_script(scripts[0])
        self.assertEqual(fields["type"], "http-response")
        self.assertEqual(fields["requires-body"], "1")
        self.assertEqual(fields["max-size"], "0")
        self.assertNotIn("/master/", fields["script-path"])
        self.assertEqual(read_entries(ROOT / "src/apps/amap/mitm.list"), ["*.amap.com"])

    def test_amap_rewrites_cover_ads_without_normal_features(self) -> None:
        lines = read_entries(ROOT / "src/apps/amap/url-rewrite.list")
        patterns = [re.compile(line.split()[0]) for line in lines]

        def matches(url: str) -> bool:
            return any(pattern.search(url) for pattern in patterns)

        self.assertTrue(
            matches("https://m5-zb.amap.com/ws/aos/alimama/splash_screen?channel=ios")
        )
        self.assertTrue(
            matches("https://m5-zb.amap.com/ws/asa/ads_attribution?scene=home")
        )
        self.assertTrue(
            matches("https://optimus-ads.amap.com/uploadimg/ABC123.gif")
        )
        self.assertTrue(matches("https://m5-zb.amap.com/v2/ai_rec/?scene=home"))
        self.assertTrue(
            matches("https://m5.amap.com/ws/shield/scene/recommend?scene=home")
        )
        self.assertFalse(
            matches("https://m5-zb.amap.com/ws/valueadded/alimama/splash_screen?channel=ios")
        )
        self.assertFalse(matches("https://m5.amap.com/ws/valueadded/weather"))
        self.assertFalse(matches("https://m5.amap.com/ws/msgbox/pull"))
        self.assertFalse(matches("https://m5-zb.amap.com/ws/boss/order_web/tips_information"))
        self.assertFalse(matches("https://m5.amap.com/ws/mapapi/hint_text/offline_data"))
        self.assertFalse(matches("https://render-oss-cdn.amap.com/render/studio-dev/image/a.png"))
        self.assertFalse(matches("https://example.com/ws/asa/ads_attribution"))

    def test_amap_script_targets_mixed_json_endpoints(self) -> None:
        line = read_entries(ROOT / "src/apps/amap/script.list")[0]
        _, fields = parse_script(line)
        pattern = re.compile(fields["pattern"])

        endpoints = (
            "ws/faas/amap-navigation/main-page",
            "ws/message/notice/list",
            "ws/msgbox/pull",
            "ws/promotion-web/resource",
            "ws/shield/dsp/profile/index/nodefaasv3",
            "ws/shield/frogserver/aocs/updatable",
            "ws/shield/search/nearbyrec_smart",
            "ws/shield/search/new_hotword",
            "ws/valueadded/alimama/splash_screen",
        )
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                self.assertRegex(f"https://m5-zb.amap.com/{endpoint}?platform=ios", pattern)

        for url in (
            "https://m5.amap.com/ws/faas/amap-navigation/main-page-assets",
            "https://sns.amap.com/ws/msgbox/pull_mp",
            "https://m5.amap.com/ws/shield/search/new_hotword_extra",
            "https://example.com/ws/message/notice/list",
        ):
            with self.subTest(url=url):
                self.assertNotRegex(url, pattern)

    def test_main_module_contains_amap_component_once(self) -> None:
        main = next(profile for profile in all_profiles() if profile.output.name == "adblock.module")
        main_data = collect(main)
        for line in read_entries(ROOT / "src/apps/amap/url-rewrite.list"):
            self.assertEqual(main_data.rewrites.count(line), 1)
        amap_script = read_entries(ROOT / "src/apps/amap/script.list")[0]
        self.assertEqual(main_data.scripts.count(amap_script), 1)
        self.assertEqual(main_data.hostnames.count("*.amap.com"), 1)

    def test_youtube_component_is_standalone_and_complete(self) -> None:
        core_lines = (
            read_entries(ROOT / "src/core/url-rewrite.list")
            + read_entries(ROOT / "src/core/script.list")
            + read_entries(ROOT / "src/core/mitm.list")
        )
        self.assertFalse(any("youtubei" in line.lower() for line in core_lines))

        rules = read_entries(ROOT / "src/apps/youtube/rule.list")
        self.assertEqual(
            rules,
            [
                "AND,((DOMAIN-SUFFIX,googlevideo.com),(PROTOCOL,UDP)),REJECT",
                "AND,((DOMAIN,youtubei.googleapis.com),(PROTOCOL,UDP)),REJECT",
            ],
        )
        self.assertEqual(len(read_entries(ROOT / "src/apps/youtube/url-rewrite.list")), 5)
        self.assertEqual(
            set(read_entries(ROOT / "src/apps/youtube/mitm.list")),
            {
                "-redirector*.googlevideo.com",
                "*.googlevideo.com",
                "s.youtube.com",
                "www.youtube.com",
                "youtubei.googleapis.com",
            },
        )
        scripts = read_entries(ROOT / "src/apps/youtube/script.list")
        self.assertEqual(len(scripts), 1)
        self.assertNotIn("workers.dev", "\n".join(scripts))
        self.assertNotIn("init-stream", "\n".join(scripts))
        self.assertNotIn("youtube.ump.js", "\n".join(scripts))
        self.assertNotIn("youtube.request.js", "\n".join(scripts))

        parsed = dict(parse_script(line) for line in scripts)
        self.assertEqual(set(parsed), {"youtube_response"})
        self.assertEqual(parsed["youtube_response"]["type"], "http-response")

        pinned_commit = "338320b364a0d6fb60fdeb60bb0407627085119b"
        for fields in parsed.values():
            self.assertEqual(fields["requires-body"], "1")
            self.assertEqual(fields["binary-body-mode"], "1")
            self.assertEqual(fields["max-size"], "-1")
            self.assertNotIn("engine", fields)
            self.assertEqual(fields["argument"], '"{}"')
            self.assertIn(f"/{pinned_commit}/", fields["script-path"])

        self.assertTrue(
            parsed["youtube_response"]["script-path"].endswith(
                "scripts/youtube-response.js"
            )
        )

        lock = json.loads((ROOT / "third_party/scripts.json").read_text(encoding="utf-8"))
        runtime = lock["akiralereal/shadowrocket-toolkit"]
        self.assertEqual(runtime["commit"], pinned_commit)
        self.assertEqual(
            runtime["files"]["scripts/youtube-response.js"],
            "c7d73339f4d802ccb02a02f18fa720889042afe31d498900590d99012dc9e5c8",
        )

    def test_youtube_script_targets_ads_and_playback_only(self) -> None:
        parsed = dict(
            parse_script(line)
            for line in read_entries(ROOT / "src/apps/youtube/script.list")
        )
        response_pattern = re.compile(parsed["youtube_response"]["pattern"])

        for endpoint in (
            "browse",
            "next",
            "player",
            "search",
            "reel/reel_watch_sequence",
            "guide",
            "account/get_setting",
            "get_watch",
        ):
            with self.subTest(endpoint=endpoint):
                self.assertRegex(
                    f"https://youtubei.googleapis.com/youtubei/v1/{endpoint}?key=test",
                    response_pattern,
                )
                self.assertRegex(
                    f"https://youtubei.googleapis.com/youtubei/v1/{endpoint}/",
                    response_pattern,
                )

        for endpoint in ("initplayback", "subscription/list", "log_event", "config"):
            with self.subTest(endpoint=endpoint):
                self.assertNotRegex(
                    f"https://youtubei.googleapis.com/youtubei/v1/{endpoint}",
                    response_pattern,
                )

        self.assertNotRegex(
            "https://youtubei.googleapis.com/youtubei/v1/playerX",
            response_pattern,
        )
        self.assertNotRegex(
            "https://example.com/youtubei/v1/player",
            response_pattern,
        )

    def test_youtube_dependency_does_not_allow_external_worker(self) -> None:
        audit = (ROOT / "tools/audit_scripts.py").read_text(encoding="utf-8")
        self.assertIn('b".workers.dev"', audit)
        self.assertIn('b"init-stream"', audit)
        self.assertNotIn("EXPECTED_RUNTIME_ENDPOINTS", audit)
        self.assertNotIn("youtube.request.js", audit)

    def test_youtube_forces_scoped_https_fallback(self) -> None:
        rules = read_entries(ROOT / "src/apps/youtube/rule.list")
        for rule in rules:
            validate_rule(rule)

        with self.assertRaises(ModuleError):
            validate_rule("AND,((PROTOCOL,UDP),(DEST-PORT,443)),REJECT-NO-DROP")
        with self.assertRaises(ModuleError):
            validate_rule("DOMAIN-SUFFIX,googlevideo.com,REJECT")

        youtube = next(
            profile for profile in all_profiles() if profile.output.name == "youtube.module"
        )
        content = render(youtube)
        self.assertIn("[Rule]\n" + "\n".join(rules), content)
        self.assertIn("[MITM]\nhostname = %APPEND% ", content)
        self.assertNotIn("h2 = true", content)
        self.assertNotIn("[General]", content)
        self.assertNotIn("block-quic", content)
        self.assertNotIn("workers.dev", content)
        self.assertNotIn("init-stream", content)

    def test_spotify_modules_are_standalone_and_compatible(self) -> None:
        profiles = {profile.output.name: profile for profile in all_profiles()}
        vip = profiles["spotify.module"]
        lyric = profiles["spotify-lyric.module"]
        vip_data = collect(vip)
        lyric_data = collect(lyric)

        self.assertEqual(len(vip_data.header_rewrites), 1)
        header_parts = vip_data.header_rewrites[0].split()
        self.assertEqual(header_parts[0], "http-request")
        self.assertEqual(header_parts[2:], ["header-del", "if-none-match"])
        header_pattern = re.compile(header_parts[1])
        for host in (
            "spclient.wg.spotify.com",
            "gae2-spclient.spotify.com:443",
        ):
            self.assertRegex(
                f"https://{host}/user-customization-service/v1/customize",
                header_pattern,
            )

        self.assertEqual(
            set(vip_data.hostnames),
            {"*spclient.spotify.com", "spclient.wg.spotify.com"},
        )
        self.assertEqual(lyric_data.hostnames, ("spclient.wg.spotify.com",))

        vip_scripts = dict(parse_script(line) for line in vip_data.scripts)
        lyric_scripts = dict(parse_script(line) for line in lyric_data.scripts)
        self.assertEqual(set(vip_scripts), {"spotify_request", "spotify_response"})
        self.assertEqual(set(lyric_scripts), {"spotify_lyrics"})
        self.assertTrue(set(vip_scripts).isdisjoint(lyric_scripts))
        pinned_commit = "338320b364a0d6fb60fdeb60bb0407627085119b"
        for fields in (*vip_scripts.values(), *lyric_scripts.values()):
            self.assertIn(f"/{pinned_commit}/", fields["script-path"])
        self.assertEqual(vip_scripts["spotify_request"]["requires-body"], "0")
        self.assertEqual(vip_scripts["spotify_response"]["binary-body-mode"], "1")
        self.assertEqual(lyric_scripts["spotify_lyrics"]["binary-body-mode"], "1")
        self.assertEqual(lyric_scripts["spotify_lyrics"]["timeout"], "10")

        request_pattern = re.compile(vip_scripts["spotify_request"]["pattern"])
        response_pattern = re.compile(vip_scripts["spotify_response"]["pattern"])
        lyric_pattern = re.compile(lyric_scripts["spotify_lyrics"]["pattern"])

        self.assertRegex(
            "https://spclient.wg.spotify.com/artistview/v1/artist/123",
            request_pattern,
        )
        self.assertRegex(
            "https://gae2-spclient.spotify.com:443/album-entity-view/v2/album/123",
            request_pattern,
        )
        for endpoint in (
            "bootstrap/v1/bootstrap",
            "user-customization-service/v1/customize",
        ):
            self.assertRegex(
                f"https://spclient.wg.spotify.com/{endpoint}",
                response_pattern,
            )
        self.assertRegex(
            "https://spclient.wg.spotify.com/color-lyrics/v2/track/abc?format=protobuf",
            lyric_pattern,
        )
        self.assertNotRegex(
            "https://spclient.wg.spotify.com/color-lyrics/v2/track/abc",
            response_pattern,
        )
        self.assertNotRegex(
            "https://spclient.wg.spotify.com/bootstrap/v1/bootstrap",
            lyric_pattern,
        )

        self.assertEqual(lyric.arguments, "appid:,securityKey:")
        lyric_content = render(lyric)
        self.assertIn("#!arguments=appid:,securityKey:\n", lyric_content)
        self.assertIn("argument=appid={{{appid}}}&securityKey={{{securityKey}}}", lyric_content)
        self.assertNotIn("appid=111", lyric_content)

        lock = json.loads((ROOT / "third_party/scripts.json").read_text(encoding="utf-8"))
        runtime = lock["akiralereal/shadowrocket-toolkit"]
        self.assertEqual(runtime["commit"], pinned_commit)
        self.assertEqual(
            {
                path: runtime["files"][path]
                for path in (
                    "scripts/spotify-json.js",
                    "scripts/spotify-lyric.js",
                    "scripts/spotify-proto.js",
                )
            },
            {
                "scripts/spotify-json.js": "41cf1074770cdef3948baa12ff4a8db9045d1cac888714c8b7e69909eb531bc9",
                "scripts/spotify-lyric.js": "1705a240e8e30a53af0e6e102526255091ea3cb90ea4db19ad8d767dbb45679a",
                "scripts/spotify-proto.js": "2e6850e888d092905c766f0bbedc4b4afb9a712330970cc1265105d7fb4995d0",
            },
        )

    def test_spotify_lyric_runtime_has_a_single_guarded_external_api(self) -> None:
        script = (ROOT / "scripts/spotify-lyric.js").read_text(encoding="utf-8")
        urls = set(re.findall(r'https?://[^"\s]+', script))
        self.assertEqual(
            urls,
            {"https://fanyi-api.baidu.com/api/trans/vip/translate"},
        )
        self.assertIn("if (!appid || !securityKey)", script)
        self.assertLess(
            script.index("if (!appid || !securityKey)"),
            script.index("$httpClient.post"),
        )
        self.assertIn("finishOriginal()", script)
        lowered = script.lower()
        for marker in ("app2smile", "chavyleung", "yfamily", "github.com"):
            self.assertNotIn(marker, lowered)

    def test_exact_ad_domain_rule_validation_is_narrow(self) -> None:
        validate_rule("DOMAIN,ads.example.com,REJECT,extended-matching")

        for unsafe in (
            "DOMAIN-SUFFIX,example.com,REJECT,extended-matching",
            "DOMAIN,ads.example.com,REJECT",
            "DOMAIN,ads.example.com,REJECT,extended-matching,pre-matching",
            "DOMAIN,*.example.com,REJECT,extended-matching",
        ):
            with self.subTest(rule=unsafe), self.assertRaises(ModuleError):
                validate_rule(unsafe)

        with self.assertRaises(ModuleError):
            validate_data(
                ModuleData(
                    rules=(
                        "DOMAIN,login.example.com,REJECT,extended-matching",
                    ),
                    rewrites=(),
                    scripts=(),
                    hostnames=(),
                )
            )

    def test_core_domain_rules_are_curated(self) -> None:
        lines = read_entries(ROOT / "src/core/rule.list")
        hosts = [line.split(",")[1] for line in lines]

        self.assertEqual(len(lines), 255)
        self.assertEqual(len(hosts), len(set(hosts)))
        self.assertEqual(hosts, sorted(hosts))
        self.assertTrue(
            all(
                line == f"DOMAIN,{host},REJECT,extended-matching"
                for line, host in zip(lines, hosts)
            )
        )

        expected = {
            "ad.qq.com",
            "ads.tiktok.com",
            "d.applovin.com",
            "pagead2.googlesyndication.com",
            "webview.unityads.unity3d.com",
            "wxsnsad.tc.qq.com",
        }
        self.assertTrue(expected.issubset(hosts))

        protected = {
            "ad.ximalaya.com",
            "ads.95516.com",
            "ads.cup.com.cn",
            "ads.youtube.com",
            "adx-cn.anythinktech.com",
            "api-access.pangolin-sdk-toutiao.com",
            "api-access.pangolin-sdk-toutiao1.com",
            "api.installer.xiaomi.com",
            "dsp-x.jd.com",
            "hc-ssp.sm.cn",
            "mi.gdt.qq.com",
            "mobads.baidu.com",
            "open.e.kuaishou.com",
            "optimus-ads.amap.com",
            "pay.sboot.cn",
            "safebrowsing.urlsec.gg.com",
            "sdk.1rtb.net",
            "statsigapi.net",
            "update.avlyun.sec.miui.com",
            "vipauth.hpplay.cn",
        }
        self.assertTrue(protected.isdisjoint(hosts))
        self.assertFalse(any("pre-matching" in line for line in lines))

    def test_domain_rule_merging_uses_the_matcher_not_modifiers(self) -> None:
        rule = "DOMAIN,ads.example.com,REJECT,extended-matching"
        self.assertEqual(_merge_rules((rule, rule)), (rule,))
        with self.assertRaises(ModuleError):
            _merge_rules(
                (
                    rule,
                    "DOMAIN,ads.example.com,DIRECT,extended-matching",
                )
            )

    def test_youtube_rewrites_match_expected_chain(self) -> None:
        lines = read_entries(ROOT / "src/apps/youtube/url-rewrite.list")
        self.assertEqual(len(lines), 5)
        for line in lines:
            validate_rewrite(line)

        self.assertIn("ctier=L", lines[0])
        self.assertIn("&oad", lines[1])
        for line in lines[1:]:
            self.assertEqual(line.split()[-2:], ["_", "reject-200"])

        ctier_pattern = re.compile(lines[0].split()[0])
        self.assertRegex(
            "https://rr1---sn-test.googlevideo.com/initplayback?id=1&ctier=L&foo=2,ctier,H",
            ctier_pattern,
        )

        oad_pattern = re.compile(lines[1].split()[0])
        self.assertRegex(
            "https://rr1---sn-test.googlevideo.com/initplayback?id=1&oad=1",
            oad_pattern,
        )
        self.assertNotRegex(
            "https://rr1---sn-test.googlevideo.com/videoplayback?id=1&oad=1",
            oad_pattern,
        )
        self.assertNotRegex(
            "https://rr1---sn-test.googlevideo.com/dclk_video_ads?id=1&oad=1",
            oad_pattern,
        )

        self.assertRegex("https://www.youtube.com/api/stats/ads?ver=2", re.compile(lines[2].split()[0]))
        self.assertRegex("https://s.youtube.com/pagead?id=1", re.compile(lines[3].split()[0]))
        self.assertRegex(
            "https://s.youtube.com/api/stats/qoe?adcontext=1",
            re.compile(lines[4].split()[0]),
        )

    def test_negative_mitm_hostname_validation_is_narrow(self) -> None:
        validate_hostname("*spclient.spotify.com")
        validate_hostname("-redirector*.googlevideo.com")
        validate_hostname("-*.googlevideo.com")
        validate_hostname("-redirector.googlevideo.com")
        with self.assertRaises(ModuleError):
            validate_hostname("redirector*.googlevideo.com")
        with self.assertRaises(ModuleError):
            validate_hostname("**spclient.spotify.com")
        with self.assertRaises(ModuleError):
            validate_hostname("-redirector**.googlevideo.com")

    def test_header_rewrite_validation_is_narrow(self) -> None:
        line = (
            r"http-request ^https:\/\/spclient\.wg\.spotify\.com/path$ "
            "header-del if-none-match"
        )
        validate_header_rewrite(line)
        validate_data(
            ModuleData(
                rules=(),
                rewrites=(),
                scripts=(),
                hostnames=("spclient.wg.spotify.com",),
                header_rewrites=(line,),
            )
        )

        for unsafe in (
            r"http-response ^https:\/\/spclient\.wg\.spotify\.com/path$ header-del etag",
            r"http-request ^https:\/\/spclient\.wg\.spotify\.com/path$ header-set etag",
            r"http-request .* header-del bad:header",
        ):
            with self.subTest(entry=unsafe), self.assertRaises(ModuleError):
                validate_header_rewrite(unsafe)

    def test_main_module_excludes_youtube(self) -> None:
        main = next(profile for profile in all_profiles() if profile.output.name == "adblock.module")
        main_data = collect(main)
        combined = (
            *main_data.rules,
            *main_data.rewrites,
            *main_data.scripts,
            *main_data.hostnames,
        )
        self.assertFalse(any("youtube" in line.lower() for line in combined))
        self.assertFalse(any("googlevideo" in line.lower() for line in combined))
        self.assertNotIn("h2 = true", render(main))

    def test_existing_modules_exclude_spotify(self) -> None:
        for output in ("adblock.module", "youtube.module"):
            profile = next(
                profile for profile in all_profiles() if profile.output.name == output
            )
            data = collect(profile)
            combined = (
                *data.rules,
                *data.header_rewrites,
                *data.rewrites,
                *data.scripts,
                *data.hostnames,
            )
            with self.subTest(output=output):
                self.assertFalse(any("spotify" in line.lower() for line in combined))
                self.assertFalse(any("spclient" in line.lower() for line in combined))


if __name__ == "__main__":
    unittest.main()
