import unittest

from scripts.test_proxies import parse_proxies


class ProxyParserTests(unittest.TestCase):
    def test_protocol_prefixed_entries_and_socks4_filter(self):
        proxies, excluded = parse_proxies(
            "http://1.2.3.4:80\nsocks5://2.3.4.5:1080\nsocks4://3.4.5.6:1080\n"
        )
        self.assertEqual(
            proxies,
            {"http://1.2.3.4:80", "socks5://2.3.4.5:1080"},
        )
        self.assertEqual(excluded, 1)

    def test_hproxy_bare_entries_expand_to_supported_protocols(self):
        proxies, excluded = parse_proxies("1.2.3.4:8080\n", expand_bare=True)
        self.assertEqual(
            proxies,
            {
                "http://1.2.3.4:8080",
                "https://1.2.3.4:8080",
                "socks5://1.2.3.4:8080",
            },
        )
        self.assertEqual(excluded, 0)

    def test_invalid_ports_are_ignored(self):
        proxies, _ = parse_proxies("1.2.3.4:0\n1.2.3.4:65536\n1.2.3.4:abc\n")
        self.assertEqual(proxies, set())


if __name__ == "__main__":
    unittest.main()
