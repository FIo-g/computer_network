#!/usr/bin/env python3
"""Week 3 · Task 1 — 직접 반복적 리졸버를 만드세요.

교재 §2.4.2 - §2.4.3.

`dig +trace`는 루트 -> TLD -> 권한 서버 과정을 대신 탐색해 줍니다. 이 과제에서는
그 탐색을 직접 수행합니다: 루트 서버에서 시작해 반환된 위임을 읽고,
다음 서버에 질의하고, 권한 있는 응답을 받을 때까지 계속 진행합니다.

전송을 위해서는 `dig`를 직접 호출해도 되고 DNS 라이브러리를 사용해도 됩니다
(컨테이너에 `dnspython`이 있습니다). 어느 쪽이든 괜찮습니다. 중요한 것은 도구가 아니라
*여러분*이 위임을 직접 따라가는 것입니다.

    python3 task1_resolve.py www.korea.ac.kr
    python3 task1_resolve.py --verify        # dig와 비교해 스스로 확인

통과 조건
--------------
`--verify`는 5개의 이름을 여러분의 리졸버와 `dig`로 각각 해석하며,
주소가 일치해야 합니다. CDN 뒤의 이름은 정당하게 매번 다른 주소를 반환할 수 있으며,
하네스는 그런 경우 주소가 아니라 도달한 *권한 네임서버 집합*을 비교합니다.
"""
import argparse, subprocess, sys

# 루트 서버. 모든 것이 여기서 시작합니다. 이보다 이전 단계는 없습니다.
ROOT_SERVERS = [
    "198.41.0.4",       # a.root-servers.net
    "199.9.14.201",     # b.root-servers.net
    "192.33.4.12",      # c.root-servers.net
]

# (이름, 종류). "stable" 이름은 dig와 정확히 일치해야 합니다. "cdn" 이름은
# 여러 복제 서버에서 서비스되므로 dig가 조금 앞서 받은 주소와 정당하게 다를 수 있습니다.
# 그런 이름은 답변에 도달하기만 하면 됩니다.
VERIFY_NAMES = [
    ("www.korea.ac.kr", "stable"),
    ("dns.google", "stable"),
    ("en.wikipedia.org", "stable"),
    ("www.stanford.edu", "stable"),
    ("www.microsoft.com", "cdn"),
]


def _norm(name):
    return name.strip().lower().rstrip(".") + "."


def _run_dig(server, qname, timeout=5):
    """Transport only: ask one server with +norecurse. Returns stdout or None."""
    try:
        r = subprocess.run(
            ["dig", f"@{server}", qname, "A", "+norecurse",
             "+time=2", "+tries=1"],
            capture_output=True, text=True, timeout=timeout)
        return r.stdout
    except Exception:
        return None


def _parse_dig(text):
    """Split dig output into (status, answer, authority, additional).

    Each record list holds (owner, type, rdata_first_token_full).
    Full rdata string kept for CNAME/NS targets.
    """
    status = None
    answer, authority, additional = [], [], []
    current = None
    for line in text.splitlines():
        s = line.strip()
        if "status:" in line and "HEADER" in line:
            # e.g. ";; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 123"
            try:
                after = line.split("status:")[1]
                status = after.split(",")[0].strip()
            except Exception:
                pass
            continue
        if s.startswith(";; ANSWER SECTION:"):
            current = "answer"
            continue
        if s.startswith(";; AUTHORITY SECTION:"):
            current = "authority"
            continue
        if s.startswith(";; ADDITIONAL SECTION:"):
            current = "additional"
            continue
        if not s or s.startswith(";"):
            continue
        parts = s.split()
        if len(parts) < 5:
            continue
        owner, rtype = parts[0], parts[3].upper()
        rdata = " ".join(parts[4:])
        if rtype not in ("A", "NS", "CNAME", "SOA"):
            # Only track what the walk needs; ignore AAAA etc.
            if current == "additional" and rtype != "A":
                continue
            if current in ("answer", "authority") and rtype not in ("A", "NS", "CNAME"):
                continue
        entry = (owner, rtype, rdata)
        if current == "answer":
            answer.append(entry)
        elif current == "authority":
            authority.append(entry)
        elif current == "additional":
            additional.append(entry)
    return status, answer, authority, additional


class Resolver:
    """여러분이 만들 반복적 리졸버입니다.

    핵심은 서버에게 재귀 질의를 절대 시키지 않는 것입니다.
    하나의 서버에 물으면 "내 것이 아니니 저기로 물어봐"라고 답하고, 여러분은 그곳으로 이동합니다.

    권장 구조 - 직접 설계해도 됩니다:

        resolve(name) -> (address, path)
            address : 최종적으로 얻은 A 레코드, 문자열
            path    : 작업 과정을 보여주기 위해 순서대로 질의한 서버 목록

    대략 이 순서대로 마주하게 됩니다:

    1.  위임은 NS *이름*을 주며, 글루 A 레코드가 함께 올 때도 있고 없을 때도 있습니다.
        글루가 없으면 그 네임서버의 이름부터 먼저 해석해야 합니다 - 또 다른 탐색입니다.
        이 경우 어떻게 처리할지 정하세요.
    2.  서버가 응답하지 않을 수 있습니다. 포기하지 말고 다음 서버를 시도하세요.
    3.  CNAME. 돌려받은 답이 질의한 이름과 다른 이름일 수 있으며,
        그 이름으로 처음부터 다시 시작해야 합니다.
    4.  루프. 깊이에 상한을 두어 무한 루프에 빠지지 않게 하세요.

    dig를 직접 호출한다면 `+norecurse` 플래그를 사용하세요. 이렇게 하면
    질의받은 서버가 대신 작업하지 않고 위임으로 응답합니다:

        dig @198.41.0.4 www.korea.ac.kr +norecurse
    """

    MAX_HOPS = 20        # R6: one walk may not delegate forever
    MAX_CNAME = 10       # R5/R6: CNAME restarts are bounded
    MAX_DEPTH = 6        # R3/R6: glue-less NS recursion is bounded

    def resolve(self, name):
        path = []
        addr = self._lookup(name, path, depth=0)
        return addr, path

    def _lookup(self, qname, path, depth):
        if depth > self.MAX_DEPTH:
            raise RuntimeError(f"max recursion depth for {qname}")
        cur_dot = _norm(qname)
        for _restart in range(self.MAX_CNAME + 1):
            addr = self._walk(cur_dot, path, depth)
            # _walk returns either "A:<ip>" or "CNAME:<target>"
            if addr.startswith("A:"):
                return addr[2:]
            # CNAME: restart the whole walk from a root server (R5)
            cur_dot = _norm(addr[len("CNAME:"):])
            continue
        raise RuntimeError(f"CNAME loop for {qname}")

    def _walk(self, cur_dot, path, depth):
        """Iterative walk for one name. Returns 'A:ip' or 'CNAME:target'."""
        next_servers = list(ROOT_SERVERS)  # R2: always start at a root
        for _hop in range(self.MAX_HOPS):  # R6
            last_error = "no server answered"
            progressed = False
            for srv in list(next_servers):
                if srv.startswith("ns:"):
                    # R3: a glue-less NS name, resolved only when we reach it.
                    # Another walk from the root - this is where the
                    # recursion in "recursive resolver" comes from.
                    try:
                        srv = self._lookup(srv[3:], path, depth + 1)
                    except Exception as e:
                        last_error = f"glue-less {srv[3:]}: {e}"
                        continue  # R4: try the next one
                path.append(srv)  # R1: record every server asked, in order
                text = _run_dig(srv, cur_dot.rstrip("."))
                if text is None:
                    last_error = f"{srv} timeout"
                    continue  # R4: try the next one
                status, answer, authority, additional = _parse_dig(text)

                # Build local maps from the ANSWER section.
                cname_map = {}
                a_map = {}
                for owner, rtype, rdata in answer:
                    if rtype == "CNAME" and _norm(owner) == cur_dot:
                        cname_map[_norm(owner)] = _norm(rdata.split()[0])
                    elif rtype == "A":
                        a_map.setdefault(_norm(owner), []).append(
                            rdata.split()[0])

                # R5: follow a CNAME chain that is visible in this packet.
                if cur_dot in cname_map:
                    seen = set()
                    target = cname_map[cur_dot]
                    while target in cname_map and target not in seen:
                        seen.add(target)
                        target = cname_map[target]
                    if target in a_map:
                        return "A:" + a_map[target][0]
                    return "CNAME:" + target

                # Direct A answer for the queried name.
                if cur_dot in a_map:
                    return "A:" + a_map[cur_dot][0]

                # Delegation? authority NS names (R3/R4).
                ns_names = []
                for owner, rtype, rdata in authority:
                    if rtype == "NS":
                        ns_names.append(_norm(rdata.split()[0]))
                if status == "NOERROR" and ns_names:
                    glue = {}
                    for owner, rtype, rdata in additional:
                        if rtype == "A":
                            glue.setdefault(_norm(owner), rdata.split()[0])
                    # Glued servers first: they cost nothing extra. Glue-less
                    # NS names queue behind them and are resolved one at a
                    # time, only if every server before them failed (R3/R4).
                    candidates = [glue[ns] for ns in ns_names if ns in glue]
                    candidates += ["ns:" + ns.rstrip(".")
                                   for ns in ns_names if ns not in glue]
                    if candidates:
                        next_servers = candidates
                        progressed = True
                        break  # next hop: ask the delegated servers
                    last_error = "delegation without usable NS"
                    continue  # R4: this server's delegation unusable, try next

                # Anything else (SERVFAIL/NXDOMAIN/empty): try next server.
                last_error = f"{srv} status={status} ans={len(answer)} auth={len(ns_names)}"
                continue
            if progressed:
                continue
            raise RuntimeError(f"resolution failed for {cur_dot}: {last_error}")
        raise RuntimeError(f"max hops exceeded for {cur_dot}")


# ------------------------------------------------------------------- 하네스
def dig_answer(name):
    """비교를 위해 시스템 리졸버의 답변을 가져옵니다."""
    out = subprocess.run(["dig", "+short", name, "A"],
                         capture_output=True, text=True).stdout
    return [l for l in out.split() if l and l[0].isdigit()]


def verify():
    r, failures = Resolver(), 0
    for name, kind in VERIFY_NAMES:
        try:
            addr, path = r.resolve(name)
        except NotImplementedError:
            print("Nothing implemented yet - write Resolver.resolve first.")
            return 1
        except Exception as e:
            print(f"  FAIL  {name:<22} your resolver raised {e!r}")
            failures += 1
            continue
        expected = dig_answer(name)
        if addr in expected:
            note = ""
        elif kind == "cdn":
            note = "  <- differs, but this name is CDN-hosted. Explain it."
        else:
            note = "  <- should have matched"
            failures += 1
        print(f"  {'FAIL' if note.endswith('matched') else 'ok  '}  {name:<22} "
              f"you={addr:<16} dig={','.join(expected) or '-'}   "
              f"hops={len(path)}{note}")
    print(f"\n  {len(VERIFY_NAMES) - failures}/{len(VERIFY_NAMES)} ok")
    return 1 if failures else 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("name", nargs="?", default="www.korea.ac.kr")
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()

    if a.verify:
        sys.exit(verify())

    addr, path = Resolver().resolve(a.name)
    for i, server in enumerate(path, 1):
        print(f"  {i}. asked {server}")
    print(f"\n  {a.name} -> {addr}")


if __name__ == "__main__":
    main()
