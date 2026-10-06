# Task 3 · Beat the Baseline Cache

**Files** — `task3_cache.py` · harness `bench.py` (**do not edit the harness**)
**Theory** — §2.4.2 caching, §2.4.3 TTL
**Kind** — improvement · fully simulated, so it works on any network

---

## What you are given

`BaselineCache` in `task3_cache.py` works. Somebody wrote it in a hurry. It is bad in
more than one way, and **one of its problems is worse than being slow**.

You are not told where the bugs are. Finding them is half the task.

```bash
python3 bench.py            # baseline only
python3 bench.py --yours    # side by side, once YourCache exists
```

## How you are measured

The harness replays **1,000 queries over a simulated hour** against a simulated upstream:
a fixed 20 ms round trip and a fixture of names with realistic TTLs, from 20 seconds
(a CDN name) to a day (a root server). Everyone runs the same workload, so slow Wi-Fi
does not decide your grade.

Four numbers come back:

| | |
|---|---|
| `upstream` | round trips actually made — lower is better |
| `hit rate` | served without going upstream |
| `stale` | answers served **after their TTL had expired** — must be 0 |
| `sim time` | what the workload would have cost in the real world |

**Where the baseline lands:**

```
  baseline   upstream   325   hit rate  67.5%   stale  266   sim time    6.5s
```

Read that line twice. A 67.5% hit rate looks respectable. **266 of 1,000 answers were
expired records.** A cache that keeps everything forever would post a beautiful hit rate
and be completely wrong — so speed alone is not the score.

## Requirements

| # | Requirement |
|---|---|
| R1 | `YourCache` exposes the same interface: `__init__(upstream)`, `lookup(name, now)`, `stats()` |
| R2 | `bench.py` is unmodified. If you need to change the harness to win, you are not winning |
| R3 | Zero stale answers |
| R4 | No more upstream queries than the baseline |
| R5 | In `observation.md`: the **floor** — how few upstream queries could *any* correct cache make on this workload, and why you cannot go below it |

## Grading

| | Requirement |
|---|---|
| pass | R1–R3 |
| good | R1–R4 |
| **strong** | R1–R5 |

R5 is the real question, and it is worth working out **before** you start optimising,
because it tells you where to stop. There is a number below which no correct cache can go,
and it is not set by how clever your data structure is.

If you find yourself trying to be clever about it, re-read what the TTL is for.

## What to write in `observation.md`

- The two things wrong with the baseline. Name them separately — one is a performance
  problem and one is a correctness problem, and they have the same root cause
- Your floor number from R5, with the reasoning
- Which record in the fixture the baseline handles worst, and why that one

---

## 한국어 번역본 (Korean Translation)

# 과제 3 · 기준 캐시 뛰어넘기

**파일** — `task3_cache.py` · 하네스 `bench.py` (**하네스는 수정하지 마세요**)
**이론** — §2.4.2 캐싱, §2.4.3 TTL
**종류** — 개선 · 완전 시뮬레이션이므로 어떤 네트워크에서도 동작

---

## 주어진 것

`task3_cache.py`의 `BaselineCache`는 동작합니다. 누군가 급하게 작성했습니다. 여러 면에서
나쁘며, **그중 한 문제는 느리다는 것보다 더 심각합니다.**

버그가 어디에 있는지 알려주지 않습니다. 찾는 것이 과제의 절반입니다.

```bash
python3 bench.py            # 기준선만 실행
python3 bench.py --yours    # YourCache가 완성되면 나란히 비교
```

## 측정 방식

하네스는 시뮬레이션된 업스트림에 대해 **시뮬레이션된 1시간 동안 1,000개의 쿼리**를 재생합니다:
고정 왕복 시간 20ms와 20초(CDN 이름)부터 하루(루트 서버)까지의 현실적인 TTL을 가진
이름들의 픽스처. 모두 같은 워크로드를 실행하므로 느린 와이파이가 성적에 영향을 주지 않습니다.

돌아오는 숫자는 네 가지입니다:

| | |
|---|---|
| `upstream` | 실제로 수행한 왕복 횟수 — 낮을수록 좋음 |
| `hit rate` | 업스트림에 가지 않고 서비스한 비율 |
| `stale` | TTL이 만료된 **이후에** 서비스한 답변 — 반드시 0이어야 함 |
| `sim time` | 이 워크로드가 실제 세계에서 들였을 비용 |

**기준선의 위치:**

```
  baseline   upstream   325   hit rate  67.5%   stale  266   sim time    6.5s
```

이 줄을 두 번 읽으세요. 67.5% 적중률은 그럴듯해 보입니다. **1,000개의 답변 중 266개가
만료된 레코드였습니다.** 모든 것을 영원히 보관하는 캐시는 아름다운 적중률을 기록하겠지만
완전히 틀린 것입니다 — 따라서 속도만으로는 점수가 되지 않습니다.

## 요구 사항

| # | 요구 사항 |
|---|---|
| R1 | `YourCache`는 같은 인터페이스를 제공: `__init__(upstream)`, `lookup(name, now)`, `stats()` |
| R2 | `bench.py`는 수정하지 않음. 하네스를 고쳐야 이긴다면 이긴 것이 아님 |
| R3 | 만료된 답변 0개 |
| R4 | 기준선과 같거나 더 적은 업스트림 쿼리 수 |
| R5 | `observation.md`에 **하한** — 이 워크로드에서 *올바른* 캐시가 만들 수 있는 최소 업스트림 쿼리 수는 몇 개이며, 왜 그 이하로 내려갈 수 없는지 |

## 채점

| | 요구 사항 |
|---|---|
| 통과 | R1–R3 |
| 양호 | R1–R4 |
| **우수** | R1–R5 |

R5가 진짜 질문이며, 최적화를 시작하기 **전에** 계산해 볼 가치가 있습니다.
올바른 캐시가 내려갈 수 없는 하한 숫자가 존재하며, 그것은 자료구조가 얼마나
영리한지로 정해지지 않기 때문입니다.

영리한 수를 쓰려고 한다면, TTL이 무엇인지 다시 읽어보세요.

## `observation.md`에 쓸 것

- 기준선의 잘못된 점 두 가지. 따로따로 명시하세요 — 하나는 성능 문제이고 하나는
  정확성 문제이며, 근본 원인은 같습니다
- R5의 하한 숫자와 그 근거
- 픽스처에서 기준선이 가장 나쁘게 처리하는 레코드가 무엇이며, 왜 그런지
