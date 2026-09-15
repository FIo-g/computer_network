import contextlib
import io
import unittest

import bench
import task3_cache as t3


class TestTask3Cache(unittest.TestCase):
    class Upstream:
        def __init__(self, answers):
            self.answers = answers
            self.calls = []

        def __call__(self, name):
            self.calls.append(name)
            return self.answers[name]

    def test_first_lookup_fetches_and_second_fresh_lookup_hits(self):
        upstream = self.Upstream({"a.example": ("192.0.2.1", 20)})
        cache = t3.YourCache(upstream)

        self.assertEqual(cache.lookup("a.example", 10.0), "192.0.2.1")
        self.assertEqual(cache.lookup("a.example", 29.999), "192.0.2.1")
        self.assertEqual(upstream.calls, ["a.example"])

    def test_exact_expiry_refetches_and_replaces_entry(self):
        answers = [("192.0.2.1", 20), ("192.0.2.2", 30)]

        def upstream(name):
            return answers.pop(0)

        cache = t3.YourCache(upstream)

        self.assertEqual(cache.lookup("a.example", 10.0), "192.0.2.1")
        self.assertEqual(cache.lookup("a.example", 30.0), "192.0.2.2")
        self.assertEqual(cache.lookup("a.example", 59.999), "192.0.2.2")

    def test_nonpositive_ttl_is_never_reused(self):
        upstream = self.Upstream(
            {
                "zero.example": ("192.0.2.3", 0),
                "negative.example": ("192.0.2.4", -5),
            }
        )
        cache = t3.YourCache(upstream)

        cache.lookup("zero.example", 1.0)
        cache.lookup("zero.example", 1.0)
        cache.lookup("negative.example", 1.0)
        cache.lookup("negative.example", 1.0)

        self.assertEqual(
            upstream.calls,
            ["zero.example", "zero.example", "negative.example", "negative.example"],
        )
        self.assertEqual(cache.stats(), {"entries": 0})

    def test_distinct_names_and_stats_are_independent(self):
        upstream = self.Upstream(
            {
                "a.example": ("192.0.2.1", 60),
                "b.example": ("192.0.2.2", 60),
            }
        )
        cache = t3.YourCache(upstream)

        cache.lookup("a.example", 0.0)
        cache.lookup("b.example", 0.0)

        self.assertEqual(cache.stats(), {"entries": 2})
        self.assertEqual(upstream.calls, ["a.example", "b.example"])

    def test_supplied_workload_reaches_the_correct_floor(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = bench.run(t3.YourCache, "yours")

        self.assertEqual(result, {"upstream": 275, "hits": 725, "stale": 0})
