#!/usr/bin/env python3
"""Week 3 · Task 2 — DNS가 정말로 트래픽을 유도하는지 측정하세요.

교재 §2.4.3 (레코드)와 §2.5 (CDN).

수업에서는 두 가지를 주장합니다:

    (a) 대부분의 대형 사이트는 CNAME 체인을 거쳐 CDN으로 서비스된다
    (b) DNS는 각 사용자를 *가까운* 복제 서버로 유도한다

둘 다 여러분의 노트북에서 검증할 수 있으며, 하나는 슬라이드에서 보이는 것보다 증명하기 어렵습니다.
여러분이 할 일은 근거 자료와 수치를 만드는 것입니다.

    python3 task2_steering.py --collect        # 원시 데이터 수집
    python3 task2_steering.py --report         # 분석 결과 작성

만들어야 할 것
----------------------
1.  SITES에 있는 각 호스트 이름에 대해 CNAME 체인을 끝까지 따라가며
    모든 홉을 기록하세요. `--collect`는 원시 데이터를 out/chains.json에 남겨야 합니다.

2.  각 사이트가 **제3자**에 의해 서비스되는지 판단하세요.
    이 부분이 어렵고, 정답인 규칙은 하나만 있지 않습니다:

      - `www.microsoft.com`은 `akamaiedge.net`에서 끝남     - 명확히 제3자
      - `www.netflix.com`은 `netflix.com` 내부에서 끝남      - 자체 CDN, 제3자 아님
      - 어떤 사이트는 CNAME이 전혀 없는데도 CDN 뒤에 있음 (애니캐스트)
      - `foo.cloudfront.net`과 `foo.s3.amazonaws.com`은 둘 다 Amazon이지만,
        같은 서비스는 아님

    사용한 규칙을 적고 **observation.md에서 그 이유를 설명**하세요.
    마지막 두 레이블만 비교하는 규칙은 아래 사이트 중 적어도 하나에서는 틀립니다.
    어느 사이트인지 찾고, 그렇게 말하세요.

3.  같은 이름에 대해 **서로 다른 두 리졸버**에 질의하고,
    반환된 주소를 비교하세요. DNS가 정말 위치에 따라 트래픽을 유도한다면, CDN이 호스팅하는
    이름은 서로 다른 곳에 있는 리졸버에 다르게 응답해야 합니다.

        아래 RESOLVERS에는 시스템 리졸버와 두 개의 공용 리졸버가 있습니다.

    보고서에는: CDN이 호스팅하는 사이트 N개 중 서로 다른 리졸버에 서로 다른 주소 집합으로
    응답한 곳이 몇 개인지 적으세요. 주장 (b)는 대부분일 것이라 예측합니다. 확인해 보세요.

통과 조건
--------------
정답은 정해져 있지 않습니다. out/report.md에 다음을 만들면 통과입니다:

  - 표: 사이트 | 체인 길이 | 최종 존 | 제3자 여부 | 여러분 규칙의 판정
  - 스티어링 수치: "서로 다른 리졸버에 다르게 응답한 사이트 X / N개"
  - 분류 규칙이 틀린 사이트가 최소 하나, 그리고 그 이유
"""
import argparse, ipaddress, json, os, re, socket, statistics, struct, subprocess, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
CHAINS = os.path.join(OUT, "chains.json")     # B1/B2/B3 원시 데이터, 사이트별
PROBE = os.path.join(OUT, "probe.json")       # 관측 지점, 존, 주소별 AS 와 RTT
REPORT = os.path.join(OUT, "report.md")
CAPTURE = os.path.join(OUT, "dns.pcapng")     # Part A
RUN_LOG = os.path.join(OUT, "task1_run.txt")  # 캡처하는 동안 돌린 task1 출력

SITES = [
    "www.microsoft.com",     # Akamai, 다단계
    "www.netflix.com",       # 자체 CDN
    "www.adobe.com",
    "www.cnn.com",
    "www.apple.com",
    "www.korea.ac.kr",       # CDN 없음
    "www.stanford.edu",
    "www.bbc.co.uk",
    "www.spotify.com",
    "www.github.com",
    "www.wikipedia.org",
    "www.nytimes.com",
]

RESOLVERS = {
    "system": None,          # 여러분의 resolv.conf에 설정된 리졸버
    "google": "8.8.8.8",
    "quad9":  "9.9.9.9",
}

# 9.9.9.9 가 아예 닿지 않는 망이 있습니다 (이 측정의 LG U+ 회선이 그렇습니다 - ping 도 안 됨).
# 그때는 같은 Quad9 서비스의 보조 주소로 묻고, 그렇게 했다고 probe.json 에 남깁니다.
ALTERNATES = {"9.9.9.9": ["149.112.112.112"]}

# 경로 (B) 의 보강: 두 번째 물리 네트워크가 없을 때 Google 에 EDNS Client Subnet 을 실어
# "이 서브넷의 사용자가 묻는다"고 알리고, CDN 이 그 사용자에게 줄 답을 받아 봅니다.
# 흉내일 뿐입니다 - ECS 를 무시하는 권한 서버에는 아무 효과가 없습니다.
ECS_VIA = "8.8.8.8"
ECS_VANTAGES = {
    "ecs-kr-campus":   "163.152.0.0/24",   # 고려대학교 (AS9452), 서울
    "ecs-us-stanford": "171.64.0.0/24",    # Stanford (AS32), 캘리포니아
}

ROUNDS = 3        # 같은 질의를 반복해 로드밸런싱 회전과 위치 기반 스티어링을 구분합니다
NEAR_MS = 5.0     # 본 복제 서버 중 가장 가까운 것보다 이만큼 이내면 "가깝다"

# eTLD+1 을 구하기 위한 다중 레이블 공용 접미사. Public Suffix List 전체 대신
# 이 측정에 나오는 것과 그 이웃만 둡니다.
MULTI_LABEL_SUFFIXES = {"co.uk", "ac.uk", "org.uk", "gov.uk", "ac.kr", "co.kr", "or.kr",
                        "go.kr", "re.kr", "ne.kr", "com.au", "co.jp", "ac.jp"}

# 남의 콘텐츠를 서비스하는 것이 본업인 회사의 AS. 규칙의 2단계(CNAME 없는 애니캐스트)에 씁니다.
# Amazon, Google, Microsoft 는 일부러 뺐습니다: 그 AS 에서는 "CDN 을 쓴다"와
# "자기 서버를 클라우드에 올렸다"를 구분할 수 없습니다.
CDN_ASNS = {16625: "Akamai", 20940: "Akamai", 21342: "Akamai", 32787: "Akamai",
            35994: "Akamai", 54113: "Fastly", 13335: "Cloudflare", 209242: "Cloudflare",
            15133: "Edgio", 22822: "Edgio", 60068: "CDN77"}

# B4 의 정답표. 규칙이 아니라 사람이 정했습니다. 근거는 최종 주소를 광고하는 AS
# (out/probe.json) 와 그 AS 를 운영하는 조직입니다. 규칙은 이 표를 보지 않습니다.
TRUTH = {
    "www.microsoft.com": (True,  "Akamai 가 서비스 (AS16625)"),
    "www.netflix.com":   (False, "Netflix 자체 AS40027 (상위 /22 는 AS2906)"),
    "www.adobe.com":     (True,  "Akamai. 일부 응답은 LG U+ 망(AS3786) 안의 Akamai 캐시"),
    "www.cnn.com":       (True,  "Fastly (AS54113)"),
    "www.apple.com":     (True,  "Apple 의 aaplimg.com 이 Akamai 로 넘김"),
    "www.korea.ac.kr":   (False, "고려대학교 자체 AS9452"),
    "www.stanford.edu":  (True,  "Netlify, AWS Global Accelerator 애니캐스트(AS16509) 위"),
    "www.bbc.co.uk":     (True,  "Fastly (AS54113)"),
    "www.spotify.com":   (True,  "Fastly (AS54113)"),
    "www.github.com":    (False, "GitHub 자체. 한국에선 모회사 Azure(AS8075), 미국에선 GitHub AS36459"),
    "www.wikipedia.org": (False, "Wikimedia 자체 캐시 데이터센터 (AS14907)"),
    "www.nytimes.com":   (True,  "Fastly (AS54113)"),
}


def dig(name, rtype="A", server=None):
    """저수준 조회 함수입니다. 전송만 담당합니다. 판단은 여러분의 몫입니다."""
    args = ["dig", "+short", name, rtype]
    if server:
        args.insert(1, f"@{server}")
    out = subprocess.run(args, capture_output=True, text=True).stdout
    return [l.strip() for l in out.splitlines() if l.strip()]


# ------------------------------------------------------------------ 조회 도구
def _norm(name):
    return name.strip().lower().rstrip(".") + "."


def _bare(name):
    return name.rstrip(".")


def query(name, rtype="A", server=None, ecs=None):
    """answer 섹션을 [(owner, ttl, type, rdata)] 로. 아무 서버도 답하지 않으면 None."""
    args = ["dig", "+noall", "+answer", "+time=3", "+tries=2", name, rtype]
    if server:
        args.insert(1, f"@{server}")
    if ecs:
        args.append(f"+subnet={ecs}")
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:          # dig 는 응답이 없으면 9 로 끝납니다
        return None
    recs = []
    for line in r.stdout.splitlines():
        p = line.split()
        if len(p) >= 5 and not line.startswith(";"):
            recs.append((_norm(p[0]), int(p[1]), p[3].upper(), " ".join(p[4:])))
    return recs


def follow(site, recs):
    """B1: answer 섹션의 CNAME 을 사이트 이름에서부터 한 홉씩 따라갑니다.
    섹션 안의 순서는 믿지 않습니다. (홉 목록, 마지막 이름, 그 이름의 A 레코드)."""
    cname = {o: (_norm(r), ttl) for o, ttl, t, r in recs if t == "CNAME"}
    hops, cur = [], _norm(site)
    while cur in cname and len(hops) < 16:
        target, ttl = cname[cur]
        hops.append({"name": _bare(cur), "cname": _bare(target), "ttl": ttl})
        cur = target
    addrs = sorted({r for o, _, t, r in recs if t == "A" and o == cur},
                   key=ipaddress.ip_address)
    return hops, _bare(cur), addrs


def zone_of(name):
    """name 이 들어 있는 존의 apex: SOA 를 정확히 그 이름으로 돌려주는 가장 긴 접미사.
    CNAME 이 걸린 이름에 SOA 를 물으면 대상 쪽 SOA 가 오므로, owner 가 같은지 꼭 봅니다."""
    labels = _bare(name).split(".")
    for i in range(len(labels)):
        cand = _norm(".".join(labels[i:]))
        if any(o == cand and t == "SOA" for o, _, t, _ in (query(cand, "SOA") or [])):
            return _bare(cand)
    return ""


def registrable(name):
    """eTLD+1. www.bbc.co.uk -> bbc.co.uk, www.korea.ac.kr -> korea.ac.kr"""
    labels = _bare(name).lower().split(".")
    n = 3 if ".".join(labels[-2:]) in MULTI_LABEL_SUFFIXES else 2
    return ".".join(labels[-n:])


def last_two(name):
    """비교용 순진한 규칙: 마지막 두 레이블."""
    return ".".join(_bare(name).lower().split(".")[-2:])


_as_names = {}


def origin_as(ip):
    """ip 를 광고하는 AS. Team Cymru 의 DNS 인터페이스로 묻습니다 - 이것도 DNS 입니다."""
    rev = ipaddress.ip_address(ip).reverse_pointer.rsplit(".", 2)[0]
    zone = "origin6.asn.cymru.com" if ":" in ip else "origin.asn.cymru.com"
    txt = dig(f"{rev}.{zone}", "TXT")
    if not txt:
        return None
    # 겹치는 프리픽스를 여러 AS 가 광고할 수 있습니다. 라우터처럼 가장 긴 프리픽스를 고릅니다.
    rows = [[x.strip() for x in t.strip('"').split("|")] for t in txt]
    f = max(rows, key=lambda r: int(r[1].split("/")[1]) if "/" in r[1] else 0)
    asn = int(f[0].split()[0])
    if asn not in _as_names:
        t = dig(f"AS{asn}.asn.cymru.com", "TXT")
        _as_names[asn] = t[0].strip('"').split("|")[-1].strip() if t else ""
    return {"asn": asn, "prefix": f[1], "cc": f[2], "as_name": _as_names[asn]}


def tcp_rtt(ip, port=443, tries=3, timeout=2.0):
    """TCP 핸드셰이크 한 번에 걸린 시간(ms)의 최솟값. ICMP 를 막는 CDN 도 443 은 엽니다."""
    best = None
    for _ in range(tries):
        t0 = time.perf_counter()
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                pass
        except OSError:
            continue
        ms = (time.perf_counter() - t0) * 1000
        best = ms if best is None else min(best, ms)
    return round(best, 1) if best is not None else None


def system_resolver():
    try:
        for line in open("/etc/resolv.conf"):
            if line.split()[:1] == ["nameserver"]:
                return line.split()[1]
    except OSError:
        pass
    return None


def pick_server(server):
    """응답하는 주소를 고릅니다. (성공 여부, 사용한 주소, 응답하지 않은 주소들)"""
    failed = []
    for cand in [server] + ALTERNATES.get(server, []):
        if query("example.com", "A", cand) is not None:
            return True, cand, failed
        failed.append(cand)
    return False, None, failed


def resolver_view(server, ecs=None):
    """권한 서버(Akamai whoami)가 본 리졸버의 출구 주소와 ECS. CDN 은 이것으로 사용자 위치를 짐작합니다."""
    seen = {}
    for _, _, t, rdata in query("whoami.ds.akahelp.net", "TXT", server, ecs) or []:
        parts = re.findall(r'"([^"]*)"', rdata)
        if t == "TXT" and len(parts) >= 2:
            seen[parts[0]] = parts[1]
    if ecs:                       # ECS 를 실었다면, Google 이 정말 그것을 넘겼는지
        fwd =subprocess.run(["dig", "+short", f"@{server}", "o-o.myaddr.l.google.com", "TXT",
                              f"+subnet={ecs}"], capture_output=True, text=True).stdout
        m = re.search(r"edns0-client-subnet ([0-9a-f.:/]+)", fwd)
        seen["forwarded_ecs"] = m.group(1) if m else None
    if server:
        pop = subprocess.run(["dig", "+short", "+time=2", "+tries=1", f"@{server}",
                              "id.server", "CH", "TXT"], capture_output=True, text=True).stdout
        if pop.strip() and not pop.startswith(";"):
            seen["id.server"] = pop.strip().strip('"')
    if seen.get("ns"):
        seen["ns_as"] = origin_as(seen["ns"])
    return seen


def _load(path, default):
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    return default


def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def public_ip_now():
    ip = (dig("myip.opendns.com", "A", "resolver1.opendns.com") or [None])[0]
    return ip or resolver_view(ECS_VIA).get("ip")


def measure_rtt(chains, probe, network):
    """지금까지 본 모든 주소에 지금 네트워크에서 TCP/443 RTT 를 잽니다. 다른 네트워크가 받은
    답까지 재 두어야 "내가 받은 답이 정말 더 가까웠나"를 비교할 수 있습니다."""
    ips = sorted({a for e in chains.values() for v in e["vantages"].values() for a in v["addrs"]},
                 key=ipaddress.ip_address)
    for ip in ips:
        info = probe["addrs"].setdefault(ip, {"rtt_ms": {}})
        if "as" not in info:
            info["as"] = origin_as(ip)
    print(f"  RTT: {len(ips)}개 주소에 TCP/443 연결 시간 측정 중 ({network}) ...")
    with ThreadPoolExecutor(max_workers=8) as pool:
        for ip, ms in zip(ips, pool.map(tcp_rtt, ips)):
            probe["addrs"][ip]["rtt_ms"][network] = ms


def remeasure(network):
    """--rtt: 응답은 다시 모으지 않고, 이미 본 주소들의 RTT 만 이 네트워크에서 다시 잽니다."""
    chains, probe = _load(CHAINS, None), _load(PROBE, None)
    if not chains or network not in (probe or {}).get("networks", {}):
        raise SystemExit(f"먼저 --collect --network {network}")
    now_ip, then_ip = public_ip_now(), probe["networks"][network].get("public_ip")
    if now_ip != then_ip:
        raise SystemExit(f"지금 공인 IP {now_ip} 가 {network} 의 {then_ip} 와 다릅니다. "
                         f"{network} 에 다시 붙은 뒤 실행하세요.")
    measure_rtt(chains, probe, network)
    probe["networks"][network]["rtt_remeasured_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    _save(PROBE, probe)


# ------------------------------------------------------------------ 수집
def collect(network="home-wifi"):
    """원시 체인과 리졸버별 응답을 out/chains.json에 모읍니다.

    --network 이름으로 저장하므로, 다른 네트워크에서 다시 돌리면 결과가 덧붙습니다 (B3).
    """
    chains = _load(CHAINS, {})
    probe = _load(PROBE, {"primary": network, "networks": {}, "zones": {}, "addrs": {}})
    now = datetime.now().astimezone().isoformat(timespec="seconds")

    public_ip = (dig("myip.opendns.com", "A", "resolver1.opendns.com") or [None])[0]
    net = {"kind": "physical", "collected_at": now, "public_ip": public_ip,
           "public_as": origin_as(public_ip) if public_ip else None, "resolvers": {}}
    vantages = []
    for label, server in RESOLVERS.items():
        ok, used, failed = pick_server(server)
        net["resolvers"][label] = {"configured": server or system_resolver(),
                                   "used": (used or system_resolver()) if ok else None,
                                   "unreachable": failed,
                                   "seen_by_authority": resolver_view(used) if ok else {}}
        if ok:
            vantages.append((network, label, used, None))
        print(f"  {network}/{label:<7} {'ok ' if ok else 'FAIL'} via {used or 'system'}"
              + (f"  ({', '.join(failed)} 응답 없음)" if failed else ""))
    if not public_ip:                     # OpenDNS 가 막힌 망: Google 경유 whoami 가 본 클라이언트 주소
        public_ip = (net["resolvers"].get("google", {}).get("seen_by_authority") or {}).get("ip")
        net.update(public_ip=public_ip, public_ip_via="whoami.ds.akahelp.net @8.8.8.8",
                   public_as=origin_as(public_ip) if public_ip else None)
    probe["networks"][network] = net

    for name, subnet in ECS_VANTAGES.items():
        probe["networks"][name] = {"kind": "ecs-simulated", "subnet": subnet, "via": ECS_VIA,
                                   "collected_from": network, "collected_at": now,
                                   "seen_by_authority": resolver_view(ECS_VIA, subnet)}
        vantages.append((name, "google", ECS_VIA, subnet))

    for site in SITES:
        entry = chains.setdefault(site, {"vantages": {}})
        for vnet, label, server, ecs in vantages:
            rounds = []
            for _ in range(ROUNDS):
                recs = query(site, "A", server, ecs)
                if recs is None:
                    rounds.append({"error": "no answer"})
                    continue
                hops, final, addrs = follow(site, recs)
                rounds.append({"hops": hops, "final": final, "addrs": addrs})
            good = [r for r in rounds if "addrs" in r]
            entry["vantages"][f"{vnet}/{label}"] = {
                "network": vnet, "resolver": label, "server": server, "ecs": ecs,
                "collected_at": now,
                "chain": [h["name"] for h in good[0]["hops"]] + [good[0]["final"]] if good else [],
                "addrs": sorted({a for r in good for a in r["addrs"]}, key=ipaddress.ip_address),
                "rounds": rounds,
            }
        v = entry["vantages"][f"{network}/system"]
        print(f"  {site:<20} {' -> '.join(v['chain'])}  [{len(v['addrs'])} A]")

    names = {n for e in chains.values() for v in e["vantages"].values() for n in v["chain"]}
    for n in sorted(names - set(probe["zones"])):
        probe["zones"][n] = zone_of(n)

    measure_rtt(chains, probe, network)
    _save(CHAINS, chains)
    _save(PROBE, probe)
    print(f"\n  -> {os.path.relpath(CHAINS, HERE)} ({len(chains)} sites), "
          f"{os.path.relpath(PROBE, HERE)}")


# ------------------------------------------------------------------ B4 규칙
def classify(site, final, addrs, addrinfo):
    """제3자 판정. (판정, 근거) 를 돌려줍니다.

    1. CNAME 체인의 마지막 이름이 사이트와 다른 eTLD+1 에 있으면 제3자.
    2. 체인이 자기 도메인 안에서 끝나거나 CNAME 이 없으면, 최종 주소를 광고하는 AS 를 봅니다.
       CDN 이 본업인 회사의 AS 이면 제3자 (CNAME 없는 애니캐스트).
    3. 둘 다 아니면 자체.
    """
    if registrable(final) != registrable(site):
        return True, f"체인이 `{registrable(final)}` 로 나감"
    for ip in addrs:
        asn = ((addrinfo.get(ip) or {}).get("as") or {}).get("asn")
        if asn in CDN_ASNS:
            return True, f"이름은 안에 있지만 주소가 {CDN_ASNS[asn]} AS{asn}"
    return False, "체인이 자기 도메인 안에서 끝나고 주소도 CDN AS 아님"


# ------------------------------------------------------------------ Part A: 캡처 읽기
# tshark 없이도 읽도록 pcapng/pcap -> IP -> UDP/TCP -> DNS 를 직접 풉니다.
RR_TYPES = {1: "A", 2: "NS", 5: "CNAME", 6: "SOA", 12: "PTR", 15: "MX", 16: "TXT",
            28: "AAAA", 41: "OPT", 43: "DS", 46: "RRSIG", 47: "NSEC", 48: "DNSKEY", 50: "NSEC3"}


def _frames(path):
    """(번호, linktype, 바이트). 번호는 Wireshark 의 No. 열과 같습니다."""
    data = open(path, "rb").read()
    n = 0
    if data[:4] == b"\x0a\x0d\x0d\x0a":                      # pcapng
        off, e, links = 0, "<", []
        while off + 12 <= len(data):
            if data[off:off + 4] == b"\x0a\x0d\x0d\x0a":     # 섹션마다 바이트 순서가 새로 정해짐
                e = "<" if data[off + 8:off + 12] == b"\x4d\x3c\x2b\x1a" else ">"
                links = []
            btype, blen = struct.unpack_from(e + "II", data, off)
            if blen < 12:
                break
            body = data[off + 8:off + blen - 4]
            if btype == 1:                                   # Interface Description
                links.append(struct.unpack_from(e + "H", body, 0)[0])
            elif btype == 6:                                 # Enhanced Packet
                iface, _, _, caplen, _ = struct.unpack_from(e + "IIIII", body, 0)
                n += 1
                yield n, links[iface], body[20:20 + caplen]
            elif btype == 3:                                 # Simple Packet
                n += 1
                yield n, links[0], body[4:4 + struct.unpack_from(e + "I", body, 0)[0]]
            off += blen
    else:                                                    # 고전 pcap
        e = "<" if data[:4] in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1") else ">"
        link, off = struct.unpack_from(e + "I", data, 20)[0] & 0xFFFF, 24
        while off + 16 <= len(data):
            caplen = struct.unpack_from(e + "I", data, off + 8)[0]
            n += 1
            yield n, link, data[off + 16:off + 16 + caplen]
            off += 16 + caplen


def _ip(link, b):
    """링크 계층을 벗겨 (src, dst, proto, L4 바이트)."""
    if link in (149, 258):                   # Apple PKTAP: 헤더 길이, 다음 타입, 안쪽 DLT
        hl, _, inner = struct.unpack_from("<III", b, 0)
        return _ip(inner, b[hl:])
    if link == 1:                            # Ethernet (+VLAN)
        et, off = struct.unpack_from("!H", b, 12)[0], 14
        while et == 0x8100:
            et, off = struct.unpack_from("!H", b, off + 2)[0], off + 4
        b = b[off:] if et in (0x0800, 0x86DD) else b""
    elif link in (0, 108):                   # BSD loopback, utun
        b = b[4:]
    elif link not in (12, 14, 101):          # raw IP
        return None
    if len(b) >= 20 and b[0] >> 4 == 4:
        ihl, total = (b[0] & 15) * 4, struct.unpack_from("!H", b, 2)[0]
        return (socket.inet_ntop(socket.AF_INET, b[12:16]),
                socket.inet_ntop(socket.AF_INET, b[16:20]), b[9], b[ihl:total])
    if len(b) >= 40 and b[0] >> 4 == 6:
        plen = struct.unpack_from("!H", b, 4)[0]
        return (socket.inet_ntop(socket.AF_INET6, b[8:24]),
                socket.inet_ntop(socket.AF_INET6, b[24:40]), b[6], b[40:40 + plen])
    return None


def _dname(msg, off):
    """압축 포인터를 따라가며 이름을 읽습니다. (이름, 포인터 이전의 다음 오프셋)"""
    labels, end, jumps = [], None, 0
    while True:
        n = msg[off]
        if n >= 0xC0:
            end = off + 2 if end is None else end
            off, jumps = ((n & 0x3F) << 8) | msg[off + 1], jumps + 1
            if jumps > 32:
                raise ValueError("pointer loop")
        elif n == 0:
            return ".".join(labels) + ".", (off + 1 if end is None else end)
        else:
            labels.append(msg[off + 1:off + 1 + n].decode("ascii", "replace"))
            off += 1 + n


def _parse_dns(msg):
    tid, flags, qd, an, ns, ar = struct.unpack_from("!6H", msg, 0)
    off, qname, qtype = 12, "", ""
    for _ in range(qd):
        qname, off = _dname(msg, off)
        qtype = RR_TYPES.get(struct.unpack_from("!H", msg, off)[0], "?")
        off += 4
    sections, sizes = {}, {"header+question": off}
    for sec, count in (("answer", an), ("authority", ns), ("additional", ar)):
        start, rrs = off, []
        for _ in range(count):
            owner, off = _dname(msg, off)
            t, cls, _, rdlen = struct.unpack_from("!HHIH", msg, off)
            off += 10
            rd = msg[off:off + rdlen]
            if t == 1:
                val = socket.inet_ntop(socket.AF_INET, rd)
            elif t == 28:
                val = socket.inet_ntop(socket.AF_INET6, rd)
            elif t in (2, 5):
                val = _dname(msg, off)[0]
            elif t == 41:
                val = f"EDNS udp={cls}"
            else:
                val = f"{rdlen}B"
            rrs.append({"owner": owner, "type": RR_TYPES.get(t, str(t)), "value": val})
            off += rdlen
        sections[sec], sizes[sec] = rrs, off - start
    return {"id": tid, "qr": flags >> 15, "aa": (flags >> 10) & 1, "tc": (flags >> 9) & 1,
            "rd": (flags >> 8) & 1, "rcode": flags & 15, "qname": qname, "qtype": qtype,
            "counts": [qd, an, ns, ar], "sections": sections, "section_bytes": sizes}


def dns_messages(path):
    for no, link, b in _frames(path):
        ip = _ip(link, b)
        if not ip:
            continue
        src, dst, proto, l4 = ip
        if proto == 17 and len(l4) >= 8:
            sport, dport = struct.unpack_from("!HH", l4, 0)
            msg = l4[8:]
        elif proto == 6 and len(l4) >= 20:
            sport, dport = struct.unpack_from("!HH", l4, 0)
            seg = l4[(l4[12] >> 4) * 4:]
            if len(seg) < 14:                 # 핸드셰이크와 순수 ACK
                continue
            msg = seg[2:2 + struct.unpack_from("!H", seg, 0)[0]]
        else:
            continue
        if 53 not in (sport, dport) or len(msg) < 12:
            continue
        try:
            d = _parse_dns(msg)
        except (struct.error, IndexError, ValueError):
            continue
        d.update(no=no, src=src, dst=dst, sport=sport, dport=dport,
                 proto="TCP" if proto == 6 else "UDP", frame_bytes=len(b), dns_bytes=len(msg))
        yield d


def _kind(m):
    if not m["qr"]:
        return "query"
    sec = m["sections"]
    if any(r["type"] == "A" for r in sec["answer"]):
        return "answer"
    if any(r["type"] == "CNAME" for r in sec["answer"]):
        return "cname"
    if m["rcode"] == 0 and any(r["type"] == "NS" for r in sec["authority"]):
        return "delegation"
    return ["noerror", "formerr", "servfail", "nxdomain"][m["rcode"]] if m["rcode"] < 4 else "error"


def _type_counts(rrs):
    c = {}
    for r in rrs:
        c[r["type"]] = c.get(r["type"], 0) + 1
    return ", ".join(f"{t}×{k}" for t, k in c.items()) or "-"


def capture_section():
    """Part A 를 report.md 의 한 절로. 캡처가 없으면 무엇을 하라는 말만 남깁니다."""
    L = ["## Part A · 캡처에서 본 것", ""]
    if not os.path.exists(CAPTURE):
        return L + ["**아직 캡처가 없습니다.** `out/dns.pcapng` 를 만든 뒤 `--report` 를 다시 돌리세요.", ""]
    msgs = list(dns_messages(CAPTURE))
    queries = [m for m in msgs if not m["qr"]]
    responses = [m for m in msgs if m["qr"]]
    if not responses:
        return L + ["캡처에 DNS 응답이 없습니다. 필터가 `port 53` 이었는지 확인하세요.", ""]

    def request_of(r):
        return next((q for q in queries if q["id"] == r["id"] and q["no"] < r["no"]
                     and (q["src"], q["dst"], q["sport"]) == (r["dst"], r["src"], r["dport"])
                     and q["qname"] == r["qname"]), None)

    pairs = [(request_of(r), r) for r in responses]
    deleg = next((r for r in responses if _kind(r) == "delegation"), None)
    answer = next((r for r in responses if _kind(r) == "answer"), None)
    big = max(responses, key=lambda r: r["dns_bytes"])
    q0, r0 = next((p for p in pairs if p[0]), (None, None))
    local = sorted({q["src"] for q in queries})

    L += [f"`out/dns.pcapng`: DNS 메시지 {len(msgs)}개 (질의 {len(queries)}, 응답 {len(responses)}), "
          f"질의를 보낸 주소 {', '.join(local)}. 번호는 Wireshark 의 No. 열입니다.", ""]
    L += ["| No. | 방향 | 서버 | 질의 이름 | ID | an/ns/ar | 종류 | DNS 바이트 |",
          "|---:|---|---|---|---|---|---|---:|"]
    for m in msgs[:80]:
        server = m["src"] if m["qr"] else m["dst"]
        L.append(f"| {m['no']} | {'←' if m['qr'] else '→'} | {server} | `{m['qname']}` | "
                 f"0x{m['id']:04x} | {'/'.join(map(str, m['counts'][1:]))} | {_kind(m)} | {m['dns_bytes']} |")
    if len(msgs) > 80:
        L.append(f"| … | | | {len(msgs) - 80}개 더 | | | | |")
    L.append("")

    L += ["| # | 요구 | 캡처에서 |", "|---|---|---|"]
    walk = []
    if os.path.exists(RUN_LOG):
        walk = re.findall(r"asked (\S+)", open(RUN_LOG, encoding="utf-8").read())
    asked = [q["dst"] for q in queries]
    try:                                   # 지금 이 기계가 밖으로 나갈 때 쓰는 주소
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("198.41.0.4", 53))
            mine = s.getsockname()[0]
    except OSError:
        mine = None
    a1 = (f"모든 질의의 출발지가 {', '.join(local)}"
          + (" — 이 기계의 현재 기본 인터페이스 주소와 같음" if local == [mine] else
             f" — 현재 주소 {mine} 와 다름 (다른 네트워크에서 캡처했다면 정상)"))
    if walk:
        a1 += (f"; 질의 대상 {len(asked)}개가 같은 시간에 돌린 `task1_resolve.py` 의 경로 "
               f"{len(walk)}단계와 {'순서까지 일치' if asked == walk else '일치하지 않음 - 확인 필요'}")
    L.append(f"| A1 | 내 기계에서 뜬 내 질의 | {a1} |")
    if q0:
        L.append(f"| A2 | 질의와 응답의 짝 | No. {q0['no']} 질의 → No. {r0['no']} 응답, 둘 다 "
                 f"ID 0x{q0['id']:04x}, `{q0['qname']}` @ {q0['dst']} |")
    if deleg:
        ns_names = sorted({r["value"] for r in deleg["sections"]["authority"] if r["type"] == "NS"})
        glue = sum(r["type"] in ("A", "AAAA") for r in deleg["sections"]["additional"])
        L.append(f"| A3 | 위임 | No. {deleg['no']}: {deleg['src']} 의 응답, answer 0개, authority NS "
                 f"{len(ns_names)}개 ({', '.join(ns_names[:3])}{' …' if len(ns_names) > 3 else ''}), "
                 f"additional 글루 {glue}개, AA={deleg['aa']} |")
    if answer:
        a = [r["value"] for r in answer["sections"]["answer"] if r["type"] == "A"]
        L.append(f"| A3 | 답변 | No. {answer['no']}: {answer['src']} 의 응답, answer 에 A {', '.join(a)}, "
                 f"AA={answer['aa']} |")
    sb = big["section_bytes"]
    L.append(f"| A4 | 가장 큰 응답 | No. {big['no']}: DNS 메시지 **{big['dns_bytes']} 바이트** "
             f"(프레임 {big['frame_bytes']} 바이트), `{big['qname']}` @ {big['src']}. "
             f"answer {sb['answer']}B [{_type_counts(big['sections']['answer'])}] · "
             f"authority {sb['authority']}B [{_type_counts(big['sections']['authority'])}] · "
             f"additional {sb['additional']}B [{_type_counts(big['sections']['additional'])}] |")
    L += ["", "캡처에 나온 질의 이름 전체 (개인정보 확인용): "
          + ", ".join(f"`{n}`" for n in sorted({q['qname'] for q in queries})), ""]
    return L


# ------------------------------------------------------------------ 보고서
def report():
    """out/chains.json을 읽고 out/report.md를 만듭니다.

    분류 규칙은 classify() 입니다. 정답표 TRUTH 와 비교해 틀린 곳을 스스로 적습니다.
    """
    chains, probe = _load(CHAINS, None), _load(PROBE, None)
    if not chains or not probe:
        raise SystemExit("먼저 python3 task2_steering.py --collect")
    primary, nets, addrinfo = probe["primary"], probe["networks"], probe["addrs"]
    physical = [n for n, i in nets.items() if i["kind"] == "physical"]
    simulated = [n for n, i in nets.items() if i["kind"] != "physical"]
    cols = [f"{n}/{r}" for n in physical for r in RESOLVERS] + [f"{n}/google" for n in simulated]

    def where(col):
        """이 열의 RTT 를 잰 물리 네트워크: 물리 열은 자기 자신, ECS 열은 수집한 곳."""
        n = col.split("/")[0]
        return n if nets[n]["kind"] == "physical" else nets[n].get("collected_from", primary)

    def rtt(ip, net=primary):
        return ((addrinfo.get(ip) or {}).get("rtt_ms") or {}).get(net)

    def best(addrs, net=primary):
        vals = [rtt(a, net) for a in addrs if rtt(a, net) is not None]
        return min(vals) if vals else None

    def org(ip):
        a = (addrinfo.get(ip) or {}).get("as") or {}
        words = a.get("as_name", "").split(" - ", 1)[-1].split(",")[0].replace(".com", "").split()
        drop = {"Inc.", "Inc", "Corporation", "Technologies", "Streaming", "Services",
                "Foundation", "International", "B.V."}
        return " ".join(w for w in words if w not in drop)[:18] or "?"

    def prefixes(addrs):
        return {str(ipaddress.ip_network(a + "/24", strict=False)) for a in addrs}

    def ms(x):
        return "—" if x is None else f"{x:.0f}"

    L = ["# Task 2 · DNS는 정말 가까운 복제 서버로 보내 주는가", ""]
    def label(n):
        """네트워크 이름에 그 네트워크의 공인 주소를 광고하는 AS 를 붙입니다."""
        pa = nets[n].get("public_as") or {}
        owner = pa.get("as_name", "").split(" - ", 1)[-1].split(",")[0]
        return f"`{n}` ({owner}, AS{pa.get('asn')})" if pa else f"`{n}`"

    L += ["수집 " + ", ".join(f"{label(n)} `{nets[n]['collected_at']}`" for n in physical)
          + " · `python3 task2_steering.py --collect --network <이름>` 후 `--report` 로 생성. "
          "원시 데이터 `out/chains.json`, 관측 지점과 주소 정보 `out/probe.json`.", ""]

    # 관측 지점
    L += ["## 관측 지점", "",
          "| network | 종류 | resolver | 실제로 물은 주소 | 권한 서버가 본 리졸버 (Akamai whoami) |",
          "|---|---|---|---|---|"]
    for n in physical:
        i = nets[n]
        pa = i.get("public_as") or {}
        kind = f"물리 · 공인 IP {i['public_ip']} (AS{pa.get('asn')} {pa.get('as_name', '').split(' - ')[-1]})"
        for r, ri in i["resolvers"].items():
            seen = ri.get("seen_by_authority") or {}
            ns_as = seen.get("ns_as") or {}
            view = f"{seen.get('ns', '?')} AS{ns_as.get('asn', '?')}"
            if seen.get("ecs"):
                view += f" · ECS {seen['ecs']}"
            if seen.get("id.server"):
                view += f" · PoP `{seen['id.server']}`"
            used = ri["used"] or "응답 없음"
            if ri["unreachable"]:
                used += f" ({', '.join(ri['unreachable'])} 응답 없음)"
            L.append(f"| {n} | {kind} | {r} | {used} | {view} |")
            kind = ""
    for n in simulated:
        i = nets[n]
        L.append(f"| {n} | ECS 시뮬레이션 · `{i['subnet']}` 을 Google({i['via']})에 실어 보냄 | google | "
                 f"{i['via']} | Google 이 권한 서버로 넘긴 ECS: "
                 f"{(i.get('seen_by_authority') or {}).get('forwarded_ecs') or '없음'} |")
    L.append("")

    L += capture_section()

    # B1 / B4
    rows, wrong, naive_wrong = [], [], []
    L += ["## B1 · B4 · CNAME 체인과 제3자 판정", "",
          f"체인은 `{primary}/system` 리졸버가 준 것입니다. final zone 은 SOA 로 찾은 실제 존의 apex 입니다.", "",
          "| site | chain length | 체인 | final zone | 주소의 AS | third party? (사람) | rule verdict | last-two-labels |",
          "|---|---:|---|---|---|---|---|---|"]
    for site in SITES:
        v = chains[site]["vantages"][f"{primary}/system"]
        final = v["chain"][-1] if v["chain"] else site
        verdict, why = classify(site, final, v["addrs"], addrinfo)
        truth, evidence = TRUTH[site]
        naive = last_two(final) != last_two(site)
        asns = sorted({f"AS{((addrinfo.get(a) or {}).get('as') or {}).get('asn')} {org(a)}" for a in v["addrs"]})
        mark = "✓" if verdict == truth else "**✗**"
        nmark = "✓" if naive == truth else "**✗**"
        chain = " → ".join(f"`{n}`" for n in v["chain"][1:]) or "(CNAME 없음)"
        L.append(f"| {site} | {len(v['chain']) - 1} | {chain} | `{probe['zones'].get(final, '?')}` | "
                 f"{', '.join(asns)} | {'yes' if truth else 'no'} — {evidence} | "
                 f"{'yes' if verdict else 'no'} {mark} ({why}) | "
                 f"{'yes' if naive else 'no'} {nmark} (`{last_two(site)}` vs `{last_two(final)}`) |")
        rows.append((site, truth, verdict))
        if verdict != truth:
            wrong.append((site, final, verdict, why, evidence, v["addrs"]))
        if naive != truth or last_two(site) in MULTI_LABEL_SUFFIXES:
            naive_wrong.append((site, final, naive, naive == truth))
    L.append("")
    L += ["### 규칙", "",
          "1. CNAME 체인을 끝까지 따라가 마지막 이름의 **등록 가능 도메인(eTLD+1)** 을 구한다. "
          "`co.uk`, `ac.kr` 처럼 두 레이블짜리 공용 접미사는 한 덩어리로 본다. 사이트의 eTLD+1 과 다르면 → 제3자.",
          "2. 체인이 자기 도메인 안에서 끝나거나 CNAME 이 없으면, 최종 주소를 광고하는 AS 를 Team Cymru 에 DNS 로 묻는다. "
          f"CDN 이 본업인 회사의 AS({', '.join(sorted(set(CDN_ASNS.values())))}) 이면 → 제3자. CNAME 없는 애니캐스트를 잡기 위한 단계다.",
          "3. 둘 다 아니면 → 자체.", "",
          f"정답과 일치: **{sum(t == v for _, t, v in rows)} / {len(rows)}**", ""]
    L += ["### 규칙이 틀린 곳", ""]
    for site, final, verdict, why, evidence, addrs in wrong:
        asinfo = ((addrinfo.get(addrs[0]) or {}).get("as") or {}) if addrs else {}
        line = (f"- **{site}** — 규칙은 \"{why}\" 라서 {'제3자' if verdict else '자체'}로 판정했다. "
                f"그러나 `{final}` 의 주소 {addrs[0] if addrs else '?'} 를 광고하는 것은 "
                f"AS{asinfo.get('asn')} {asinfo.get('as_name', '')} 이다. 정답: {evidence}.")
        if verdict and why.startswith("체인이"):
            line += " 한 조직이 서로 다른 등록 도메인 두 개를 쓰면, 이름만 보는 규칙은 같은 조직임을 알 수 없다."
        L.append(line)
    if not wrong:
        L.append("- 이 측정에서는 정답표와 모두 일치했다. 아래 마지막 두 레이블 규칙과 비교할 것.")
    L += ["", "마지막 두 레이블만 비교하는 규칙:", ""]
    for site, final, naive, right in naive_wrong:
        if not right:
            L.append(f"- **{site}** — 틀림. `{last_two(site)}` ≠ `{last_two(final)}` 이라 제3자라고 하지만 같은 운영 주체다.")
        else:
            L.append(f"- **{site}** — 우연히 맞음. 사이트의 \"마지막 두 레이블\" `{last_two(site)}` 는 공용 접미사라서 "
                     f"이 규칙은 `{last_two(site)}` 아래의 모든 조직을 같은 조직으로 본다. "
                     f"CNAME 이 같은 접미사의 다른 기관으로 갔다면 자체라고 잘못 판정했을 것이다.")
    L.append("")

    # B2 / B3 / B5
    L += ["## B2 · B3 · B5 · 스티어링", "",
          f"각 칸: 응답 주소를 광고하는 조직, 첫 주소(+나머지 개수), 그 열의 네트워크에서 잰 TCP/443 핸드셰이크 RTT 의 최솟값(ms) "
          f"(ECS 열은 수집한 네트워크에서 잼). "
          f"리졸버마다 {ROUNDS}번 물어 합집합을 냈고, ↻ 는 그 {ROUNDS}번 사이에 집합이 바뀐 것(회전)이다.", "",
          "| site | 3rd | " + " | ".join(cols) + " |", "|---|---|" + "---|" * len(cols)]
    stats = {c: [] for c in cols}
    res_diff, res_strict, net_diff, net_strict = set(), set(), set(), set()
    near, rotating, moved = {c: 0 for c in cols}, set(), {n: set() for n in simulated}
    third = [s for s in SITES if TRUTH[s][0]]
    for site in SITES:
        vs = chains[site]["vantages"]
        cells = []
        everything = {a for c in cols if c in vs for a in vs[c]["addrs"]}
        for c in cols:
            floor = best(everything, where(c))     # 그 네트워크에서 본 가장 가까운 복제 서버
            v = vs.get(c)
            if not v or not v["addrs"]:
                cells.append("—")
                continue
            a = v["addrs"]
            spin = len({tuple(r["addrs"]) for r in v["rounds"] if "addrs" in r}) > 1
            b = best(a, where(c))
            cells.append(f"{org(a[0])} {a[0]}{f' +{len(a) - 1}' if len(a) > 1 else ''} · {ms(b)}"
                         + (" ↻" if spin else ""))
            if site in third:
                if spin:
                    rotating.add(site)
                if b is not None:
                    stats[c].append(b)
                if b is not None and floor is not None and b - floor <= NEAR_MS:
                    near[c] += 1
        L.append(f"| {site} | {'yes' if TRUTH[site][0] else 'no'} | " + " | ".join(cells) + " |")
        for n in simulated:             # ECS 가 답을 정말 옮겼나: 같은 네트워크의 Google, /24 가 하나도 안 겹침
            base = vs.get(f"{nets[n].get('collected_from', primary)}/google", {}).get("addrs")
            other = vs.get(f"{n}/google", {}).get("addrs")
            if base and other and not (prefixes(base) & prefixes(other)):
                moved[n].add(site)
        if site not in third:
            continue
        for n in physical:
            sets = [vs[f"{n}/{r}"]["addrs"] for r in RESOLVERS if vs.get(f"{n}/{r}", {}).get("addrs")]
            if len({frozenset(s) for s in sets}) > 1:
                res_diff.add(site)
            if any(not (prefixes(x) & prefixes(y)) for i, x in enumerate(sets) for y in sets[i + 1:]):
                res_strict.add(site)
        by_res = {}                     # 같은 resolver 를 네트워크끼리 비교
        for c in cols:
            if vs.get(c, {}).get("addrs"):
                by_res.setdefault(c.split("/")[1], []).append(vs[c]["addrs"])
        for sets in by_res.values():
            if len({frozenset(x) for x in sets}) > 1:
                net_diff.add(site)
            if any(not (prefixes(x) & prefixes(y)) for i, x in enumerate(sets) for y in sets[i + 1:]):
                net_strict.add(site)
    L.append("")

    N = len(third)
    anyd = res_diff | net_diff
    two_nets = len(physical) >= 2
    vantage_names = " · ".join(label(n) for n in physical)
    if simulated:
        vantage_names += ", ECS 흉내 " + " · ".join(f"`{n}` ({nets[n]['subnet']})" for n in simulated)
    L += ["### 스티어링 수치 (B5)", "",
          f"네트워크: {vantage_names}.", "",
          f"제3자 CDN 사이트 N = **{N}** (사람 판정 기준: {', '.join(s.replace('www.', '') for s in third)}).", "",
          f"- **{len(anyd)} / {N}** 사이트가 다른 resolver 나 다른 네트워크에 다른 주소 집합으로 응답했다.",
          f"  - 같은 네트워크(`{'`, `'.join(physical)}`)에서 resolver 만 바꿨을 때: **{len(res_diff)} / {N}**"
          f" — 그중 /24 가 하나도 겹치지 않는 것: {len(res_strict)} / {N}",
          f"  - 관측 지점({', '.join(f'`{n}`' for n in physical + simulated)})을 바꿨을 때 (같은 resolver 끼리): "
          f"**{len(net_diff)} / {N}** — 그중 /24 가 하나도 겹치지 않는 것: {len(net_strict)} / {N}",
          f"  - 같은 resolver 에 {ROUNDS}번 물었는데 집합이 바뀐 것(회전): {len(rotating)} / {N}"
          " — \"다르다\"의 일부는 위치가 아니라 로드밸런싱이다.", ""]
    for n in simulated:
        cdn = sorted(moved[n] & set(third))
        other = sorted(moved[n] - set(third))
        L.append(f"- ECS `{nets[n]['subnet']}` (`{n}`) 로 답이 `{nets[n].get('collected_from', primary)}/google` 과 다른 /24 로 옮겨 간 사이트: "
                 f"제3자 CDN {len(cdn)} / {N}{' (' + ', '.join(cdn) + ')' if cdn else ''}, "
                 f"나머지 {len(other)} / {len(SITES) - N}{' (' + ', '.join(other) + ')' if other else ''}")
    L.append("")
    L += ["가까움 — 사이트별로 본 모든 복제 서버 중 가장 빠른 것보다 "
          f"{NEAR_MS:.0f} ms 이내인 답을 준 횟수, 그리고 그 답의 RTT 중앙값 (각 열의 네트워크에서 측정):", "",
          "| 관측 지점 | 가까운 답 | RTT 중앙값 (ms) |", "|---|---:|---:|"]
    for c in cols:
        med = statistics.median(stats[c]) if stats[c] else None
        L.append(f"| `{c}` | {near[c]} / {N} | {ms(med)} |")
    L.append("")
    if two_nets:
        a, b = physical[0], physical[1]
        L += [f"### 두 네트워크 교차 비교 (B3) — `{a}` 와 `{b}`", "",
              f"두 네트워크의 system resolver 가 서로 다른 답을 준 제3자 CDN 사이트에서, 각 네트워크가 받은 답과 상대가 받은 답까지의 "
              f"RTT 를 **같은 네트워크에서** 잰 것. 주장 (b) 가 맞다면 \"내 답\"이 \"남의 답\"보다 가까워야 한다.", "",
              f"| site | `{a}` 에서: 내 답 / 남의 답 | `{b}` 에서: 내 답 / 남의 답 |", "|---|---|---|"]
        tally = {"near": 0, "tie": 0, "far": 0, "n/a": 0}

        def judge(own, other):
            if own is None or other is None:
                return "n/a"
            return "near" if own < other - NEAR_MS else "far" if own > other + NEAR_MS else "tie"

        mark = {"near": "✓ 내 답이 가까움", "tie": "≈ 차이 없음", "far": "✗ 남의 답이 가까움", "n/a": "측정 없음"}
        swapped = 0
        for site in third:
            vs = chains[site]["vantages"]
            sa, sb = vs.get(f"{a}/system", {}).get("addrs"), vs.get(f"{b}/system", {}).get("addrs")
            if not sa or not sb or set(sa) == set(sb):
                continue
            swapped += 1
            cells = []
            for net, own, other in ((a, sa, sb), (b, sb, sa)):
                j = judge(best(own, net), best(other, net))
                tally[j] += 1
                cells.append(f"{ms(best(own, net))} / {ms(best(other, net))} {mark[j]}")
            L.append(f"| {site} | {cells[0]} | {cells[1]} |")
        L += ["", f"system resolver 가 네트워크마다 다른 답을 준 사이트 **{swapped} / {N}**, 그 비교 {2 * swapped}번 중 "
              f"내 답이 {NEAR_MS:.0f} ms 넘게 가까움 **{tally['near']}**, 차이 없음 {tally['tie']}, "
              f"남의 답이 더 가까움 **{tally['far']}**" + (f", 측정 없음 {tally['n/a']}" if tally["n/a"] else "")
              + f" (나머지 {N - swapped}개는 두 네트워크에 같은 주소를 줬다 — 애니캐스트이거나 같은 PoP).", ""]
    else:
        L += ["**B3 는 경로 (B) 로 했다.** 두 번째 물리 네트워크에서는 아직 측정하지 않았다. 대신 "
              "(1) 같은 회선에서 거리가 매우 다른 resolver 들 — 위 표의 \"권한 서버가 본 리졸버\" 열이 각 resolver 가 "
              "실제로 어디서 권한 서버에 묻는지 보여 준다 — 과 (2) ECS 로 다른 서브넷의 사용자를 흉내 낸 관측 지점을 비교했다. "
              "약해지는 점: ECS 는 권한 서버가 ECS 를 존중할 때만 효과가 있고, 흉내 낸 지점의 RTT 는 그 지점이 아니라 "
              f"`{primary}` 에서 잰 것이라 \"그 사용자에게 가까운가\"는 직접 확인하지 못한다. "
              "휴대폰 테더링에 붙은 뒤 `python3 task2_steering.py --collect --network lte` 를 돌리면 "
              "이 보고서에 두 번째 물리 네트워크가 열로 붙는다.", ""]

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"  -> {os.path.relpath(REPORT, HERE)}")
    print(f"  rule {sum(t == v for _, t, v in rows)}/{len(rows)} · steering {len(anyd)}/{N} "
          f"(resolver {len(res_diff)}, network {len(net_diff)})")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--collect", action="store_true")
    p.add_argument("--report", action="store_true")
    p.add_argument("--rtt", action="store_true",
                   help="응답은 그대로 두고, 이미 본 주소들의 RTT 만 --network 에서 다시 잽니다")
    p.add_argument("--network", default="home-wifi",
                   help="이 측정을 저장할 네트워크 이름 (B3: 다른 네트워크에서는 다른 이름으로)")
    a = p.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.collect:
        collect(a.network)
    elif a.rtt:
        remeasure(a.network)
    elif a.report:
        report()
    else:
        p.print_help()
