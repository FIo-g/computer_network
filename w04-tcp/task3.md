# Task 3 · Beat the Fixed Window

**Files** — `task3_congestion.py` · harness `bench.py` (**do not edit the harness**)
**Theory** — §3.7 TCP congestion control
**Kind** — improvement · fully simulated

---

## What you are given

`FixedWindow` sends 64 packets at a time and never listens. This is not a
strawman — it is what you get with no congestion control at all, and it is
roughly what the internet did until it collapsed in October 1986.

Your sender sees exactly what a real one sees:

```python
.window        how many packets you are willing to have in flight
.on_ack()      one packet made it there and back
.on_loss()     a packet timed out
```

No queue depth, no link rate. You infer them from those two events. That
inference *is* §3.7.

## The link

```
  1 packet per slot   ·   round trip 20 slots   ·   queue 10, tail drop   ·   4000 slots
```

So the pipe holds about 20 packets. Above that you are filling a queue, and
above 30 you are dropping.

## Where the baseline lands

```
  baseline   goodput  986.8/1000 slots   loss  37.4%   retx  2340   avg queue   8.8
```

**Read that before you plan anything.** The baseline has nearly the highest
goodput the link can give. It gets there by keeping the queue permanently full
and throwing away 37% of everything it sends. Every other flow sharing this
link waits behind those 8.8 packets.

So "beat it" does not mean "more goodput". It means: get almost as much, without
wrecking the link.

## Requirements

| # | Requirement |
|---|---|
| R1 | `YourControl` exposes `.window`, `.on_ack()`, `.on_loss()` |
| R2 | `bench.py` unmodified |
| R3 | Loss at most **5%** |
| R4 | Average queue at most **5.0** |
| R5 | In `observation.md`: the baseline has the highest goodput here. Why is it still the worst sender? |

## Grading

| | Requirement |
|---|---|
| pass | R1–R4 |
| good | R1–R4, and goodput ≥ **85%** of the baseline |
| **strong** | R1–R4, and goodput ≥ **93%** of the baseline |

Textbook AIMD lands around 82% — a pass, not a good. Getting past 90% needs you
to think about what the window should converge *to*, not just how to back off.

## What to write in `observation.md`

- R5, in your own words
- What your window converges to, and how that number relates to the link
- What happened to goodput when you made the backoff gentler, and what it cost

---

## 한국어 번역본 (Korean Translation)

# 과제 3 · 고정 윈도 뛰어넘기

**파일** — `task3_congestion.py` · 하네스 `bench.py` (**하네스는 수정하지 마세요**)
**이론** — §3.7 TCP 혼잡 제어
**종류** — 개선 · 완전 시뮬레이션

---

## 주어진 것

`FixedWindow`는 한 번에 64개의 패킷을 보내고 네트워크의 반응에 전혀 귀 기울이지 않습니다.
이것은 일부러 약하게 만든 허수아비가 아닙니다 — 혼잡 제어가 전혀 없을 때 얻게 되는 것이며,
1986년 10월 인터넷이 붕괴하기 전까지 인터넷이 대략 이렇게 동작했습니다.

여러분의 송신자는 실제 송신자가 보는 것과 정확히 같은 것을 봅니다:

```python
.window        전송 중(in flight)으로 둘 의향이 있는 패킷 수
.on_ack()      패킷 하나가 목적지에 도달하고 응답이 돌아옴
.on_loss()     패킷 하나가 타임아웃됨
```

큐 깊이도, 링크 속도도 알려주지 않습니다. 이 두 이벤트로부터 그것들을 추론해야 합니다.
그 추론이 *바로* §3.7입니다.

## 링크

```
  슬롯당 1패킷   ·   왕복 20슬롯   ·   큐 10, 꼬리 드롭(tail drop)   ·   4000슬롯
```

따라서 파이프에는 약 20개의 패킷이 들어갑니다. 그보다 많으면 큐를 채우게 되고,
30개를 넘으면 패킷이 버려집니다.

## 기준선의 위치

```
  baseline   goodput  986.8/1000 slots   loss  37.4%   retx  2340   avg queue   8.8
```

**무엇이든 계획하기 전에 이 줄부터 읽으세요.** 기준선은 이 링크가 낼 수 있는 거의 최고 수준의
굿풋을 기록합니다. 그것은 큐를 항상 가득 찬 상태로 유지하고, 보내는 모든 것의 37%를 버림으로써
그 수치에 도달합니다. 이 링크를 공유하는 다른 모든 흐름은 그 8.8개의 패킷 뒤에서 기다려야 합니다.

따라서 "뛰어넘기"는 "더 많은 굿풋"을 의미하지 않습니다. 링크를 망가뜨리지 않으면서 거의 같은
양을 얻으라는 뜻입니다.

## 요구 사항

| # | 요구 사항 |
|---|---|
| R1 | `YourControl`은 `.window`, `.on_ack()`, `.on_loss()`를 제공 |
| R2 | `bench.py`는 수정하지 않음 |
| R3 | 손실률 최대 **5%** |
| R4 | 평균 큐 길이 최대 **5.0** |
| R5 | `observation.md`에: 여기서는 기준선의 굿풋이 가장 높습니다. 그런데도 왜 가장 나쁜 송신자인가? |

## 채점

| | 요구 사항 |
|---|---|
| 통과 | R1–R4 |
| 양호 | R1–R4, 그리고 굿풋이 기준선의 **85%** 이상 |
| **우수** | R1–R4, 그리고 굿풋이 기준선의 **93%** 이상 |

교과서적인 AIMD는 약 82%에 머뭅니다 — 통과이지만 양호는 아닙니다. 90%를 넘기려면 단지 어떻게
물러날지가 아니라, 윈도가 *무엇으로* 수렴해야 하는지를 생각해야 합니다.

## `observation.md`에 쓸 것

- R5, 여러분 자신의 말로
- 여러분의 윈도가 무엇으로 수렴하는지, 그리고 그 숫자가 링크와 어떤 관계인지
- 백오프를 더 완만하게 했을 때 굿풋에 무슨 일이 일어났는지, 그리고 그 대가는 무엇이었는지
