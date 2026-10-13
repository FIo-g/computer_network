#!/usr/bin/env python3
"""Week 4 · Task 2 — 내 링크를, 한 번이 아니라 여러 번 재세요.

교재 §3.5 (핸드셰이크, 순서 번호)와 §3.7 (처리량을 제한하는 것).

이것은 실습 과제입니다. 이 스크립트가 내는 숫자는 *지금 이 순간* *여러분의* 연결에
관한 것이며, 다른 누구의 것과도, 한 시간 뒤 여러분 자신의 것과도 같지 않을 것입니다.
그것은 측정의 문제가 아니라 발견입니다.

    python3 task2_measure.py --label "campus wifi"
    python3 task2_measure.py --label "tethering"

각 실행은 out/throughput.json에 덧붙으므로 나중에 비교할 수 있습니다.

    python3 task2_measure.py --report                       # out/report.md
    python3 task2_measure.py --report --capture ../traces/tcp-wireshark-trace1-1.pcapng

`--report` 는 out/tcp.pcapng (파트 A) 와 out/throughput.json (파트 B) 을 읽어 보고서를
씁니다. 캡처는 tshark 없이 직접 풉니다. 경로 (B) 라면 `--capture` 로 공식 trace 를 주세요.
"""
import argparse, ipaddress, json, os, shutil, socket, statistics, struct, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
THROUGHPUT = os.path.join(OUT, "throughput.json")
CAPTURE = os.path.join(OUT, "tcp.pcapng")
REPORT = os.path.join(OUT, "report.md")

# 이웃이 아닌 호스트에서 몇 MB. 이 주소가 죽으면 바꾸세요 - 바꿨다면 observation.md에
# 그렇게 적으세요. 거리도 여러분이 재는 것의 일부이기 때문입니다.
TARGET = "https://speed.cloudflare.com/__down?bytes=5000000"
REPEATS = 5

# 서버가 본 나: 공인 IP 와 응답한 Cloudflare 데이터센터(colo). 어느 네트워크에서 쟀는지 남깁니다.
WHOAMI = "https://speed.cloudflare.com/cdn-cgi/trace"

INIT_CWND = 10     # 초기 혼잡 윈도(세그먼트). RFC 6928, 오늘날 서버의 기본값
MSS = 1448         # 캡처가 없을 때 쓰는 세그먼트 크기: 1500 - IP 20 - TCP 20 - 타임스탬프 12

CURL_FIELDS = ["time_namelookup", "time_connect", "time_appconnect", "time_starttransfer",
               "time_total", "size_download", "local_ip", "local_port", "remote_ip",
               "remote_port", "http_version"]


# ------------------------------------------------------------------ 측정 (파트 B)
def one_run():
    """전송 한 번. 초 단위 시간들, 바이트, 그리고 curl 자신의 시간 분해를 돌려줍니다.

    curl 의 시각은 모두 요청 시작부터 누적입니다. 구간으로 바꾸면:
      dns        이름 조회
      connect    TCP 핸드셰이크: SYN 을 보내고 SYN-ACK 를 받기까지 = 1 RTT
      tls        TLS 핸드셰이크 (TLS 1.3 이면 1 RTT)
      wait       요청을 보내고 첫 바이트가 오기까지 = 1 RTT + 서버 처리
      transfer   첫 바이트부터 마지막 바이트까지 - 혼잡 윈도가 자라는 구간
    """
    fmt = " ".join("%{" + f + "}" for f in CURL_FIELDS)
    started = time.time()
    r = subprocess.run(["curl", "-s", "-o", os.devnull, "-w", fmt, TARGET],
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"curl failed: {r.stderr.strip() or r.returncode}")
    v = dict(zip(CURL_FIELDS, r.stdout.split()))
    dns, conn, tls, first, total = (float(v[k]) for k in CURL_FIELDS[:5])
    size = int(v["size_download"])
    tls_done = tls or conn                 # http:// 이면 appconnect 는 0
    return {
        "dns_s": dns,
        "connect_s": conn - dns,           # 이것이 여러분의 TCP 핸드셰이크입니다
        "tls_s": tls_done - conn,
        "wait_s": first - tls_done,
        "ttfb_s": first - conn,            # 연결 뒤 첫 바이트까지 (tls + wait)
        "transfer_s": total - first,
        "total_s": total,
        "bytes": size,
        "mbps": size * 8 / total / 1e6 if total else 0,
        "transfer_mbps": size * 8 / (total - first) / 1e6 if total > first else 0,
        "started": round(started, 3),      # 캡처의 시각과 맞춰 보기 위한 유닉스 시각
        "local": [v.get("local_ip"), int(v.get("local_port") or 0)],
        "remote": [v.get("remote_ip"), int(v.get("remote_port") or 0)],
        "http": v.get("http_version"),
    }


def origin_as(ip):
    """ip 를 광고하는 AS. Team Cymru 에 DNS 로 묻습니다 (3주차와 같은 방법). 없으면 None."""
    if not shutil.which("dig"):
        return None
    try:
        rev = ipaddress.ip_address(ip).reverse_pointer.rsplit(".", 2)[0]
    except ValueError:
        return None
    zone = "origin6.asn.cymru.com" if ":" in ip else "origin.asn.cymru.com"

    def txt(name):
        out = subprocess.run(["dig", "+short", "+time=3", "+tries=1", name, "TXT"],
                             capture_output=True, text=True).stdout
        return [l.strip().strip('"') for l in out.splitlines() if l.strip()]

    rows = [[x.strip() for x in t.split("|")] for t in txt(f"{rev}.{zone}")]
    rows = [r for r in rows if len(r) >= 3 and r[0].split()[0].isdigit()]
    if not rows:
        return None
    best = max(rows, key=lambda r: int(r[1].split("/")[1]) if "/" in r[1] else 0)
    asn = int(best[0].split()[0])
    name = txt(f"AS{asn}.asn.cymru.com")
    return {"asn": asn, "prefix": best[1], "cc": best[2],
            "as_name": name[0].split("|")[-1].strip() if name else ""}


def default_interface():
    """기본 경로가 나가는 인터페이스 (en0 = Wi-Fi 인 경우가 많고, 테더링이면 바뀝니다)."""
    for cmd, key in ((["route", "-n", "get", "default"], "interface:"),
                     (["ip", "route", "show", "default"], "dev")):
        if not shutil.which(cmd[0]):
            continue
        words = subprocess.run(cmd, capture_output=True, text=True).stdout.split()
        if key in words and words.index(key) + 1 < len(words):
            return words[words.index(key) + 1]
    return None


def whereami():
    info = {"interface": default_interface()}
    r = subprocess.run(["curl", "-s", "-m", "10", WHOAMI], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        k, _, v = line.partition("=")
        if k in ("ip", "colo", "loc", "http", "tls"):
            info[k] = v
    if info.get("ip"):
        info["as"] = origin_as(info["ip"])
    return info


def measure(label, repeats):
    os.makedirs(OUT, exist_ok=True)
    net = whereami()
    a = net.get("as") or {}
    print(f"  {label}: 공인 IP {net.get('ip', '?')} (AS{a.get('asn', '?')} "
          f"{a.get('as_name', '').split(' - ')[-1]}) · Cloudflare {net.get('colo', '?')} · "
          f"인터페이스 {net.get('interface') or '?'}\n")

    runs = []
    for i in range(repeats):
        for attempt in range(3):
            try:
                r = one_run()
                break
            except RuntimeError as e:
                print(f"  {i + 1}/{repeats}  실패 ({e}) - 다시 시도")
                time.sleep(2)
        else:
            raise SystemExit("  세 번 연속 실패했습니다. 아무것도 기록하지 않았습니다.")
        runs.append(r)
        print(f"  {i + 1}/{repeats}  {r['mbps']:7.2f} Mbps   "
              f"handshake {r['connect_s'] * 1000:6.1f} ms   "
              f"ttfb {r['ttfb_s'] * 1000:6.1f} ms   "
              f"port {r['local'][1]}")
        time.sleep(1)

    mbps = [r["mbps"] for r in runs]
    record = {
        "label": label,
        "when": time.strftime("%Y-%m-%d %H:%M:%S"),
        "target": TARGET,
        "network": net,
        "runs": runs,
        "mbps_median": statistics.median(mbps),
        "mbps_min": min(mbps),
        "mbps_max": max(mbps),
        "handshake_ms_median": statistics.median(
            r["connect_s"] * 1000 for r in runs),
    }

    all_records = _load(THROUGHPUT, [])
    all_records.append(record)
    with open(THROUGHPUT, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    spread = (max(mbps) - min(mbps)) / statistics.median(mbps) if mbps else 0
    print(f"\n  {label}:  median {record['mbps_median']:.2f} Mbps, "
          f"spread {spread:.0%} across {repeats} runs")
    print(f"  handshake median {record['handshake_ms_median']:.1f} ms")
    print(f"  -> out/throughput.json  ({len(all_records)} record(s) so far)")


def _load(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


# ------------------------------------------------------------------ 캡처 읽기 (파트 A)
# tshark 없이도 읽도록 pcapng/pcap -> 링크 계층 -> IP -> TCP 를 직접 풉니다.
FIN, SYN, RST, PSH, ACK = 0x01, 0x02, 0x04, 0x08, 0x10


def _frames(path):
    """(번호, 시각(초), linktype, 바이트). 번호는 Wireshark 의 No. 열과 같습니다."""
    with open(path, "rb") as f:
        data = f.read()
    n = 0
    if data[:4] == b"\x0a\x0d\x0d\x0a":                      # pcapng
        off, e, ifaces = 0, "<", []
        while off + 12 <= len(data):
            if data[off:off + 4] == b"\x0a\x0d\x0d\x0a":     # 섹션마다 바이트 순서가 새로 정해짐
                e = "<" if data[off + 8:off + 12] == b"\x4d\x3c\x2b\x1a" else ">"
                ifaces = []
            btype, blen = struct.unpack_from(e + "II", data, off)
            if blen < 12:
                break
            body = data[off + 8:off + blen - 4]
            if btype == 1:                                   # Interface Description
                link = struct.unpack_from(e + "H", body, 0)[0]
                res, o = 1e-6, 8                             # 기본 해상도는 마이크로초
                while o + 4 <= len(body):
                    code, ln = struct.unpack_from(e + "HH", body, o)
                    if code == 0:
                        break
                    if code == 9 and ln >= 1:                # if_tsresol
                        v = body[o + 4]
                        res = 2.0 ** -(v & 0x7F) if v & 0x80 else 10.0 ** -v
                    o += 4 + (ln + 3) // 4 * 4
                ifaces.append((link, res))
            elif btype == 6:                                 # Enhanced Packet
                iface, hi, lo, caplen, _ = struct.unpack_from(e + "IIIII", body, 0)
                link, res = ifaces[iface]
                n += 1
                yield n, ((hi << 32) | lo) * res, link, body[20:20 + caplen]
            elif btype == 3:                                 # Simple Packet (시각 없음)
                n += 1
                yield n, 0.0, ifaces[0][0], body[4:4 + struct.unpack_from(e + "I", body, 0)[0]]
            off += blen
    else:                                                    # 고전 pcap
        magic = data[:4]
        e = "<" if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1") else ">"
        res = 1e-9 if magic in (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d") else 1e-6
        link, off = struct.unpack_from(e + "I", data, 20)[0] & 0xFFFF, 24
        while off + 16 <= len(data):
            sec, frac, caplen = struct.unpack_from(e + "III", data, off)
            n += 1
            yield n, sec + frac * res, link, data[off + 16:off + 16 + caplen]
            off += 16 + caplen


def _ip(link, b):
    """링크 계층을 벗겨 (src, dst, proto, L4 바이트, IP 헤더가 말하는 L4 길이)."""
    if link in (149, 258):                   # Apple PKTAP: 헤더 길이, 다음 타입, 안쪽 DLT
        hl, _, inner = struct.unpack_from("<III", b, 0)
        return _ip(inner, b[hl:])
    if link == 1:                            # Ethernet (+VLAN)
        et, off = struct.unpack_from("!H", b, 12)[0], 14
        while et == 0x8100:
            et, off = struct.unpack_from("!H", b, off + 2)[0], off + 4
        b = b[off:] if et in (0x0800, 0x86DD) else b""
    elif link == 113:                        # Linux cooked (any 인터페이스)
        b = b[16:]
    elif link in (0, 108):                   # BSD loopback, utun
        b = b[4:]
    elif link not in (12, 14, 101):          # raw IP
        return None
    if len(b) >= 20 and b[0] >> 4 == 4:
        ihl, total = (b[0] & 15) * 4, struct.unpack_from("!H", b, 2)[0]
        return (socket.inet_ntop(socket.AF_INET, b[12:16]),
                socket.inet_ntop(socket.AF_INET, b[16:20]), b[9], b[ihl:total], total - ihl)
    if len(b) >= 40 and b[0] >> 4 == 6:
        plen = struct.unpack_from("!H", b, 4)[0]
        return (socket.inet_ntop(socket.AF_INET6, b[8:24]),
                socket.inet_ntop(socket.AF_INET6, b[24:40]), b[6], b[40:40 + plen], plen)
    return None


def _tcp(l4, l4len):
    """TCP 헤더와 옵션. 페이로드 길이는 캡처 길이가 아니라 IP 헤더에서 계산합니다."""
    sport, dport, seq, ack, off_flags, win = struct.unpack_from("!HHIIHH", l4, 0)
    hl = (off_flags >> 12) * 4
    opts, i = {}, 20
    while i < min(hl, len(l4)):
        kind = l4[i]
        if kind == 0:                        # 옵션 목록 끝
            break
        if kind == 1:                        # NOP: 4바이트 정렬용
            i += 1
            continue
        ln = l4[i + 1] if i + 1 < len(l4) else 0
        if ln < 2:
            break
        body = l4[i + 2:i + ln]
        if kind == 2 and ln == 4:
            opts["mss"] = struct.unpack("!H", body)[0]
        elif kind == 3 and ln == 3:
            opts["wscale"] = body[0]
        elif kind == 4:
            opts["sack_perm"] = True
        elif kind == 5:
            opts["sack_blocks"] = (ln - 2) // 8
        elif kind == 8 and ln == 10:
            opts["ts"] = struct.unpack("!II", body)
        i += ln
    return {"sport": sport, "dport": dport, "seq": seq, "ack": ack, "flags": off_flags & 0x1FF,
            "win": win, "opts": opts, "payload": max(0, l4len - hl)}


def tcp_segments(path):
    for no, t, link, b in _frames(path):
        try:
            ip = _ip(link, b)
            if not ip or ip[2] != 6 or len(ip[3]) < 20:
                continue
            seg = _tcp(ip[3], ip[4])
        except (struct.error, IndexError, ValueError):
            continue
        seg.update(no=no, t=t, src=ip[0], dst=ip[1])
        yield seg


def connections(path):
    """캡처 안에서 SYN 으로 시작한 연결들. 캡처 전에 열린 연결은 핸드셰이크가 없어 뺍니다."""
    conns = {}
    for s in tcp_segments(path):
        fwd = (s["src"], s["sport"], s["dst"], s["dport"])
        rev = (s["dst"], s["dport"], s["src"], s["sport"])
        if fwd in conns:
            c, s["from_client"] = conns[fwd], True
        elif rev in conns:
            c, s["from_client"] = conns[rev], False
        elif s["flags"] & SYN and not s["flags"] & ACK:
            c, s["from_client"] = conns.setdefault(fwd, {"key": fwd, "segs": []}), True
        else:
            continue
        c["segs"].append(s)
    return list(conns.values())


def analyse(conn):
    """한 연결의 핸드셰이크, 옵션, 윈도, 비행량. 핸드셰이크가 불완전하면 None."""
    segs = conn["segs"]
    syn = segs[0]
    synack = next((s for s in segs if not s["from_client"] and s["flags"] & SYN
                   and s["flags"] & ACK and s["ack"] == (syn["seq"] + 1) % 2 ** 32), None)
    if synack is None:
        return None
    ack = next((s for s in segs if s["from_client"] and s["no"] > synack["no"]
                and s["flags"] & ACK and not s["flags"] & SYN
                and s["ack"] == (synack["seq"] + 1) % 2 ** 32), None)

    # 윈도 스케일은 양쪽 SYN 에 모두 있어야 켜지고, SYN 자신의 윈도 필드에는 적용되지 않습니다.
    scaled = "wscale" in syn["opts"] and "wscale" in synack["opts"]
    shift = {True: syn["opts"].get("wscale", 0) if scaled else 0,
             False: synack["opts"].get("wscale", 0) if scaled else 0}
    isn = {True: syn["seq"], False: synack["seq"]}
    sent = {side: sum(s["payload"] for s in segs if s["from_client"] == side) for side in (True, False)}
    sender = sent[True] > sent[False]          # True: 클라이언트가 보냄(업로드)

    # 캡처한 위치: 클라이언트 쪽이면 SYN -> SYN-ACK 가 한 RTT, SYN-ACK -> ACK 는 거의 0.
    d1 = synack["t"] - syn["t"]
    d2 = (ack["t"] - synack["t"]) if ack else 0.0
    at_client = d1 >= d2
    rtt = d1 + d2
    at_sender = sender == at_client

    # 비행량 = 보낸 가장 높은 순서 번호 - 확인받은 번호.
    # 송신 쪽에서 캡처했다면 그대로 보입니다. 수신 쪽이라면 송신자는 우리가 한 RTT 전에 보낸
    # ACK 까지만 알고 있으므로, 한 RTT 전의 ACK 와 비교합니다.
    lag = 0.0 if at_sender else rtt
    rx = [(s["t"], (s["ack"] - isn[sender]) % 2 ** 32, s["win"] << shift[not sender])
          for s in segs if s["from_client"] != sender and s["flags"] & ACK and not s["flags"] & SYN]
    data = [s for s in segs if s["from_client"] == sender and s["payload"] > 0]
    i, acked, rwnd, top, retx, flights = 0, 1, None, 1, 0, []
    for s in data:
        while i < len(rx) and rx[i][0] <= s["t"] - lag:
            _, acked, rwnd = rx[i]
            i += 1
        end = (s["seq"] - isn[sender]) % 2 ** 32 + s["payload"]
        if end <= top:
            retx += 1                          # 이미 보낸 구간을 다시 보냄
        top = max(top, end)
        flights.append({"no": s["no"], "t": s["t"], "flight": max(0, top - acked), "rwnd": rwnd})

    wins = [w for _, _, w in rx if w]
    # MSS 옵션은 TCP 옵션을 빼지 않은 값입니다. 양쪽이 타임스탬프를 쓰면 세그먼트마다 12 B 를 씁니다.
    # 이건 상한일 뿐이라, 세그먼트 수는 송신자가 실제로 가장 많이 보낸 페이로드 크기로 셉니다.
    mss_opt = (min(syn["opts"].get("mss", MSS), synack["opts"].get("mss", MSS))
               - (12 if "ts" in syn["opts"] and "ts" in synack["opts"] else 0))
    return {
        "key": conn["key"], "syn": syn, "synack": synack, "ack": ack, "scaled": scaled,
        "shift": shift, "sender_is_client": sender, "at_client": at_client, "rtt": rtt,
        "d1": d1, "d2": d2, "at_sender": at_sender, "bytes": top - 1, "sent": sent,
        "retx": retx, "flights": flights, "rwnd": wins, "segments": len(segs),
        "duration": (data[-1]["t"] - data[0]["t"]) if len(data) > 1 else 0.0,
        "mss_opt": mss_opt,
        "mss": statistics.mode(s["payload"] for s in data) if data else mss_opt,
    }


# ------------------------------------------------------------------ 보고서
def _fmt_opts(o):
    parts = []
    if "mss" in o:
        parts.append(f"MSS {o['mss']}")
    if "wscale" in o:
        parts.append(f"WS {o['wscale']} (×{2 ** o['wscale']})")
    if o.get("sack_perm"):
        parts.append("SACK 허용")
    if "ts" in o:
        parts.append("타임스탬프")
    return " · ".join(parts) or "없음"


def _flags(f):
    return ",".join(n for bit, n in ((SYN, "SYN"), (ACK, "ACK"), (PSH, "PSH"), (FIN, "FIN"),
                                     (RST, "RST")) if f & bit)


def _runs_by_port(records):
    """curl 이 기록한 로컬 포트 -> (label, 몇 번째 실행). 캡처의 연결이 내 것인지 보는 근거."""
    out = {}
    for rec in records:
        for k, r in enumerate(rec.get("runs", []), 1):
            port = (r.get("local") or [None, None])[1]
            if port:
                out[port] = (rec["label"], k, rec.get("when", ""))
    return out


def capture_section(path, records):
    L = ["## 파트 A · 캡처에서 본 핸드셰이크", ""]
    rel = os.path.relpath(path, HERE)
    if not os.path.exists(path):
        hosts = sorted({r["remote"][0] for rec in records for r in rec.get("runs", [])
                        if r.get("remote") and r["remote"][0]})
        filt = "tcp port 443" + (" and (" + " or ".join(f"host {h}" for h in hosts) + ")" if hosts else "")
        return L + [f"아직 캡처가 없습니다. Wireshark 를 캡처 필터 `{filt}` 로 켠 채 "
                    "`python3 task2_measure.py --label ...` 을 돌리고, `out/tcp.pcapng` 로 저장한 뒤 "
                    "`--report` 를 다시 돌리세요. 필터의 주소는 지금까지 curl 이 연결한 서버입니다 - "
                    "좁힐수록 다른 트래픽이 덜 들어갑니다. 경로 (B) 라면 `--capture <공식 trace>`.", ""]

    by_port = _runs_by_port(records)
    conns = [a for a in (analyse(c) for c in connections(path)) if a]
    if not conns:
        return L + [f"`{rel}` 에서 완전한 핸드셰이크(SYN, SYN-ACK)를 찾지 못했습니다. "
                    "전송을 시작하기 전에 캡처를 켰는지 확인하세요.", ""]

    def mine(a):
        return by_port.get(a["key"][1])

    focus = max(conns, key=lambda a: (mine(a) is not None, a["bytes"]))
    L += [f"`{rel}` 에서 SYN 으로 시작한 연결 {len(conns)}개. 번호는 Wireshark 의 No. 열입니다.", "",
          "| 클라이언트 | 서버 | 세그먼트 | 클라이언트→서버 B | 서버→클라이언트 B | throughput.json 의 실행 |",
          "|---|---|---:|---:|---:|---|"]
    for a in conns[:20]:
        c_ip, c_port, s_ip, s_port = a["key"]
        m = mine(a)
        L.append(f"| {c_ip}:{c_port} | {s_ip}:{s_port} | {a['segments']} | {a['sent'][True]:,} | "
                 f"{a['sent'][False]:,} | {f'`{m[0]}` {m[1]}번째' if m else '-'} |")
    if len(conns) > 20:
        L.append(f"| … {len(conns) - 20}개 더 | | | | | |")
    L.append("")

    a = focus
    c_ip, c_port, s_ip, s_port = a["key"]
    t0 = a["syn"]["t"]
    L += [f"### 자세히 본 연결: {c_ip}:{c_port} → {s_ip}:{s_port}", "",
          "| No. | 시각 (ms, SYN 기준) | 방향 | 플래그 | seq (raw) | ack (raw) | window 필드 | 옵션 |",
          "|---:|---:|---|---|---:|---:|---:|---|"]
    for s in (a["syn"], a["synack"], a["ack"]):
        if s is None:
            continue
        L.append(f"| {s['no']} | {(s['t'] - t0) * 1000:.2f} | {'→' if s['from_client'] else '←'} | "
                 f"{_flags(s['flags'])} | {s['seq']:,} | {s['ack']:,} | {s['win']:,} | {_fmt_opts(s['opts'])} |")
    L.append("")

    m = mine(a)
    where = "클라이언트" if a["at_client"] else "서버"
    a1 = (f"클라이언트 {c_ip}:{c_port}. 캡처 위치는 {where} 쪽 (SYN→SYN-ACK {a['d1'] * 1000:.2f} ms, "
          f"SYN-ACK→ACK {a['d2'] * 1000:.2f} ms - 한 RTT 를 기다린 쪽이 SYN 을 보낸 쪽)")
    a1 += (f". `throughput.json` 의 `{m[0]}` {m[1]}번째 실행이 curl 로 같은 로컬 포트 {c_port} 를 기록함"
           if m else ". `throughput.json` 에 이 포트를 쓴 실행이 없음 - 다른 프로그램의 연결이거나 다른 때의 캡처")
    L += ["| # | 요구 | 캡처에서 |", "|---|---|---|", f"| A1 | 내 기계에서 뜬 내 트래픽 | {a1} |"]
    L.append(f"| A2 | 핸드셰이크 | SYN No. {a['syn']['no']} → SYN-ACK No. {a['synack']['no']} → "
             f"ACK No. {a['ack']['no'] if a['ack'] else '?'} |")
    ci, si = a["syn"]["seq"], a["synack"]["seq"]
    L.append(f"| A3 | 초기 순서 번호 | 클라이언트 ISN {ci:,}, 서버 ISN {si:,} (raw). "
             f"SYN-ACK 의 ack = {a['synack']['ack']:,} = 클라이언트 ISN + 1, "
             f"ACK 의 ack = {a['ack']['ack'] if a['ack'] else 0:,} = 서버 ISN + 1. "
             "Wireshark 가 기본으로 보여 주는 0 은 상대 번호입니다 (`tcp.seq_raw` 로 확인) |")
    L.append(f"| A4 | SYN 옵션 | 클라이언트 SYN: {_fmt_opts(a['syn']['opts'])}. "
             f"서버 SYN-ACK: {_fmt_opts(a['synack']['opts'])}. 윈도 스케일 "
             + (f"켜짐 - 클라이언트가 보내는 윈도는 ×{2 ** a['shift'][True]}, 서버가 보내는 윈도는 "
                f"×{2 ** a['shift'][False]}" if a["scaled"] else "꺼짐 (한쪽 SYN 에 없음)") + " |")

    flights = [f for f in a["flights"] if f["rwnd"]]
    recv = "클라이언트" if not a["sender_is_client"] else "서버"
    if flights and a["rwnd"]:
        peak = max(flights, key=lambda f: f["flight"])
        how = ("송신 쪽 캡처라 보낸 최고 순서 번호 - 받은 ACK 그대로"
               if a["at_sender"] else
               f"수신 쪽 캡처라 받은 최고 순서 번호 - 한 RTT({a['rtt'] * 1000:.1f} ms) 전에 보낸 ACK")
        rw = sorted(a["rwnd"])
        L.append(f"| A5 | 광고 윈도 vs 실제 비행량 | 수신자({recv})가 광고한 윈도(스케일 적용): 중앙값 "
                 f"{statistics.median(rw):,.0f} B, 범위 {rw[0]:,}~{rw[-1]:,} B. 실제 비행량 최대 "
                 f"{peak['flight']:,} B ({peak['flight'] / a['mss']:.0f} 세그먼트, No. {peak['no']}, "
                 f"{(peak['t'] - t0) * 1000:.0f} ms), 그때 광고 윈도 {peak['rwnd']:,} B 의 "
                 f"{peak['flight'] / peak['rwnd']:.0%}. 추정 방식: {how} |")
    else:
        L.append("| A5 | 광고 윈도 vs 실제 비행량 | 데이터 세그먼트가 없어 계산하지 못함 |")
    rate = a["bytes"] * 8 / a["duration"] / 1e6 if a["duration"] else 0
    L += ["", f"이 연결: {a['bytes']:,} B 를 {a['duration'] * 1000:.0f} ms 동안 → {rate:.1f} Mbps. "
              f"다시 보낸 세그먼트 {a['retx']}개. 데이터 세그먼트 크기 {a['mss']} B (가장 많이 보낸 "
              f"페이로드 크기. SYN 옵션으로 계산한 상한은 {a['mss_opt']} B).", ""]

    # 비행량이 RTT 마다 어떻게 자라는지 - 슬로 스타트가 보이는 곳
    if a["flights"] and a["rtt"] > 0:
        start = a["flights"][0]["t"]
        rounds = {}
        for f in a["flights"]:
            k = int((f["t"] - start) / a["rtt"])
            if f["flight"] > rounds.get(k, (0, None))[0]:
                rounds[k] = (f["flight"], f["rwnd"])
        L += [f"RTT({a['rtt'] * 1000:.1f} ms) 단위로 끊어 본 비행량 최댓값:", "",
              "| 첫 데이터부터 RTT | 비행량 B | 세그먼트 | 광고 윈도 B |", "|---:|---:|---:|---:|"]
        for k in sorted(rounds)[:16]:
            fl, rw = rounds[k]
            L.append(f"| {k} | {fl:,} | {fl / a['mss']:.1f} | {f'{rw:,}' if rw else '-'} |")
        if len(rounds) > 16:
            L.append(f"| … {len(rounds) - 16}개 더 | | | |")
        L.append("")
    return L


def _median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _pearson(xs, ys):
    if len(xs) < 3:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy) if sx and sy else None


def slow_start_rounds(nbytes, mss):
    """혼잡 윈도가 INIT_CWND 에서 RTT 마다 두 배가 될 때 nbytes 를 다 보내는 데 드는 RTT 수.
    k 라운드 뒤까지 보낸 세그먼트 = INIT_CWND · (2^k - 1)."""
    segs, k, total = nbytes / mss, 0, 0
    while total < segs:
        total += INIT_CWND * 2 ** k
        k += 1
    return k


def throughput_section(records, mss):
    L = ["## 파트 B · 네트워크별 처리량", ""]
    if not records:
        return L + ["아직 측정이 없습니다. `python3 task2_measure.py --label \"campus wifi\"`", ""]
    labels = []
    for rec in records:
        if rec["label"] not in labels:
            labels.append(rec["label"])
    groups = {lb: [r for r in records if r["label"] == lb] for lb in labels}
    runs = {lb: [x for r in recs for x in r["runs"]] for lb, recs in groups.items()}

    L += ["| label | 측정 시각 | 네트워크 | 실행 | 중앙값 Mbps | 최소~최대 | 퍼짐 | 핸드셰이크 중앙값 ms | TLS ms | 요청→첫 바이트 ms |",
          "|---|---|---|---:|---:|---|---:|---:|---:|---:|"]
    stats = {}
    for lb in labels:
        rs = runs[lb]
        mbps = [r["mbps"] for r in rs]
        med = statistics.median(mbps)
        net = groups[lb][-1].get("network") or {}
        a = net.get("as") or {}
        where = (f"{net.get('ip', '?')} · AS{a.get('asn', '?')} {a.get('as_name', '').split(' - ')[-1]} · "
                 f"Cloudflare {net.get('colo', '?')} · {net.get('interface') or '?'}") if net else "기록 없음"
        st = {
            "mbps": med, "spread": (max(mbps) - min(mbps)) / med if med else 0,
            "rtt": _median(r["connect_s"] for r in rs),
            "tls": _median(r.get("tls_s") for r in rs),
            "wait": _median(r.get("wait_s") for r in rs),
            "transfer": _median(r.get("transfer_s") for r in rs),
            "bytes": _median(r["bytes"] for r in rs),
            "dns": _median(r["dns_s"] for r in rs),
        }
        stats[lb] = st
        when = ", ".join(g["when"] for g in groups[lb])
        L.append(f"| `{lb}` | {when} | {where} | {len(rs)} | {med:.1f} | {min(mbps):.1f}~{max(mbps):.1f} | "
                 f"{st['spread']:.0%} | {st['rtt'] * 1000:.1f} | "
                 f"{st['tls'] * 1000 if st['tls'] is not None else float('nan'):.1f} | "
                 f"{st['wait'] * 1000 if st['wait'] is not None else float('nan'):.1f} |")
    L.append("")

    # B4: 실행마다
    L += ["### 실행별 (B2 · B4)", "",
          "| label | # | Mbps | DNS ms | 핸드셰이크 ms | TLS ms | 요청→첫 바이트 ms | 전송 구간 ms | 전체 ms | 로컬 포트 | 서버 |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for lb in labels:
        for k, r in enumerate(runs[lb], 1):
            def ms(key):
                return f"{r[key] * 1000:.1f}" if r.get(key) is not None else "-"
            L.append(f"| `{lb}` | {k} | {r['mbps']:.1f} | {ms('dns_s')} | {ms('connect_s')} | {ms('tls_s')} | "
                     f"{ms('wait_s')} | {ms('transfer_s')} | {ms('total_s')} | "
                     f"{(r.get('local') or ['', '-'])[1]} | {(r.get('remote') or ['-'])[0]} |")
    L.append("")
    L += ["퍼짐이 어디서 오는가. 구간마다 다섯 번의 최댓값 - 최솟값 (ms)이고, 괄호는 전체 시간의 범위에 "
          "대한 비율입니다. 구간들의 범위는 서로 더해지지 않습니다 (가장 느린 구간이 실행마다 다르므로).", "",
          "| label | 전체 범위 | DNS | 핸드셰이크 | TLS | 요청→첫 바이트 | 전송 구간 | 핸드셰이크와 Mbps 의 상관 r |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for lb in labels:
        rs = runs[lb]
        rng = {}
        for key in ("total_s", "dns_s", "connect_s", "tls_s", "wait_s", "transfer_s"):
            vals = [r[key] for r in rs if r.get(key) is not None]
            rng[key] = (max(vals) - min(vals)) * 1000 if vals else None
        r = _pearson([x["connect_s"] for x in rs], [x["mbps"] for x in rs])
        tot = rng["total_s"] or 1

        def cell(key):
            v = rng[key]
            return "-" if v is None else f"{v:.1f} ({v / tot:.0%})"
        L.append(f"| `{lb}` | {rng['total_s']:.1f} | {cell('dns_s')} | {cell('connect_s')} | {cell('tls_s')} | "
                 f"{cell('wait_s')} | {cell('transfer_s')} | {'-' if r is None else f'{r:+.2f}'} |")
    L.append("")

    # B5: 핸드셰이크(=RTT)와 처리량
    rounds = slow_start_rounds(statistics.median(st["bytes"] for st in stats.values()), mss)
    L += ["### 핸드셰이크 시간과 처리량 (B5)", "",
          f"핸드셰이크 시간은 RTT 한 번입니다. 받은 바이트가 같아도 RTT 가 길면 두 곳에서 손해를 봅니다. "
          f"(1) 데이터가 오기 전 연결 준비: TCP 핸드셰이크 + TLS + 요청이 각각 한 RTT 씩입니다. "
          f"(2) 전송 구간: 혼잡 윈도는 슬로 스타트에서 RTT 마다 두 배가 되고, 그동안 처리량은 "
          f"대략 윈도 / RTT 입니다. 초기 윈도 {INIT_CWND} 세그먼트, MSS {mss} B 라면 "
          f"{statistics.median(st['bytes'] for st in stats.values()) / 1e6:.0f} MB 를 슬로 스타트만으로 "
          f"보내는 데 {rounds} RTT 가 듭니다. 아래의 \"RTT 만으로 정해지는 상한\"은 대역폭이 무한해도 "
          f"이 두 가지 때문에 넘을 수 없는 처리량입니다.", "",
          "| label | RTT ms | 연결 준비 (ms · RTT 몇 번) | 전송 구간 ms (RTT 몇 번) | 평균 비행량 = 전송 구간 처리량 × RTT | "
          f"슬로 스타트 {rounds} RTT 의 시간 | RTT 만으로 정해지는 상한 Mbps | 측정 중앙값 Mbps |",
          "|---|---:|---|---|---:|---:|---:|---:|"]
    for lb in labels:
        st = stats[lb]
        rtt = st["rtt"]
        setup = (st["rtt"] or 0) + (st["tls"] or 0) + (st["wait"] or 0)
        rate = st["bytes"] * 8 / st["transfer"] if st["transfer"] else 0
        flight = rate / 8 * rtt
        ss = rounds * rtt
        ceiling = st["bytes"] * 8 / (st["dns"] + setup + ss) / 1e6 if rtt else 0
        L.append(f"| `{lb}` | {rtt * 1000:.1f} | {setup * 1000:.0f} · {setup / rtt:.1f} | "
                 f"{st['transfer'] * 1000:.0f} ({st['transfer'] / rtt:.1f}) | "
                 f"{flight / 1000:,.0f} KB ({flight / mss:.0f} 세그먼트) | {ss * 1000:.0f} ms | "
                 f"{ceiling:,.0f} | {st['mbps']:.1f} |")
    L.append("")
    if len(labels) >= 2:
        base = labels[0]
        for lb in labels[1:]:
            a, b = stats[base], stats[lb]
            L.append(f"- `{lb}` 대 `{base}`: RTT ×{b['rtt'] / a['rtt']:.2f}, 처리량 ×{b['mbps'] / a['mbps']:.2f}, "
                     f"전송 구간 시간 ×{b['transfer'] / a['transfer']:.2f}")
        L.append("")
    else:
        L += [f"B1 은 아직입니다. 지금은 `{labels[0]}` 한 곳뿐입니다. 휴대폰 테더링에 붙은 뒤 "
              "`python3 task2_measure.py --label tethering` 을 돌리면 이 표에 두 번째 행이 붙고, "
              "두 네트워크의 RTT 비와 처리량 비가 여기에 나옵니다. 네트워크가 정말 하나뿐이라면 "
              "매우 다른 시간대에 같은 곳에서 다시 재고 label 을 시간대로 붙이세요 (경로 B).", ""]
    return L


def report(capture):
    records = _load(THROUGHPUT, [])
    os.makedirs(OUT, exist_ok=True)
    mss = MSS
    if os.path.exists(capture):
        conns = [a for a in (analyse(c) for c in connections(capture)) if a]
        if conns:
            mss = max(conns, key=lambda a: a["bytes"])["mss"]
    L = ["# Task 2 · 내 링크를 두 번 재기", "",
         f"`python3 task2_measure.py --report` 로 생성 ({time.strftime('%Y-%m-%d %H:%M')}). "
         f"원시 데이터 `out/throughput.json`, 캡처 `{os.path.relpath(capture, HERE)}`.", ""]
    L += capture_section(capture, records)
    L += throughput_section(records, mss)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"  -> {os.path.relpath(REPORT, HERE)}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--label",
                   help='어디서 쟀는지, 예: "campus wifi" 또는 "tethering"')
    p.add_argument("--repeats", type=int, default=REPEATS)
    p.add_argument("--report", action="store_true",
                   help="out/throughput.json 과 캡처를 읽어 out/report.md 작성")
    p.add_argument("--capture", default=CAPTURE,
                   help="파트 A 에 쓸 캡처 (기본 out/tcp.pcapng, 경로 B 면 공식 trace)")
    a = p.parse_args()
    if a.report:
        report(os.path.abspath(a.capture))
    elif a.label:
        measure(a.label, a.repeats)
    else:
        p.error("--label 이나 --report 중 하나가 필요합니다")


if __name__ == "__main__":
    main()
