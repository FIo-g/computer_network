# usage: python3 out/differential_test.py   (run from w05-ip-nat/)
# Random differential test: YourTable vs LinearTable on 400 random tables (seeds 0-399).
import random, sys
sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), ".."))
from task3_lpm import LinearTable, YourTable
M = 0xFFFFFFFF
def mask(p): return (M << (32 - p)) & M
bad = checks = 0
for trial in range(400):
    rng = random.Random(trial)
    routes = []
    for i in range(rng.randint(1, 80)):
        r = rng.random()
        if routes and r < 0.35:
            bn, bp, _ = rng.choice(routes)
            p = rng.randint(0, 32)
            n = (bn | (rng.getrandbits(32 - bp) if bp < 32 else 0)) & mask(p)
        elif routes and r < 0.45:
            n, p, _ = rng.choice(routes)
        else:
            p = rng.choice([0, 1, 7, 8, 12, 15, 16, 17, 20, 23, 24, 25, 28, 30, 31, 32, rng.randint(0, 32)])
            n = rng.getrandbits(32) & mask(p)
        hop = None if rng.random() < 0.03 else f"h{trial}-{i}"
        if p < 32 and rng.random() < 0.04:
            n |= 1
        routes.append((n, p, hop))
    rng.shuffle(routes)
    lin, mine = LinearTable(), YourTable()
    half = len(routes) // 2
    for stage in (routes[:half], routes[half:]):
        for n, p, h in stage:
            lin.add(n, p, h); mine.add(n, p, h)
        qs = {0, M}
        for n, p, _ in routes:
            b = n | (~mask(p) & M)
            qs.update({n, b, (n - 1) & M, (b + 1) & M, n | (rng.getrandbits(32 - p) if p < 32 else 0)})
        qs.update(rng.getrandbits(32) for _ in range(50))
        for q in sorted(qs):
            checks += 1
            if lin.lookup(q) != mine.lookup(q):
                bad += 1
                if bad <= 5: print("MISMATCH trial", trial, hex(q), lin.lookup(q), mine.lookup(q))
print(f"differential: {checks} lookups, {bad} mismatches")
for args in ((0, -1, "x"), (0, 33, "x"), (-1, 8, "x"), (1 << 32, 8, "x")):
    try:
        YourTable().add(*args); print("accepted (WRONG):", args); bad += 1
    except ValueError:
        print("ValueError ok:", args)
sys.exit(1 if bad else 0)
