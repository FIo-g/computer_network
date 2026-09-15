#!/usr/bin/env python3
"""Task 2 DNS steering의 결정적 단위 테스트다."""
import json
import os
import tempfile
import unittest

import task2_steering as t2


class TestTask2Collection(unittest.TestCase):
    @staticmethod
    def fake_lookup(name, rtype="A", server=None):
        name = name.rstrip(".").lower()
        cname_map = {
            "www.microsoft.com": ["edge.microsoft.example."],
            "edge.microsoft.example": ["node.cdn.example."],
        }
        if rtype == "CNAME":
            return cname_map.get(name, [])
        if rtype == "SOA":
            labels = name.split(".")
            if len(labels) == 2:
                return ["ns.example. hostmaster.example. 1 3600 600 86400 60"]
            return []
        if rtype == "A":
            addresses = {
                None: "192.0.2.10",
                "8.8.8.8": "192.0.2.11",
                "9.9.9.9": "192.0.2.12",
            }
            return [addresses[server], addresses[server], "alias.example."]
        raise AssertionError(f"unexpected type {rtype}")

    def test_follows_each_cname_edge(self):
        chain = t2.follow_cname_chain("WWW.Microsoft.COM.", self.fake_lookup)

        self.assertEqual(
            chain,
            ["www.microsoft.com", "edge.microsoft.example", "node.cdn.example"],
        )
        self.assertEqual(len(chain) - 1, 2)

    def test_no_cname_keeps_only_original_name(self):
        chain = t2.follow_cname_chain("www.korea.ac.kr", self.fake_lookup)

        self.assertEqual(chain, ["www.korea.ac.kr"])

    def test_cname_loop_is_rejected(self):
        def looping(name, rtype="A", server=None):
            if name == "a.example":
                return ["b.example."]
            return ["a.example."]

        with self.assertRaisesRegex(t2.LookupFailure, "loop"):
            t2.follow_cname_chain("a.example", looping)

    def test_zone_search_uses_soa_suffix(self):
        calls = []

        def lookup(name, rtype="A", server=None):
            calls.append((name, rtype, server))
            if name == "bbc.co.uk" and rtype == "SOA":
                return ["ns.bbc.co.uk. hostmaster.bbc.co.uk. 1 2 3 4 5"]
            return []

        zone = t2.authoritative_zone("edge.news.bbc.co.uk", lookup)

        self.assertEqual(zone, "bbc.co.uk")
        self.assertEqual(calls[-1], ("bbc.co.uk", "SOA", None))

    def test_cname_depth_is_rejected(self):
        def endless(name, rtype="A", server=None):
            number = int(name[4:])
            return [f"node{number + 1}."]

        with self.assertRaisesRegex(t2.LookupFailure, "depth"):
            t2.follow_cname_chain("node0", endless, max_edges=2)

    def test_ipv4_answers_filters_aliases_and_duplicates(self):
        values = ["alias.example.", "192.0.2.2", "192.0.2.1", "192.0.2.2", "2001:db8::1"]

        self.assertEqual(t2.ipv4_answers(values), ["192.0.2.1", "192.0.2.2"])

    def test_collect_creates_twelve_sites_and_merges_networks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "chains.json")
            first = t2.collect("campus-wifi", out_path=path, lookup=self.fake_lookup)
            second = t2.collect("phone-tethering", out_path=path, lookup=self.fake_lookup)

            self.assertEqual(set(first), set(t2.SITES))
            self.assertEqual(len(first), 12)
            self.assertEqual(
                set(second["www.microsoft.com"]["measurements"]),
                {"campus-wifi", "phone-tethering"},
            )
            measurement = second["www.microsoft.com"]["measurements"]["campus-wifi"]
            self.assertEqual(measurement["original_zone"], "microsoft.com")
            self.assertEqual(measurement["final_zone"], "cdn.example")
            self.assertEqual(
                measurement["resolver_addresses"]["google"], ["192.0.2.11"]
            )
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), second)

    def test_duplicate_network_requires_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "chains.json")
            t2.collect("campus-wifi", out_path=path, lookup=self.fake_lookup)

            with self.assertRaisesRegex(t2.LookupFailure, "already exists"):
                t2.collect("campus-wifi", out_path=path, lookup=self.fake_lookup)

            replaced = t2.collect(
                "campus-wifi", replace=True, out_path=path, lookup=self.fake_lookup
            )
            self.assertIn("campus-wifi", replaced["www.cnn.com"]["measurements"])


if __name__ == "__main__":
    unittest.main()
