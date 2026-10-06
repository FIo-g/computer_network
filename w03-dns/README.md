# Week 3 Lab · DNS Hierarchy and CDNs

**Theory** — 3-1 DNS hierarchy (§2.4.2) · 3-2 DNS records (§2.4.3) · 3-2 Video streaming and CDNs (§2.5)
**Textbook lab (path B)** — Wireshark Lab: DNS
**Submit to** — `w03-dns/out/`

You type a name and an address comes back. Three questions this week:
**who actually answered, whose machine is it, and how long may we keep the answer?**

```bash
cd w03-dns
```

| | Task | You build |
|---|---|---|
| 1 | Resolve a name yourself | an iterative resolver — no `dig +trace` |
| 2 | Does DNS really steer you? | a measurement over 12 sites and three resolvers |
| 3 | Beat the baseline cache | a correct cache, and an argument about its floor |

---

## Task 1 · Build Your Own Iterative Resolver

`task1_resolve.py`

`dig +trace` walks root → TLD → authoritative for you. Do that walk yourself:
start at a root server, read the delegation, ask the next server, repeat until
someone answers authoritatively.

You may shell out to `dig` for transport (`+norecurse` is the flag that stops a
server from doing the work for you) or use `dnspython`. What matters is that
**you** follow the delegations.

What will actually get in your way:

- a delegation gives you `NS` **names**, sometimes with glue `A` records and sometimes without.
  No glue means you have to resolve *that* name first — another walk. Decide what you do there
- servers that do not answer. Try the next one
- `CNAME`s: the answer may be for a different name than the one you asked, and you start again
- loops. Cap your depth

**Pass condition**

```bash
python3 task1_resolve.py --verify
```

Five names, resolved by you and by `dig`, must agree. CDN names can legitimately
return a different address per query — if that is what happened, say so in `observation.md`.

---

## Task 2 · Does DNS Actually Steer You?

`task2_steering.py`

The lecture claims two things. One is easy to show and one is not:

- **(a)** most large sites are served by a CDN, reached through a `CNAME` chain
- **(b)** DNS steers each user to a *nearby* replica

Build the measurement over the 12 sites in `SITES` and the three resolvers in `RESOLVERS`.

**The hard part is deciding what counts as "served by a third party."**
There is no single right rule.

| Site | What it does |
|---|---|
| `www.microsoft.com` | ends at `akamaiedge.net` — clearly a third party |
| `www.netflix.com` | stops inside `netflix.com` — runs its **own** CDN |
| `www.korea.ac.kr` | no `CNAME` at all, and no CDN either |
| some sites | sit behind a CDN with no `CNAME` at all (anycast) |

A rule that just compares the last two labels **will be wrong on at least one site
in the list.** Find which one, and say so.

**Pass condition** — `out/report.md` contains:

- the table: site · chain length · final zone · third party? · your rule's verdict
- the steering number: "X of N sites answered differently to a different resolver"
- at least one site your rule got wrong, and why

---

## Task 3 · Beat the Baseline Cache

`task3_cache.py` · harness `bench.py` — **do not edit the harness**

`BaselineCache` works. It is also bad in more than one way, and one of its problems
is worse than being slow.

```bash
python3 bench.py            # baseline only
python3 bench.py --yours    # side by side, once you have written YourCache
```

The harness replays 1,000 queries over a simulated hour against a simulated upstream
(fixed 20 ms round trip, a fixture of names with realistic TTLs from 20 s to a day),
so everyone's numbers are comparable and slow Wi-Fi does not decide your grade.

**Where the baseline lands:**

```
  baseline   upstream   325   hit rate  67.5%   stale  266   sim time    6.5s
```

Read that line carefully. The hit rate looks respectable. **266 of 1,000 answers were
expired** — the cache handed out records whose TTL had already run out. A cache that keeps
everything forever would score a beautiful hit rate and be completely wrong.

| | Requirement |
|---|---|
| pass | zero stale answers |
| good | zero stale, and no more upstream queries than the baseline |
| **strong** | the above, plus: **how few upstream queries could any correct cache make on this workload, and why can you not go below that?** |

The last row is the real question, and it is worth reading before you start optimising —
it tells you where to stop. A correct cache does not get to be clever about this.

---

## Path (B) · When Measurement Is Blocked

Some campus and corporate networks block `dig +trace`, or outbound port 53 to public resolvers.

- **Task 1** — use the official **Wireshark Lab: DNS** trace in `traces/` and reconstruct the
  delegation chain by reading the captured queries instead of issuing your own
- **Task 2** — you need at least two resolvers for the steering number. If only one is
  reachable, measure from two different networks instead (campus and phone tethering), and say so
- **Task 3** — unaffected. It is fully simulated
- Source and attribution: `traces/README.md`

---

## What to Submit

| File | What |
|---|---|
| `task1_resolve.py` | your resolver |
| `task2_steering.py` · `out/report.md` | your measurement and its table |
| `task3_cache.py` | your cache |
| `out/bench.txt` | output of `python3 bench.py --yours` |
| `out/observation.md` | 2–3 lines per task, see below |

```bash
python3 ../check.py w03
```

This checks **format only**. It does not grade your answers; it tells you what is missing.

## What to Write in `observation.md`

- **Task 1** — why the root server did not just hand you the address. And: what did you do
  when a delegation arrived without glue?
- **Task 2** — your third-party rule, the site it got wrong, and the steering number
- **Task 3** — the floor. How few upstream queries could a correct cache make here, and why

---

## 한국어 번역본 (Korean Translation)

# 3주차 실습 · DNS 계층 구조와 CDN

**이론** — 3-1 DNS 계층 구조 (§2.4.2) · 3-2 DNS 레코드 (§2.4.3) · 3-2 비디오 스트리밍과 CDN (§2.5)
**교재 실습 (경로 B)** — Wireshark Lab: DNS
**제출 위치** — `w03-dns/out/`

이름을 입력하면 주소가 돌아옵니다. 이번 주에는 세 가지 질문을 다룹니다:
**실제로 누가 응답했는지, 그 기계가 누구의 것인지, 그리고 그 답변을 얼마나 오래 보관해도 되는지?**

```bash
cd w03-dns
```

| | 과제 | 만들 것 |
|---|---|---|
| 1 | 이름을 직접 해석하기 | 반복적 리졸버 만들기 — `dig +trace` 사용 금지 |
| 2 | DNS가 정말로 트래픽을 유도하는가? | 12개 사이트와 3개 리졸버에 대한 측정 |
| 3 | 기준 캐시 뛰어넘기 | 올바른 캐시, 그리고 그 한계에 대한 논증 |

---

## 과제 1 · 직접 반복적 리졸버 만들기

`task1_resolve.py`

`dig +trace`는 루트 → TLD → 권한 서버 순서로 대신 탐색해 줍니다. 이 과정을 직접 수행하세요:
루트 서버에서 시작해 위임(delegation)을 읽고, 다음 서버에 질의하고, 권한 있는 응답을
받을 때까지 반복합니다.

전송 수단으로 `dig`를 사용해도 됩니다 (`+norecurse`는 서버가 대신 작업을 수행하지
못하도록 막는 플래그입니다). 또는 `dnspython`을 사용해도 됩니다. 중요한 것은 **여러분이**
위임을 직접 따라가는 것입니다.

실제로 발목을 잡을 것들:

- 위임은 `NS` **이름**을 알려주며, 글루(glue) `A` 레코드가 함께 올 때도 있고 없을 때도 있습니다.
  글루가 없으면 그 이름을 먼저 해석해야 합니다 — 또 다른 탐색이 필요합니다. 이 경우 어떻게 할지 정하세요
- 응답하지 않는 서버들. 다음 서버를 시도하세요
- `CNAME`: 응답이 질의한 이름과 다른 이름에 대한 것일 수 있으며, 이 경우 처음부터 다시 시작합니다
- 루프. 깊이에 상한을 두세요

**통과 조건**

```bash
python3 task1_resolve.py --verify
```

5개의 이름에 대해 여러분의 결과와 `dig`의 결과가 일치해야 합니다. CDN 이름은 질의마다
정당하게 다른 주소를 반환할 수 있습니다 — 그런 경우라면 `observation.md`에 그렇게 명시하세요.

---

## 과제 2 · DNS가 실제로 트래픽을 유도하는가?

`task2_steering.py`

수업에서는 두 가지를 주장합니다. 하나는 보이기 쉽고, 다른 하나는 그렇지 않습니다:

- **(a)** 대부분의 대형 사이트는 `CNAME` 체인을 거쳐 CDN으로 서비스된다
- **(b)** DNS는 각 사용자를 *가까운* 복제 서버로 유도한다

`SITES`의 12개 사이트와 `RESOLVERS`의 3개 리졸버에 대해 측정을 수행하세요.

**어려운 부분은 무엇이 "제3자에 의해 서비스됨"에 해당하는지 정하는 것입니다.**
정답인 규칙은 하나만 있지 않습니다.

| 사이트 | 특징 |
|---|---|
| `www.microsoft.com` | `akamaiedge.net`에서 끝남 — 명확히 제3자 |
| `www.netflix.com` | `netflix.com` 내부에서 끝남 — **자체** CDN 운영 |
| `www.korea.ac.kr` | `CNAME`도 없고, CDN도 없음 |
| 일부 사이트 | `CNAME` 없이 CDN 뒤에 있음 (애니캐스트) |

마지막 두 레이블만 비교하는 규칙은 목록 중 **적어도 하나의 사이트에서는 반드시 틀립니다.**
어느 사이트인지 찾고, 그렇게 말하세요.

**통과 조건** — `out/report.md`에 다음이 포함되어야 합니다:

- 표: 사이트 · 체인 길이 · 최종 존 · 제3자 여부 · 여러분 규칙의 판정
- 스티어링 수치: "N개 중 X개 사이트가 리졸버에 따라 다르게 응답함"
- 여러분의 규칙이 틀린 사이트가 최소 하나, 그리고 그 이유

---

## 과제 3 · 기준 캐시 뛰어넘기

`task3_cache.py` · 하네스 `bench.py` — **하네스는 수정하지 마세요**

`BaselineCache`는 동작합니다. 하지만 여러 면에서 나쁘며, 그중 한 문제는
느리다는 것보다 더 심각합니다.

```bash
python3 bench.py            # 기준선만 실행
python3 bench.py --yours    # YourCache를 작성한 뒤 나란히 비교
```

하네스는 시뮬레이션된 업스트림(고정 왕복 시간 20ms, 20초부터 하루까지의 현실적인 TTL을 가진
이름들의 픽스처)에 대해 시뮬레이션된 1시간 동안 1,000개의 쿼리를 재생합니다.
따라서 모두의 수치를 비교할 수 있고, 느린 와이파이가 성적에 영향을 주지 않습니다.

**기준선의 위치:**

```
  baseline   upstream   325   hit rate  67.5%   stale  266   sim time    6.5s
```

이 줄을 주의 깊게 읽으세요. 적중률은 그럴듯해 보입니다. **1,000개의 답변 중 266개가
만료된 것**이었습니다 — 캐시가 TTL이 이미 지난 레코드를 내준 것입니다. 모든 것을 영원히
보관하는 캐시는 아름다운 적중률을 기록하겠지만 완전히 틀린 것입니다.

| | 요구 사항 |
|---|---|
| 통과 | 만료된(stale) 답변 0개 |
| 양호 | 만료 답변 0개, 그리고 기준선보다 많지 않은 업스트림 쿼리 수 |
| **우수** | 위 조건을 모두 만족하고, 추가로: **이 워크로드에서 올바른 캐시가 만들 수 있는 최소 업스트림 쿼리 수는 몇 개이며, 왜 그 이하로 내려갈 수 없는가?** |

마지막 행이 진짜 질문이며, 최적화를 시작하기 전에 읽어볼 가치가 있습니다 —
어디서 멈춰야 하는지 알려줍니다. 올바른 캐시라면 이 점에 대해 영리한 수를 쓸 수 없습니다.

---

## 경로 (B) · 측정이 차단된 경우

일부 캠퍼스 및 기업 네트워크에서는 `dig +trace`나 공용 리졸버로의 아웃바운드 53번 포트를 차단합니다.

- **과제 1** — `traces/`에 있는 공식 **Wireshark Lab: DNS** 트레이스를 사용하고, 직접 질의하는 대신
  캡처된 쿼리를 읽어 위임 체인을 재구성하세요
- **과제 2** — 스티어링 수치를 위해 최소 두 개의 리졸버가 필요합니다. 하나만 도달 가능하다면,
  대신 두 개의 서로 다른 네트워크에서 측정하세요 (캠퍼스와 휴대폰 테더링), 그리고 그렇게 명시하세요
- **과제 3** — 영향 없음. 완전 시뮬레이션입니다
- 출처 및 저작권 표시: `traces/README.md`

---

## 제출할 것

| 파일 | 내용 |
|---|---|
| `task1_resolve.py` | 여러분의 리졸버 |
| `task2_steering.py` · `out/report.md` | 여러분의 측정과 그 표 |
| `task3_cache.py` | 여러분의 캐시 |
| `out/bench.txt` | `python3 bench.py --yours`의 출력 |
| `out/observation.md` | 과제별 2–3줄, 아래 참조 |

```bash
python3 ../check.py w03
```

이것은 **형식만** 검사합니다. 답을 채점하지 않으며, 무엇이 빠졌는지 알려줍니다.

## `observation.md`에 쓸 것

- **과제 1** — 루트 서버가 왜 주소를 바로 주지 않았는지. 그리고: 글루 없이 위임이 도착했을 때
  어떻게 했는지?
- **과제 2** — 여러분의 제3자 판정 규칙, 그 규칙이 틀린 사이트, 그리고 스티어링 수치
- **과제 3** — 하한. 올바른 캐시가 여기서 만들 수 있는 최소 업스트림 쿼리 수는 몇 개이며, 왜 그런지
