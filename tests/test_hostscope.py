from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from hostscope import host_pattern_is_covered, hostname_is_covered, https_host_patterns
from modulelib import ModuleData, ModuleError, all_profiles, collect
from validate import validate_data


class HostScopeTests(unittest.TestCase):
    def test_finite_alternatives_and_optional_labels_are_all_checked(self):
        self.assertEqual(
            https_host_patterns(r"^https?://m?api\.weibo\.(?:cn|com)/ad"),
            ("api.weibo.cn", "api.weibo.com", "mapi.weibo.cn", "mapi.weibo.com"),
        )
        self.assertEqual(
            https_host_patterns(r"^https?://api-access\.pangolin-sdk-toutiao(?:1)?\.com/ads"),
            ("api-access.pangolin-sdk-toutiao.com", "api-access.pangolin-sdk-toutiao1.com"),
        )
        data = ModuleData((), (r"^https://(?:ads|cdn)\.example\.com/ad reject",), (), ("ads.example.com",))
        with self.assertRaisesRegex(ModuleError, "cdn.example.com"):
            validate_data(data)
        validate_data(replace(data, hostnames=("ads.example.com", "cdn.example.com")))

    def test_escaped_slashes_ports_and_variable_subdomains(self):
        self.assertEqual(
            https_host_patterns(r"^https:\/\/(?:spclient\.wg\.spotify\.com|[A-Za-z0-9-]+-spclient\.spotify\.com(?::443)?)\/path$"),
            ("*-spclient.spotify.com", "spclient.wg.spotify.com"),
        )
        self.assertEqual(
            https_host_patterns(r"^https?://(?:[A-Za-z0-9-]+\.)+amap\.com/path"),
            ("*.amap.com",),
        )
        self.assertEqual(https_host_patterns(r"^https://api\.example\.com:443/path"), ("api.example.com",))
        self.assertEqual(https_host_patterns(r"^https://[^/]+\.ximalaya\.com/path"), ("*.ximalaya.com",))
        self.assertEqual(https_host_patterns(r"^https://api\.example\.com(?:/|$)"), ("api.example.com",))
        self.assertEqual(https_host_patterns(r"^http://127\.0\.0\.1:8080/path"), ())

    def test_spotify_cannot_pass_without_mitm(self):
        spotify = collect(next(p for p in all_profiles() if p.path.stem == "spotify"))
        for hosts in ((), ("spclient.wg.spotify.com",), ("*spclient.spotify.com",)):
            with self.subTest(hostnames=hosts), self.assertRaisesRegex(ModuleError, "MITM"):
                validate_data(replace(spotify, hostnames=hosts))
        validate_data(spotify)

    def test_scripts_with_escaped_literal_hosts_require_mitm(self):
        script = (
            r"sample=type=http-response,pattern=^https:\/\/api\.example\.com\/ad,"
            "requires-body=1,script-path=https://raw.githubusercontent.com/owner/repo/"
            + "a" * 40 + "/scripts/test.js"
        )
        data = ModuleData((), (), (script,), ())
        with self.assertRaisesRegex(ModuleError, "api.example.com"):
            validate_data(data)
        validate_data(replace(data, hostnames=("api.example.com",)))

    def test_negative_hosts_override_positive_matches(self):
        hosts = {"*.googlevideo.com", "-redirector*.googlevideo.com"}
        self.assertFalse(hostname_is_covered("redirector.googlevideo.com", hosts))
        self.assertFalse(hostname_is_covered("redirector1.googlevideo.com", hosts))
        self.assertTrue(hostname_is_covered("r1.googlevideo.com", hosts))
        self.assertFalse(hostname_is_covered("googlevideo.com", hosts))
        self.assertTrue(host_pattern_is_covered("*.googlevideo.com", hosts))
        self.assertFalse(host_pattern_is_covered("redirector*.googlevideo.com", hosts))
        self.assertFalse(host_pattern_is_covered("*.googlevideo.com", {"*.googlevideo.com", "-*.googlevideo.com"}))
        with self.assertRaisesRegex(ModuleError, "excluded"):
            validate_data(ModuleData((), (r"^https://redirector\.googlevideo\.com/ad reject",), (), tuple(hosts)))

    def test_wildcard_scopes_require_sufficient_coverage(self):
        self.assertTrue(host_pattern_is_covered("p*.meituan.net", {"*.meituan.net"}))
        self.assertTrue(host_pattern_is_covered("*-spclient.spotify.com", {"*spclient.spotify.com"}))
        self.assertFalse(host_pattern_is_covered("*.example.com", {"ads.example.com"}))
        self.assertFalse(host_pattern_is_covered("*.example.com", {"*.other.com"}))

    def test_unverifiable_patterns_fail_instead_of_skipping_mitm(self):
        for pattern in (
            r".*", r"^https://(?=api)api\.example\.com/ads", r"^https://.+/ads",
            r"^https://[a-z/]+\.example\.com/ads", r"^https://ads\.example\.com/ads|.*",
            r"^http://ads\.example\.com/ads|^https://api\.example\.com/ads",
            r"(^https://ads\.example\.com/ads|.*)",
        ):
            with self.subTest(pattern=pattern), self.assertRaises(ModuleError):
                validate_data(ModuleData((), (pattern + " reject",), (), ("*.example.com",)))

    def test_shared_cdn_images_and_videos_are_not_blocked(self):
        import re

        data = collect(next(p for p in all_profiles() if p.path.stem == "adblock"))
        patterns = [re.compile(line.split()[0]) for line in data.rewrites]
        for url in (
            "https://fuss10.elemecdn.com/product/dish/w/640/h/480",
            "https://fuss10.elemecdn.com/product/dish/w/750/h/1000?format=webp",
            "https://fuss10.elemecdn.com/product/demo.mp4",
            "https://fuss10.elemecdn.com/product/demo.mp4?token=test",
        ):
            self.assertFalse(any(pattern.search(url) for pattern in patterns), url)
        self.assertNotIn("fuss10.elemecdn.com", data.hostnames)


if __name__ == "__main__":
    unittest.main()
