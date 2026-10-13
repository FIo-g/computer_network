#!/usr/bin/env python3
"""Week 5 · Task 3 — Make longest-prefix match fast.

Textbook §4.3.3.

`LinearTable` is correct and it is what you probably wrote in Task 1: keep the
prefixes in a list, check every one, remember the longest that matched. On six
entries that is fine. A real router holds close to a million, and it has to
answer while the packet is still in the buffer.

Beat it:

    python3 bench.py
    python3 bench.py --yours

Correctness first: `bench.py` checks every one of your answers against the
linear table. A fast router that forwards to the wrong next hop is not a
router, it is an outage.
"""


# Marks an empty slot. Distinct from None, because None is a legal next hop.
_MISS = object()


class LinearTable:
    """Correct, and slow in the obvious way."""

    def __init__(self):
        self.entries = []                     # (prefix_len, network, next_hop)

    def add(self, network, prefix_len, next_hop):
        self.entries.append((prefix_len, network, next_hop))

    def lookup(self, address):
        best = None
        for plen, net, hop in self.entries:
            mask = (0xFFFFFFFF << (32 - plen)) & 0xFFFFFFFF
            if address & mask == net and (best is None or plen > best[0]):
                best = (plen, hop)
        return best[1] if best else None


class YourTable:
    """Controlled prefix expansion with strides 16 / 8 / 8 (the DIR-24-8 idea).

    Every prefix is copied ("expanded") into fixed-size slots when it is added,
    so a lookup never searches - it indexes:

      _l16   list of 65,536 slots, index = address >> 16.
             Holds the best prefix of length 0-16 covering that /16 block.
      _d24   dict, key = address >> 8 (a /24 block).
             Holds the best prefix of length 17-24 covering that /24 block.
             A key exists only where some /17-/24 covers it, and any such
             answer is longer than anything in _l16, so a hit here wins.
      _deep  dict, key = address >> 8 -> list of 256 slots, index = address & 255.
             Holds the best prefix of length 25-32; _MISS where none covers.
             Only /24 blocks that contain a /25-/32 get a list.

    Each structure has a twin (_l16_len, _d24_len, _deep_len) storing the prefix
    length that owns each slot, so add() only overwrites a slot with a strictly
    longer prefix. That makes the result independent of add order.

    Decisions (so that every answer equals LinearTable):
      * the same (network, prefix_len) added twice: the FIRST next hop stays.
        LinearTable keeps both but its `plen > best` test is strict, so the
        earlier entry wins; the strict `<` below reproduces that.
      * network with host bits set: stored nowhere. LinearTable keeps it, but
        `address & mask == net` can never be true for it, so it never answers.
      * prefix_len not an int in 0-32, or network not an int in 0..2**32-1:
        ValueError at add().
      * next_hop may be any object, including None (returned as None, exactly
        like LinearTable).
      * lookup() does no validation: address must be an int in 0..2**32-1.

    Cost: lookup is at most three probes (deep, /24, /16) whatever the table
    size. Memory and add() time pay for it: a /0 fills 65,536 slots, a /17
    writes 128 keys, a /25 allocates two 256-slot lists.
    """

    def __init__(self):
        self._l16 = [None] * 65536        # next hop per /16 block (lengths 0-16)
        self._l16_len = [-1] * 65536      # owning prefix length, -1 = none
        self._d24 = {}                    # /24 block -> next hop (lengths 17-24)
        self._d24_len = {}                # /24 block -> owning prefix length
        self._deep = {}                   # /24 block -> 256 next hops (lengths 25-32)
        self._deep_len = {}               # /24 block -> 256 owning prefix lengths

    def add(self, network, prefix_len, next_hop):
        if not isinstance(prefix_len, int) or not 0 <= prefix_len <= 32:
            raise ValueError(f"prefix length must be an int in 0-32, got {prefix_len!r}")
        if not isinstance(network, int) or not 0 <= network <= 0xFFFFFFFF:
            raise ValueError(f"network must be a 32-bit int, got {network!r}")
        mask = (0xFFFFFFFF << (32 - prefix_len)) & 0xFFFFFFFF
        if network & ~mask & 0xFFFFFFFF:
            return                        # host bits set: LinearTable never matches it
        if prefix_len <= 16:
            hops, lens = self._l16, self._l16_len
            start = network >> 16
            for i in range(start, start + (1 << (16 - prefix_len))):
                if lens[i] < prefix_len:
                    lens[i] = prefix_len
                    hops[i] = next_hop
        elif prefix_len <= 24:
            hops, lens = self._d24, self._d24_len
            start = network >> 8
            for k in range(start, start + (1 << (24 - prefix_len))):
                if lens.get(k, -1) < prefix_len:
                    lens[k] = prefix_len
                    hops[k] = next_hop
        else:
            block = network >> 8
            hops = self._deep.get(block)
            if hops is None:
                hops = self._deep[block] = [_MISS] * 256
                self._deep_len[block] = [-1] * 256
            lens = self._deep_len[block]
            start = network & 255
            for i in range(start, start + (1 << (32 - prefix_len))):
                if lens[i] < prefix_len:
                    lens[i] = prefix_len
                    hops[i] = next_hop

    def lookup(self, address):
        if self._deep:                                   # any /25-/32 at all?
            slots = self._deep.get(address >> 8)
            if slots is not None:
                hop = slots[address & 255]
                if hop is not _MISS:
                    return hop
        hop = self._d24.get(address >> 8, _MISS)
        if hop is not _MISS:
            return hop
        return self._l16[address >> 16]
