#!/usr/bin/env python3
"""Week 5 · Task 1 — Subnets and longest-prefix match.

Textbook §4.3.2 (IPv4 addressing, CIDR) and §4.3.3 (forwarding).

Two things a router does with every packet: work out which prefixes the
destination falls inside, and pick the longest one. The second is the whole
of "longest prefix match", and it is the reason the internet's routing table
can hold a million entries and still be answerable.

You build both, from integers up. No `ipaddress` module - that library is
exactly the thing you are supposed to understand this week.

    python3 task1_forward.py --verify
"""
import argparse


_ALL_ONES = 0xFFFFFFFF


def _mask(prefix_len):
    """/24 -> 0xFFFFFF00, /0 -> 0. Shift left, then cut back to 32 bits."""
    return (_ALL_ONES << (32 - prefix_len)) & _ALL_ONES


def _ip_to_int(text):
    """'163.152.6.0' -> 0xA3980600. Exactly four decimal octets, each 0-255.

    A leading zero ('010') is rejected: C-style parsers read it as octal and
    others as decimal, so it is ambiguous.
    """
    parts = text.split(".")
    if len(parts) != 4:
        raise ValueError(f"not a dotted-quad address: {text!r}")
    value = 0
    for part in parts:
        if not (part.isascii() and part.isdigit()) or (len(part) > 1 and part[0] == "0"):
            raise ValueError(f"bad octet {part!r} in {text!r}")
        octet = int(part)
        if octet > 255:
            raise ValueError(f"octet {octet} > 255 in {text!r}")
        value = (value << 8) | octet
    return value


def _int_to_ip(value):
    """0xA3980600 -> '163.152.6.0'."""
    return f"{(value >> 24) & 255}.{(value >> 16) & 255}.{(value >> 8) & 255}.{value & 255}"


def parse_cidr(cidr):
    """'163.152.6.0/24' -> (network as int, prefix length).

    Raises ValueError when:
      * the text is not exactly '<a.b.c.d>/<n>' (one slash, decimal digits only)
      * the prefix length is outside 0-32                            (R1)
      * any host bit is set: '163.152.6.5/24' is a host, not a network (R2)
    """
    if not isinstance(cidr, str) or cidr.count("/") != 1:
        raise ValueError(f"not a CIDR block: {cidr!r}")
    addr_text, len_text = cidr.strip().split("/")
    if not (len_text.isascii() and len_text.isdigit()):
        raise ValueError(f"bad prefix length in {cidr!r}")
    prefix_len = int(len_text)
    if not 0 <= prefix_len <= 32:
        raise ValueError(f"prefix length {prefix_len} is outside 0-32 in {cidr!r}")
    network = _ip_to_int(addr_text)
    if network & ~_mask(prefix_len) & _ALL_ONES:
        raise ValueError(f"{cidr} has host bits set - it is a host, not a network")
    return network, prefix_len


def network_range(cidr):
    """'163.152.6.0/24' -> (first usable, last usable, broadcast) as strings.

    The edges, decided here (see observation.md):
      /0-/30  network + 1, broadcast - 1, broadcast   (the textbook rule)
      /31     (network, network + 1, None)  RFC 3021: a point-to-point link,
              both addresses are hosts and there is no broadcast address
      /32     (address, address, None)      a single host route
    The cidr must be a network (host bits clear) - it goes through parse_cidr.
    """
    network, prefix_len = parse_cidr(cidr)
    broadcast = network | (~_mask(prefix_len) & _ALL_ONES)
    if prefix_len == 32:
        return _int_to_ip(network), _int_to_ip(network), None
    if prefix_len == 31:
        return _int_to_ip(network), _int_to_ip(broadcast), None
    return _int_to_ip(network + 1), _int_to_ip(broadcast - 1), _int_to_ip(broadcast)


class ForwardingTable:
    """Longest-prefix-match forwarding.

    add(cidr, next_hop)  ·  lookup(address) -> next_hop or None

    Entries are grouped by prefix length ({length: {network: next_hop}}), and
    lookup asks the lengths present from longest to shortest, stopping at the
    first hit. 0.0.0.0/0 has length 0, so it is asked last and loses to any
    other match (R5).

    Same prefix added twice (same network, same length):
      * same next hop       -> no-op
      * different next hop  -> ValueError. Longest match cannot choose between
        two entries of equal length, so the table is malformed; refusing at
        add() is better than silently forwarding by insertion order.
    Two different networks of the same length never overlap, so they are fine.

    lookup takes a dotted-quad string or a 32-bit int; no match -> None.
    """

    def __init__(self):
        self._by_len = {}     # prefix length -> {network int: next hop}
        self._lens = []       # prefix lengths present, longest first

    def add(self, cidr, next_hop):
        network, prefix_len = parse_cidr(cidr)
        group = self._by_len.get(prefix_len)
        if group is None:
            group = self._by_len[prefix_len] = {}
            self._lens = sorted(self._by_len, reverse=True)
        if network in group:
            if group[network] == next_hop:
                return
            raise ValueError(f"{cidr} is already in the table -> {group[network]!r}; "
                             f"refusing a second next hop {next_hop!r}")
        group[network] = next_hop

    def lookup(self, address):
        if isinstance(address, str):
            address = _ip_to_int(address)
        elif not isinstance(address, int) or not 0 <= address <= _ALL_ONES:
            raise ValueError(f"not an IPv4 address: {address!r}")
        for prefix_len in self._lens:
            group = self._by_len[prefix_len]
            key = address & _mask(prefix_len)
            if key in group:
                return group[key]
        return None


# ------------------------------------------------------------------- harness
RANGE_CASES = [
    ("192.168.0.0/24",  "192.168.0.1",   "192.168.0.254",  "192.168.0.255"),
    ("10.0.0.0/8",      "10.0.0.1",      "10.255.255.254", "10.255.255.255"),
    ("172.16.32.0/20",  "172.16.32.1",   "172.16.47.254",  "172.16.47.255"),
    ("203.0.113.64/26", "203.0.113.65",  "203.0.113.126",  "203.0.113.127"),
]

TABLE = [
    ("0.0.0.0/0",       "default-gw"),
    ("10.0.0.0/8",      "campus"),
    ("10.20.0.0/16",    "eng-building"),
    ("10.20.30.0/24",   "lab-floor"),
    ("10.20.30.64/26",  "lab-rack-2"),
    ("192.168.1.0/24",  "home"),
]

LOOKUP_CASES = [
    ("10.20.30.70",   "lab-rack-2"),     # inside all four 10.x entries
    ("10.20.30.10",   "lab-floor"),
    ("10.20.99.1",    "eng-building"),
    ("10.99.0.1",     "campus"),
    ("8.8.8.8",       "default-gw"),
    ("192.168.1.77",  "home"),
]


def verify():
    fails = 0
    for cidr, first, last, bcast in RANGE_CASES:
        try:
            got = network_range(cidr)
        except NotImplementedError:
            print("  network_range is still a stub"); return 1
        except Exception as e:
            print(f"  FAIL  {cidr:<18} raised {e!r}"); fails += 1; continue
        ok = tuple(got) == (first, last, bcast)
        print(f"  {'ok  ' if ok else 'FAIL'}  {cidr:<18} {got}")
        fails += not ok

    t = ForwardingTable()
    try:
        for cidr, hop in TABLE:
            t.add(cidr, hop)
    except NotImplementedError:
        print("  ForwardingTable is still a stub"); return 1

    for addr, expect in LOOKUP_CASES:
        got = t.lookup(addr)
        ok = got == expect
        print(f"  {'ok  ' if ok else 'FAIL'}  {addr:<16} -> {got}  (want {expect})")
        fails += not ok

    print(f"\n  {len(RANGE_CASES) + len(LOOKUP_CASES) - fails}"
          f"/{len(RANGE_CASES) + len(LOOKUP_CASES)} ok")
    return 1 if fails else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()
    raise SystemExit(verify() if a.verify else p.print_help())
