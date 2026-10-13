# Task 1 · Reliable Delivery Over a Bad Channel

**File** — `task1_rdt.py`
**Theory** — §3.4 reliable data transfer, §3.5 TCP sequence numbers
**Kind** — implementation · fully simulated

---

## What you are building

`UnreliableChannel` loses 10% of packets, duplicates 3%, reorders, and never
tells you which. Move 2,000 bytes across it and have them arrive byte-identical.

This is TCP's reliability with congestion control removed. It is worth building
once by hand before you trust a socket again.

## Requirements

| # | Requirement |
|---|---|
| R1 | Split the data into `PAYLOAD`-sized pieces and number them |
| R2 | The receiver reassembles **in order**, even though the channel reorders |
| R3 | A duplicate arriving twice must not corrupt the output |
| R4 | Anything unacknowledged is retransmitted until it is acknowledged |
| R5 | Do not modify `UnreliableChannel`, and do not read its internals |
| R6 | Terminate. `--verify` gives you 200,000 steps; needing more means a livelock |

R3 is the one people lose. A duplicate ACK and a duplicate data packet fail in
different ways, and both happen here.

## Choose your protocol

Stop-and-wait is easiest to get right and the slowest. A sliding window is the
point of §3.4.3 and will cost you an afternoon. Either passes — **say which you
chose and why** in `observation.md`.

## Pass condition

```bash
python3 task1_rdt.py --verify
```

```
  result   IDENTICAL
```

The harness compares SHA-256 of what went in and what came out. Then try a
different seed — a protocol that only works on seed 246 is not a protocol:

```bash
python3 task1_rdt.py --verify --seed 999
```

## What to write in `observation.md`

- Which protocol you chose, and the one case that forced the choice
- How many packets did the channel actually carry for 2,000 bytes of data?
  Compare with the minimum — that ratio is what reliability cost you
- What broke first: loss, reordering, or duplication?

---

## 한국어 번역본 (Korean Translation)

# 과제 1 · 나쁜 채널 위에서의 신뢰적 전달

**파일** — `task1_rdt.py`
**이론** — §3.4 신뢰적 데이터 전송, §3.5 TCP 순서 번호
**종류** — 구현 · 완전 시뮬레이션

---

## 만드는 것

`UnreliableChannel`은 패킷의 10%를 손실시키고, 3%를 중복시키고, 순서를 뒤바꾸며, 어떤 일이
일어났는지 절대 알려주지 않습니다. 이 채널을 통해 2,000바이트를 옮기고, 바이트 단위로 동일하게
도착하도록 하세요.

이것은 혼잡 제어를 제거한 TCP의 신뢰성입니다. 소켓을 다시 믿기 전에 한 번쯤 직접 만들어 볼
가치가 있습니다.

## 요구 사항

| # | 요구 사항 |
|---|---|
| R1 | 데이터를 `PAYLOAD` 크기의 조각으로 나누고 번호를 매김 |
| R2 | 채널이 순서를 뒤바꾸더라도 수신자는 **순서대로** 재조립 |
| R3 | 같은 패킷이 중복으로 두 번 도착해도 출력이 손상되지 않아야 함 |
| R4 | 확인 응답을 받지 못한 것은 확인 응답을 받을 때까지 재전송 |
| R5 | `UnreliableChannel`을 수정하지 말고, 그 내부를 읽지도 말 것 |
| R6 | 반드시 종료할 것. `--verify`는 200,000 스텝을 주며, 그보다 더 필요하다면 라이브락(livelock)임 |

R3이 사람들이 점수를 잃는 항목입니다. 중복 ACK와 중복 데이터 패킷은 서로 다른 방식으로
문제를 일으키며, 여기서는 둘 다 발생합니다.

## 프로토콜 선택하기

정지-대기(stop-and-wait)는 올바르게 만들기 가장 쉽지만 가장 느립니다. 슬라이딩 윈도는 §3.4.3의
핵심이며 오후 한나절이 들 것입니다. 어느 쪽이든 통과합니다 — `observation.md`에 **어느 것을
선택했고 왜 선택했는지 쓰세요**.

## 통과 조건

```bash
python3 task1_rdt.py --verify
```

```
  result   IDENTICAL
```

하네스는 들어간 데이터와 나온 데이터의 SHA-256을 비교합니다. 그다음 다른 시드로도 시도해 보세요 —
시드 246에서만 동작하는 프로토콜은 프로토콜이 아닙니다:

```bash
python3 task1_rdt.py --verify --seed 999
```

## `observation.md`에 쓸 것

- 어떤 프로토콜을 선택했는지, 그리고 그 선택을 강제한 하나의 경우
- 2,000바이트의 데이터를 위해 채널이 실제로 몇 개의 패킷을 운반했는지? 최솟값과
  비교하세요 — 그 비율이 신뢰성의 대가입니다
- 무엇이 가장 먼저 문제를 일으켰는지: 손실, 순서 뒤바뀜, 아니면 중복?
