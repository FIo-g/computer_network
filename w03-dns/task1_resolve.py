#!/usr/bin/env python3
"""Week 3 · Task 1 — Build your own iterative resolver.

Textbook §2.4.2 - §2.4.3.

`dig +trace` walks root -> TLD -> authoritative for you. In this task you do
that walk yourself: start at a root server, read the delegation it returns,
ask the next server, and keep going until somebody answers authoritatively.

You may shell out to `dig` for the transport, or use a DNS library
(`dnspython` is in the container). Either is fine - what matters is that
*you* follow the delegations rather than letting a tool do it.

    python3 task1_resolve.py www.korea.ac.kr
    python3 task1_resolve.py --verify        # check yourself against dig

Pass condition
--------------
`--verify` resolves five names with your resolver and with `dig`, and the
addresses must agree. A name behind a CDN may legitimately return a different
address each time; the harness compares the *set of authoritative nameservers*
you ended at for those, not the address.
"""
import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Tuple


class ResolutionError(RuntimeError):
    """반복 질의가 안전하게 답에 도달하지 못했음을 나타낸다."""


@dataclass(frozen=True)
class DNSRecord:
    owner: str
    rtype: str
    value: str


@dataclass(frozen=True)
class DNSReply:
    status: str
    authoritative: bool
    answers: Tuple[DNSRecord, ...]
    authority: Tuple[DNSRecord, ...]
    additional: Tuple[DNSRecord, ...]


def normalize_name(name):
    """DNS 이름 비교를 위해 대소문자와 마지막 점을 정규화한다."""
    normalized = name.strip().rstrip(".").lower()
    if not normalized:
        raise ResolutionError("DNS name must not be empty")
    return normalized


def parse_dig_output(text):
    """dig의 섹션별 출력을 반복 질의에 필요한 레코드로 바꾼다."""
    status_match = re.search(r"status:\s*([A-Z]+)", text)
    if status_match is None:
        raise ResolutionError("dig response has no DNS status")

    flags_match = re.search(r";; flags:\s*([^;]*);", text)
    flags = flags_match.group(1).split() if flags_match else []
    sections = {"answer": [], "authority": [], "additional": []}
    section = None
    headers = {
        ";; ANSWER SECTION:": "answer",
        ";; AUTHORITY SECTION:": "authority",
        ";; ADDITIONAL SECTION:": "additional",
    }

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line in headers:
            section = headers[line]
            continue
        if not line or line.startswith(";;") or section is None:
            continue
        fields = line.split(maxsplit=4)
        if len(fields) != 5:
            raise ResolutionError(f"malformed resource record: {line}")
        owner, _ttl, dns_class, rtype, value = fields
        if dns_class != "IN":
            continue
        rtype = rtype.upper()
        if rtype not in {"A", "CNAME", "NS"}:
            continue
        if rtype in {"CNAME", "NS"}:
            value = normalize_name(value)
        sections[section].append(DNSRecord(normalize_name(owner), rtype, value))

    return DNSReply(
        status=status_match.group(1),
        authoritative="aa" in flags,
        answers=tuple(sections["answer"]),
        authority=tuple(sections["authority"]),
        additional=tuple(sections["additional"]),
    )


def dig_query(server, name):
    """한 DNS 서버에 재귀를 금지한 A 질의를 보내고 구조화된 응답을 돌려준다."""
    args = [
        "dig",
        f"@{server}",
        normalize_name(name),
        "A",
        "+norecurse",
        "+time=2",
        "+tries=1",
        "+noall",
        "+comments",
        "+answer",
        "+authority",
        "+additional",
    ]
    try:
        completed = subprocess.run(
            args, capture_output=True, text=True, timeout=4, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    try:
        return parse_dig_output(completed.stdout)
    except ResolutionError:
        return None

# Root servers. Everything starts here; there is no earlier step.
ROOT_SERVERS = [
    "198.41.0.4",       # a.root-servers.net
    "199.9.14.201",     # b.root-servers.net
    "192.33.4.12",      # c.root-servers.net
]

# (name, kind).  "stable" names must match dig exactly.  "cdn" names are served
# from many replicas and may legitimately give you a different address than dig
# got a second earlier - for those we only require that you reached an answer.
VERIFY_NAMES = [
    ("www.korea.ac.kr", "stable"),
    ("dns.google", "stable"),
    ("en.wikipedia.org", "stable"),
    ("www.stanford.edu", "stable"),
    ("www.microsoft.com", "cdn"),
]


class Resolver:
    """Your iterative resolver.

    The whole point is that you never ask a server to recurse for you.
    You ask one server, it says "not mine, ask over there", and you go there.

    Suggested shape - but it is yours to design:

        resolve(name) -> (address, path)
            address : the A record you ended up with, as a string
            path    : the servers you asked, in order, so you can show your work

    Things you will hit, in roughly this order:

    1.  A delegation gives you NS *names*, sometimes with glue A records and
        sometimes without. No glue means you have to resolve that nameserver's
        name first - which is another walk. Decide what you do there.
    2.  A server may not answer. Try the next one rather than giving up.
    3.  CNAMEs. The answer you get back may be a different name than the one
        you asked for, and you have to start again with that name.
    4.  Loops. Cap your depth.

    If you shell out to dig, the flag you want is `+norecurse`, so that the
    server you ask replies with a delegation instead of doing the work:

        dig @198.41.0.4 www.korea.ac.kr +norecurse
    """

    def resolve(self, name):
        raise NotImplementedError(
            "Implement the iterative walk: root -> TLD -> authoritative")


# ------------------------------------------------------------------- harness
def dig_answer(name):
    """What the system resolver says, for comparison."""
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
