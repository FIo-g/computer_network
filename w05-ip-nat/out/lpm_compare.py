# usage: python3 out/lpm_compare.py .   (run from w05-ip-nat/; prints the report that is saved as out/lpm-compare.txt)
import sys, time, tracemalloc, platform
sys.path.insert(0, sys.argv[1])
import bench
from task3_lpm import LinearTable, YourTable
_MISS = object()

class BitTrie:                       # 1 bit per step - the textbook / hardware walk
    def __init__(self): self.root = [None, None, None, False]
    def add(self, net, plen, hop):
        node = self.root
        for i in range(plen):
            b = (net >> (31 - i)) & 1
            if node[b] is None: node[b] = [None, None, None, False]
            node = node[b]
        if not node[3]: node[2], node[3] = hop, True
    def lookup(self, a):
        node, best, i = self.root, None, 31
        while node is not None:
            if node[3]: best = node[2]
            if i < 0: break
            node = node[(a >> i) & 1]; i -= 1
        return best
    def steps(self, a):
        node, n, i = self.root, 0, 31
        while node is not None and i >= 0:
            node = node[(a >> i) & 1]; i -= 1; n += 1
        return n

class ByLength:                      # one dict per prefix length, longest first
    def __init__(self): self.d, self.g = {}, []
    def add(self, net, plen, hop):
        if plen not in self.d:
            self.d[plen] = {}
            self.g = [((0xFFFFFFFF << (32 - p)) & 0xFFFFFFFF, self.d[p]) for p in sorted(self.d, reverse=True)]
        self.d[plen].setdefault(net, hop)
    def lookup(self, a):
        for m, d in self.g:
            h = d.get(a & m, _MISS)
            if h is not _MISS: return h
        return None
    def steps(self, a):
        for k, (m, d) in enumerate(self.g, 1):
            if (a & m) in d: return k
        return len(self.g)

print(f"python {platform.python_version()} · {platform.machine()}")
routes, queries = bench.build()
print(f"bench table {len(routes):,} prefixes, {len(queries):,} queries (seed {bench.SEED})\n")

print("== 1. same table, four structures (best of 5 timings; LinearTable 1 timing)")
ref = None
for cls in (LinearTable, BitTrie, ByLength, YourTable):
    tracemalloc.start()
    t = cls()
    for n, p, h in routes: t.add(n, p, h)
    mem = tracemalloc.get_traced_memory()[0]; tracemalloc.stop()
    best = None
    for _ in range(1 if cls is LinearTable else 5):
        t0 = time.perf_counter(); ans = [t.lookup(a) for a in queries]; dt = time.perf_counter() - t0
        best = dt if best is None else min(best, dt)
    ref = ans if ref is None else ref
    wrong = sum(x != y for x, y in zip(ans, ref))
    if hasattr(t, "steps"):
        s = [t.steps(a) for a in queries]; extra = f"steps avg {sum(s)/len(s):5.2f} max {max(s)}"
    elif cls is LinearTable:
        extra = f"steps {len(routes)} (every entry)"
    else:
        s = [(1 if t._deep else 0) + 1 + (0 if (a >> 8) in t._d24 else 1) for a in queries]
        extra = f"steps avg {sum(s)/len(s):5.2f} max {max(s)}"
    print(f"  {cls.__name__:12s} {best/len(queries)*1e9:9.0f} ns/lookup   memory {mem/1e6:6.2f} MB   wrong {wrong}   {extra}")

t = YourTable()
for n, p, h in routes: t.add(n, p, h)
print(f"\n  YourTable parts: _l16 {len(t._l16):,} slots, _d24 {len(t._d24):,} keys, _deep {len(t._deep):,} blocks")
print(f"  route lengths in table: " + ", ".join(f"/{p} x{c}" for p, c in sorted(
    {p: sum(1 for _, q, _ in routes if q == p) for _, p, _ in routes}.items(), reverse=True)))

print("\n== 2. lookup cost vs table size N (bench generator, seed 1)")
for N in (1000, 5000, 20000, 100000):
    bench.ROUTES = N
    r, q = bench.build(seed=1)
    t = YourTable()
    for n, p, h in r: t.add(n, p, h)
    best = min((lambda t0: ([t.lookup(a) for a in q], time.perf_counter() - t0)[1])(time.perf_counter()) for _ in range(5))
    line = f"  N={N:>7,}  YourTable {best/len(q)*1e9:6.0f} ns/lookup"
    if N <= 20000:
        lt = LinearTable()
        for n, p, h in r: lt.add(n, p, h)
        sub = q[:1000]
        t0 = time.perf_counter(); [lt.lookup(a) for a in sub]; dt = time.perf_counter() - t0
        line += f"   LinearTable {dt/len(sub)*1e6:8.1f} us/lookup"
    print(line)
