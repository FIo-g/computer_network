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


def valid_task2_data():
    """보고서 테스트용으로 두 네트워크의 완전한 원시 자료를 만든다."""
    data = {}
    for site in t2.SITES:
        measurements = {}
        for network in ("campus-wifi", "phone-tethering"):
            address = "192.0.2.10"
            if site == "www.microsoft.com" and network == "phone-tethering":
                address = "192.0.2.20"
            measurements[network] = {
                "chain": [site],
                "original_zone": "example.net",
                "final_zone": "example.net",
                "resolver_addresses": {
                    "system": [address],
                    "google": [address],
                    "quad9": [address],
                },
                "errors": {},
            }
        data[site] = {"measurements": measurements}
    return data


def valid_task2_evidence():
    """사람이 확인해야 하는 필드를 빠짐없이 갖춘 예시를 만든다."""
    classifications = {
        site: {
            "cdn_hosted": site in {"www.microsoft.com", "www.netflix.com"},
            "third_party": site == "www.microsoft.com",
            "reason": f"reviewed ownership for {site}",
        }
        for site in t2.SITES
    }
    return {
        "capture": {
            "source_type": "own-capture",
            "matched_query_packet": 12,
            "matched_response_packet": 13,
            "transaction_id": "0x4a2f",
            "delegation_response_packet": 17,
            "answer_response_packet": 23,
            "largest_response": {
                "packet": 17,
                "dns_message_bytes": 512,
                "frame_bytes": 554,
                "reason": "Authority NS and additional glue records made it large.",
            },
        },
        "network_notes": {
            "campus-wifi": "Campus wireless network.",
            "phone-tethering": "Phone tethering network.",
        },
        "classifications": classifications,
        "steering_conclusion": (
            "The difference is consistent with steering, but resolver caches, "
            "temporal load balancing, and anycast prevent a proximity proof."
        ),
    }


class TestTask2Report(unittest.TestCase):
    def write_json(self, path, value):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(value, handle)

    def test_report_renders_required_table_capture_and_steering_number(self):
        data = valid_task2_data()
        evidence = valid_task2_evidence()
        with tempfile.TemporaryDirectory() as directory:
            chains_path = os.path.join(directory, "chains.json")
            evidence_path = os.path.join(directory, "task2_evidence.json")
            report_path = os.path.join(directory, "report.md")
            capture_path = os.path.join(directory, "dns.pcapng")
            self.write_json(chains_path, data)
            self.write_json(evidence_path, evidence)
            with open(capture_path, "wb") as handle:
                handle.write(b"captured-by-test")

            text = t2.report(chains_path, evidence_path, report_path, capture_path)

            self.assertIn(
                "| site | chain length | final zone | third party? | rule verdict |",
                text,
            )
            self.assertIn(
                "Rule: final authoritative zone differs from original authoritative zone.",
                text,
            )
            self.assertIn(
                "1 of 2 CDN-hosted sites answered differently to a different resolver or network.",
                text,
            )
            self.assertIn("campus-wifi", text)
            self.assertIn("phone-tethering", text)
            self.assertIn("transaction ID `0x4a2f`", text)
            self.assertIn("delegation response: 17", text)
            self.assertIn("answer response: 23", text)
            self.assertIn("DNS message bytes: 512", text)
            self.assertIn("www.microsoft.com", text)
            with open(report_path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), text)

    def test_first_party_cdn_is_in_denominator(self):
        self.assertEqual(
            t2.steering_count(valid_task2_data(), valid_task2_evidence()),
            (1, 2),
        )

    def test_incomplete_classification_is_rejected(self):
        evidence = valid_task2_evidence()
        evidence["classifications"].pop("www.cnn.com")

        with self.assertRaisesRegex(t2.LookupFailure, "classifications"):
            t2.validate_report_inputs(valid_task2_data(), evidence, "capture.pcapng")

    def test_generic_network_label_is_rejected(self):
        data = valid_task2_data()
        for site_data in data.values():
            site_data["measurements"]["network-1"] = site_data["measurements"].pop(
                "campus-wifi"
            )
        evidence = valid_task2_evidence()
        evidence["network_notes"]["network-1"] = evidence["network_notes"].pop(
            "campus-wifi"
        )

        with self.assertRaisesRegex(t2.LookupFailure, "named networks"):
            t2.validate_report_inputs(data, evidence, "capture.pcapng")

    def test_recorded_lookup_error_blocks_report(self):
        data = valid_task2_data()
        data["www.cnn.com"]["measurements"]["campus-wifi"]["errors"] = {
            "resolver:google": "timeout"
        }

        with self.assertRaisesRegex(t2.LookupFailure, "lookup errors"):
            t2.validate_report_inputs(data, valid_task2_evidence(), "capture.pcapng")

    def test_rule_must_disagree_with_at_least_one_reviewed_judgment(self):
        evidence = valid_task2_evidence()
        evidence["classifications"]["www.microsoft.com"]["third_party"] = False

        with self.assertRaisesRegex(t2.LookupFailure, "rule mismatch"):
            t2.validate_report_inputs(valid_task2_data(), evidence, "capture.pcapng")

    def test_official_trace_requires_exact_attribution(self):
        evidence = valid_task2_evidence()
        evidence["capture"]["source_type"] = "official-trace"

        with self.assertRaisesRegex(t2.LookupFailure, "attribution"):
            t2.validate_report_inputs(valid_task2_data(), evidence, None)

        evidence["capture"]["attribution"] = t2.OFFICIAL_ATTRIBUTION
        evidence["capture"]["whose_machine_and_evidence"] = (
            "The trace header and addresses identify the textbook lab host."
        )
        networks = t2.validate_report_inputs(valid_task2_data(), evidence, None)
        self.assertEqual(networks, ["campus-wifi", "phone-tethering"])


if __name__ == "__main__":
    unittest.main()
