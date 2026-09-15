#!/usr/bin/env python3
"""Week 3 · Task 2 — Does DNS actually steer you? Measure it.

Textbook §2.4.3 (records) and §2.5 (CDNs).

The lecture claims two things:

    (a) most large sites are served by a CDN, reached through a CNAME chain
    (b) DNS steers each user to a *nearby* replica

Both are testable from your laptop, and one of them is harder to prove than
the slide makes it look. Your job is to produce the evidence and a number.

    python3 task2_steering.py --collect        # gather the raw data
    python3 task2_steering.py --report         # your analysis

What you have to build
----------------------
1.  For each hostname in SITES, follow the CNAME chain to its end and record
    every hop. `--collect` should leave the raw data in out/chains.json.

2.  Decide, for each site, whether it is served by a **third party**.
    This is the hard part and there is no single right answer:

      - `www.microsoft.com` ends at `akamaiedge.net`     - clearly third party
      - `www.netflix.com`   stops inside `netflix.com`   - own CDN, not third party
      - some sites have no CNAME at all and still sit behind a CDN (anycast)
      - `foo.cloudfront.net` and `foo.s3.amazonaws.com` are both Amazon,
        but they are not the same service

    Write down the rule you used and **defend it in observation.md**. A rule
    that just compares the last two labels will be wrong on at least one of
    the sites below; find which, and say so.

3.  Ask **two different resolvers** for the same name and compare the
    addresses you get back. If DNS really steers by location, a CDN-hosted
    name should answer differently to resolvers sitting in different places.

        RESOLVERS below has your system resolver and two public ones.

    Report: of N CDN-hosted sites, how many returned a different address set
    from a different resolver? Claim (b) predicts most of them. Check it.

Pass condition
--------------
There is no fixed answer. You pass by producing, in out/report.md:

  - the table: site | chain length | final zone | third party? | your rule's verdict
  - the steering number: "X of N sites answered differently to a different resolver"
  - at least one site where your classification rule was wrong, and why
"""
import argparse
import ipaddress
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

SITES = [
    "www.microsoft.com",     # Akamai, multi-hop
    "www.netflix.com",       # own CDN
    "www.adobe.com",
    "www.cnn.com",
    "www.apple.com",
    "www.korea.ac.kr",       # no CDN at all
    "www.stanford.edu",
    "www.bbc.co.uk",
    "www.spotify.com",
    "www.github.com",
    "www.wikipedia.org",
    "www.nytimes.com",
]

RESOLVERS = {
    "system": None,          # whatever is in your resolv.conf
    "google": "8.8.8.8",
    "quad9":  "9.9.9.9",
}


class LookupFailure(RuntimeError):
    """측정 질의나 저장 데이터가 완전하지 않을 때 사용한다."""


def normalize_name(name):
    """서로 다른 dig 표기를 같은 DNS 이름으로 비교한다."""
    normalized = name.strip().rstrip(".").lower()
    if not normalized:
        raise LookupFailure("DNS name must not be empty")
    return normalized


def dig(name, rtype="A", server=None):
    """지정한 리졸버에 질의하고 실패를 빈 정상 응답과 구분한다."""
    args = ["dig"]
    if server:
        args.append(f"@{server}")
    args.extend(["+short", "+time=2", "+tries=1", name, rtype])
    try:
        completed = subprocess.run(
            args, capture_output=True, text=True, timeout=4, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise LookupFailure(f"dig failed for {name} {rtype}: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"exit {completed.returncode}"
        raise LookupFailure(f"dig failed for {name} {rtype}: {detail}")
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def follow_cname_chain(name, lookup=dig, max_edges=16):
    """CNAME을 한 간선씩 따라가며 원본을 포함한 전체 경로를 반환한다."""
    chain = [normalize_name(name)]
    for _edge in range(max_edges + 1):
        values = lookup(chain[-1], "CNAME", None)
        targets = []
        for value in values:
            target = normalize_name(value)
            if target not in targets:
                targets.append(target)
        if not targets:
            return chain
        if len(targets) != 1:
            raise LookupFailure(f"multiple CNAME targets for {chain[-1]}")
        target = targets[0]
        if target in chain:
            raise LookupFailure(f"CNAME loop at {target}")
        if len(chain) - 1 == max_edges:
            raise LookupFailure("CNAME depth limit exceeded")
        chain.append(target)
    raise LookupFailure("CNAME depth limit exceeded")


def authoritative_zone(name, lookup=dig):
    """가장 구체적인 SOA suffix를 authoritative zone으로 사용한다."""
    labels = normalize_name(name).split(".")
    for index in range(len(labels) - 1):
        candidate = ".".join(labels[index:])
        values = lookup(candidate, "SOA", None)
        if any(len(value.split()) >= 7 for value in values):
            return candidate
    raise LookupFailure(f"no SOA zone found for {name}")


def ipv4_answers(values):
    """dig 출력에서 중복 없는 IPv4 주소 집합만 정렬한다."""
    addresses = set()
    for value in values:
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue
        if address.version == 4:
            addresses.add(str(address))
    return sorted(addresses, key=ipaddress.ip_address)


def _write_json(path, data):
    """기존 측정 파일이 중간 상태가 되지 않도록 원자적으로 교체한다."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def collect(network="network-1", replace=False, out_path=None, lookup=dig):
    """현재 네트워크의 CNAME, zone, 리졸버별 주소를 기존 자료에 합친다."""
    network = network.strip()
    if not network:
        raise LookupFailure("network label must not be empty")
    path = out_path or os.path.join(OUT, "chains.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if set(data) != set(SITES):
            raise LookupFailure("existing chains.json does not contain exactly SITES")
    else:
        data = {site: {"measurements": {}} for site in SITES}

    if not replace and any(
        network in data[site].get("measurements", {}) for site in SITES
    ):
        raise LookupFailure(f"network label already exists: {network}")

    for site in SITES:
        errors = {}
        try:
            chain = follow_cname_chain(site, lookup)
        except LookupFailure as error:
            chain = [normalize_name(site)]
            errors["chain"] = str(error)

        try:
            original_zone = authoritative_zone(site, lookup)
        except LookupFailure as error:
            original_zone = ""
            errors["original_zone"] = str(error)

        try:
            final_zone = authoritative_zone(chain[-1], lookup)
        except LookupFailure as error:
            final_zone = ""
            errors["final_zone"] = str(error)

        resolver_addresses = {}
        for resolver_name, server in RESOLVERS.items():
            try:
                resolver_addresses[resolver_name] = ipv4_answers(
                    lookup(site, "A", server)
                )
            except LookupFailure as error:
                resolver_addresses[resolver_name] = []
                errors[f"resolver:{resolver_name}"] = str(error)

        data[site].setdefault("measurements", {})[network] = {
            "chain": chain,
            "original_zone": original_zone,
            "final_zone": final_zone,
            "resolver_addresses": resolver_addresses,
            "errors": errors,
        }

    _write_json(path, data)
    return data


def report():
    """Read out/chains.json and produce out/report.md.

    You write this too - including the classification rule that decides
    whether a site is on a third-party CDN.
    """
    raise NotImplementedError("build the report")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--network", default="network-1")
    parser.add_argument("--replace", action="store_true")
    arguments = parser.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if arguments.replace and not arguments.collect:
        parser.error("--replace requires --collect")
    if arguments.collect and arguments.report:
        parser.error("choose exactly one of --collect or --report")
    if arguments.collect:
        collect(arguments.network, arguments.replace)
    elif arguments.report:
        report()
    else:
        parser.print_help()
