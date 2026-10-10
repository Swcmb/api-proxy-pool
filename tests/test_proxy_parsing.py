import unittest

from scripts.test_proxies import MAX_PROXIES_TO_TEST, parse_proxies, select_candidates


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

    def test_candidate_selection_is_capped_and_reproducible(self):
        candidates = [f"http://192.0.2.{i % 250 + 1}:{1000 + i}" for i in range(6000)]
        selected = select_candidates(candidates)
        self.assertEqual(len(selected), MAX_PROXIES_TO_TEST)
        self.assertEqual(selected, select_candidates(candidates))
        self.assertEqual(selected, sorted(selected))

    def test_small_candidate_pool_is_preserved(self):
        candidates = ["http://192.0.2.1:8080"]
        self.assertEqual(select_candidates(candidates), candidates)

    def test_invalid_ports_are_ignored(self):
        proxies, _ = parse_proxies("1.2.3.4:0\n1.2.3.4:65536\n1.2.3.4:abc\n")
        self.assertEqual(proxies, set())


if __name__ == "__main__":
    unittest.main()
