#!/usr/bin/env python3
"""3주차 DNS 구현의 네트워크 비의존 단위 테스트."""

import subprocess
import unittest
from unittest.mock import patch

import task1_resolve as t1


def dns_record(owner, rtype, value):
    """테스트 응답을 짧고 읽기 쉽게 만든다."""
    return t1.DNSRecord(owner, rtype, value)


def dns_reply(*, authoritative=False, answers=(), authority=(), additional=(), status="NOERROR"):
    """리졸버 시나리오에 사용할 불변 응답을 만든다."""
    return t1.DNSReply(status, authoritative, tuple(answers), tuple(authority), tuple(additional))


class TestTask1DigParsing(unittest.TestCase):
    RESPONSE = """;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 1234
;; flags: qr aa; QUERY: 1, ANSWER: 2, AUTHORITY: 1, ADDITIONAL: 1

;; ANSWER SECTION:
www.example. 300 IN CNAME edge.example.
edge.example. 20 IN A 192.0.2.10

;; AUTHORITY SECTION:
example. 86400 IN NS ns1.example.

;; ADDITIONAL SECTION:
ns1.example. 86400 IN A 192.0.2.53
"""

    def test_parse_sections_and_authoritative_flag(self):
        reply = t1.parse_dig_output(self.RESPONSE)

        self.assertEqual(reply.status, "NOERROR")
        self.assertTrue(reply.authoritative)
        self.assertEqual(
            reply.answers,
            (
                dns_record("www.example", "CNAME", "edge.example"),
                dns_record("edge.example", "A", "192.0.2.10"),
            ),
        )
        self.assertEqual(reply.authority, (dns_record("example", "NS", "ns1.example"),))
        self.assertEqual(reply.additional, (dns_record("ns1.example", "A", "192.0.2.53"),))

    def test_malformed_header_is_rejected(self):
        with self.assertRaises(t1.ResolutionError):
            t1.parse_dig_output(";; ANSWER SECTION:\nwww.example. 30 IN A 192.0.2.1\n")

    def test_dig_query_is_explicitly_non_recursive(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=self.RESPONSE, stderr=""
        )
        with patch.object(t1.subprocess, "run", return_value=completed) as run:
            reply = t1.dig_query("198.41.0.4", "WWW.Example.")

        args = run.call_args.args[0]
        self.assertEqual(args[:4], ["dig", "@198.41.0.4", "www.example", "A"])
        self.assertIn("+norecurse", args)
        self.assertNotIn("+trace", args)
        self.assertEqual(reply.status, "NOERROR")

    def test_dig_failure_returns_none(self):
        completed = subprocess.CompletedProcess(args=[], returncode=9, stdout="", stderr="timeout")
        with patch.object(t1.subprocess, "run", return_value=completed):
            self.assertIsNone(t1.dig_query("192.0.2.53", "www.example"))


class TestTask1Resolver(unittest.TestCase):
    ROOT = t1.ROOT_SERVERS[0]

    @staticmethod
    def resolver(mapping, max_depth=32):
        def query(server, name):
            return mapping.get((server, name))

        return t1.Resolver(query=query, max_depth=max_depth)

    def test_walks_glue_referral_and_returns_authoritative_answer(self):
        mapping = {
            (self.ROOT, "www.example"): dns_reply(
                authority=[dns_record("example", "NS", "ns1.example")],
                additional=[dns_record("ns1.example", "A", "192.0.2.53")],
            ),
            ("192.0.2.53", "www.example"): dns_reply(
                authoritative=True,
                answers=[dns_record("www.example", "A", "192.0.2.10")],
            ),
        }

        address, path = self.resolver(mapping).resolve("WWW.Example.")

        self.assertEqual(address, "192.0.2.10")
        self.assertEqual(path, [self.ROOT, "192.0.2.53"])
        self.assertIn(path[0], t1.ROOT_SERVERS)

    def test_resolves_nameserver_without_glue_from_roots(self):
        mapping = {
            (self.ROOT, "www.example"): dns_reply(
                authority=[dns_record("example", "NS", "ns.external")]
            ),
            (self.ROOT, "ns.external"): dns_reply(
                authoritative=True,
                answers=[dns_record("ns.external", "A", "198.51.100.53")],
            ),
            ("198.51.100.53", "www.example"): dns_reply(
                authoritative=True,
                answers=[dns_record("www.example", "A", "192.0.2.20")],
            ),
        }

        address, path = self.resolver(mapping).resolve("www.example")

        self.assertEqual(address, "192.0.2.20")
        self.assertEqual(path, [self.ROOT, self.ROOT, "198.51.100.53"])

    def test_tries_next_nameserver_after_timeout(self):
        mapping = {
            (self.ROOT, "www.example"): dns_reply(
                authority=[
                    dns_record("example", "NS", "ns1.example"),
                    dns_record("example", "NS", "ns2.example"),
                ],
                additional=[
                    dns_record("ns1.example", "A", "192.0.2.51"),
                    dns_record("ns2.example", "A", "192.0.2.52"),
                ],
            ),
            ("192.0.2.52", "www.example"): dns_reply(
                authoritative=True,
                answers=[dns_record("www.example", "A", "192.0.2.30")],
            ),
        }

        address, path = self.resolver(mapping).resolve("www.example")

        self.assertEqual(address, "192.0.2.30")
        self.assertEqual(path, [self.ROOT, "192.0.2.51", "192.0.2.52"])

    def test_cname_restarts_at_root(self):
        mapping = {
            (self.ROOT, "www.example"): dns_reply(
                authoritative=True,
                answers=[dns_record("www.example", "CNAME", "edge.example")],
            ),
            (self.ROOT, "edge.example"): dns_reply(
                authoritative=True,
                answers=[dns_record("edge.example", "A", "192.0.2.40")],
            ),
        }

        address, path = self.resolver(mapping).resolve("www.example")

        self.assertEqual(address, "192.0.2.40")
        self.assertEqual(path, [self.ROOT, self.ROOT])

    def test_additional_address_is_not_returned_as_answer(self):
        mapping = {
            (self.ROOT, "www.example"): dns_reply(
                authoritative=True,
                additional=[dns_record("www.example", "A", "192.0.2.99")],
            )
        }

        with self.assertRaises(t1.ResolutionError):
            self.resolver(mapping).resolve("www.example")

    def test_cname_cycle_is_rejected(self):
        mapping = {
            (self.ROOT, "a.example"): dns_reply(
                authoritative=True,
                answers=[dns_record("a.example", "CNAME", "b.example")],
            ),
            (self.ROOT, "b.example"): dns_reply(
                authoritative=True,
                answers=[dns_record("b.example", "CNAME", "a.example")],
            ),
        }

        with self.assertRaisesRegex(t1.ResolutionError, "loop"):
            self.resolver(mapping).resolve("a.example")

    def test_query_budget_caps_malformed_walk(self):
        mapping = {
            (self.ROOT, "www.example"): dns_reply(
                authority=[dns_record("example", "NS", "ns1.example")],
                additional=[dns_record("ns1.example", "A", "192.0.2.53")],
            )
        }

        with self.assertRaisesRegex(t1.ResolutionError, "depth"):
            self.resolver(mapping, max_depth=1).resolve("www.example")


if __name__ == "__main__":
    unittest.main()
