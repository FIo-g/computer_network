# Task 2 · Measure Your Own Link, Twice

**Files** — `task2_measure.py`, and a capture you take yourself
**Theory** — §3.5 handshake and sequence numbers, §3.7 what limits throughput
**Kind** — **hands-on. This one cannot be done from code alone.**

---

## Why this task exists

Tasks 1 and 3 run on a simulated network. They would give the same answer on a
laptop with the Ethernet port glued shut. This one is about **your** connection,
right now, and the number will not match anybody else's.

## Part A · Capture a real handshake

Run Wireshark with capture filter `tcp port 443`, then start a transfer:

```bash
python3 task2_measure.py --label "campus wifi"
```

Stop, save as `out/tcp.pcapng`, and find one connection's opening.

| # | Requirement |
|---|---|
| A1 | The capture is your own traffic, from your machine |
| A2 | Point to the SYN, SYN-ACK and ACK of one connection by packet number |
| A3 | Report both **initial sequence numbers**. They are not 0, and not each other |
| A4 | Read the SYN's **options**: MSS, window scale factor, SACK permitted |
| A5 | Compute the **advertised window** after scaling, and compare it with the bytes actually in flight later in the transfer |

A3 is worth stopping on. The lecture said sequence numbers count bytes and start
"at some value". Look at what the two ends actually chose, and ask why not zero.

A5 is where §3.7 becomes concrete: the receiver advertised a window, the sender
never filled it, and something else was the limit.

> **Privacy** — narrow the filter to one host if you can, and check the file
> before submitting. If you cannot clean it, use path (B).

## Part B · Measure throughput on two networks

```bash
python3 task2_measure.py --label "campus wifi"
python3 task2_measure.py --label "tethering"
```

Each run does five transfers and appends to `out/throughput.json`.

| # | Requirement |
|---|---|
| B1 | At least **two labelled networks** — campus Wi-Fi and phone tethering, for example |
| B2 | Five runs each, so you have a spread and not a single number |
| B3 | Report median, spread, and **median handshake time** for each |
| B4 | Explain the spread. Five runs on one network do not agree either — say what varies |
| B5 | Relate handshake time to throughput. They are not independent |

B5 is the point of the whole task. One of these two networks will have a worse
handshake time, and that alone will cost it throughput even if its raw capacity
is the same. Name the mechanism from §3.7 that causes it.

## Pass condition

`out/throughput.json` has two or more labels with five runs each, and
`out/observation.md` answers A2–A5 and B3–B5.

```bash
python3 test_tasks.py --task 2
```

The harness checks the files exist and parse. It cannot check that you read the
packets. That is what `observation.md` is for.

## Path (B) · if capture is blocked

- **Part A** — use the official **Wireshark Lab: Exploring TCP** trace in
  `traces/`. Answer A2–A5 from it, and add: whose transfer was this, and how
  can you tell from the capture alone?
- **Part B** — you still need two vantage points. Phone tethering is the easy
  second one. If you genuinely have one network, measure at two very different
  times of day, label them that way, and say what that weakens

## What to write in `observation.md`

- The two initial sequence numbers, and why they are not zero
- The scaled receive window, and what actually limited the transfer instead
- Your two medians, the spread, and the mechanism from B5

---

## 한국어 번역본 (Korean Translation)

# 과제 2 · 자신의 링크를 두 번 측정하기

**파일** — `task2_measure.py`, 그리고 직접 캡처한 캡처본
**이론** — §3.5 핸드셰이크와 순서 번호, §3.7 처리량을 제한하는 요인
**종류** — **실습. 코드만으로는 수행할 수 없음.**

---

## 이 과제가 존재하는 이유

과제 1과 3은 시뮬레이션된 네트워크에서 실행됩니다. 이더넷 포트를 접착제로 막아 버린 노트북에서도
같은 답이 나올 것입니다. 이 과제는 **여러분의** 연결, 바로 지금에 관한 것이며, 그 숫자는 다른
누구의 것과도 일치하지 않을 것입니다.

## 파트 A · 실제 핸드셰이크 캡처하기

캡처 필터 `tcp port 443`으로 Wireshark를 실행한 뒤, 전송을 시작하세요:

```bash
python3 task2_measure.py --label "campus wifi"
```

캡처를 중지하고 `out/tcp.pcapng`로 저장한 뒤, 한 연결의 시작 부분을 찾으세요.

| # | 요구 사항 |
|---|---|
| A1 | 캡처는 여러분 자신의 트래픽이며, 여러분의 기계에서 취득했을 것 |
| A2 | 한 연결의 SYN, SYN-ACK, ACK를 패킷 번호로 가리킬 것 |
| A3 | 양쪽의 **초기 순서 번호**(ISN)를 모두 보고할 것. 둘 다 0이 아니며, 서로 같지도 않음 |
| A4 | SYN의 **옵션**을 읽을 것: MSS, 윈도 스케일 계수, SACK 허용(SACK permitted) |
| A5 | 스케일링을 적용한 **광고 윈도**를 계산하고, 전송 후반에 실제로 전송 중(in flight)이던 바이트 수와 비교할 것 |

A3은 멈춰서 생각해 볼 만한 항목입니다. 강의에서는 순서 번호가 바이트를 세며 "어떤 값에서"
시작한다고 했습니다. 양 끝이 실제로 어떤 값을 골랐는지 보고, 왜 0이 아닌지 자문해 보세요.

A5는 §3.7이 구체화되는 지점입니다: 수신자는 윈도를 광고했지만, 송신자는 그것을 한 번도 채우지
않았고, 다른 무언가가 한계였습니다.

> **개인정보** — 가능하다면 필터를 하나의 호스트로 좁히고, 제출 전에 파일을 확인하세요.
> 정리할 수 없다면 경로 (B)를 사용하세요.

## 파트 B · 두 네트워크에서 처리량 측정하기

```bash
python3 task2_measure.py --label "campus wifi"
python3 task2_measure.py --label "tethering"
```

한 번 실행할 때마다 다섯 번의 전송을 수행하고 `out/throughput.json`에 결과를 추가합니다.

| # | 요구 사항 |
|---|---|
| B1 | **레이블을 붙인 네트워크 최소 두 개** — 예: 캠퍼스 와이파이와 휴대폰 테더링 |
| B2 | 각각 다섯 번 실행하여, 하나의 숫자가 아니라 편차를 볼 수 있을 것 |
| B3 | 각 네트워크에 대해 중앙값, 편차, **핸드셰이크 시간의 중앙값**을 보고할 것 |
| B4 | 편차를 설명할 것. 한 네트워크에서의 다섯 번 실행도 서로 일치하지 않음 — 무엇이 달라지는지 말할 것 |
| B5 | 핸드셰이크 시간과 처리량을 연관 지을 것. 둘은 독립적이지 않음 |

B5가 이 과제 전체의 핵심입니다. 두 네트워크 중 하나는 핸드셰이크 시간이 더 나쁠 것이며, 원래
용량이 같더라도 그것만으로 처리량을 잃게 됩니다. 이를 일으키는 §3.7의 메커니즘을 명시하세요.

## 통과 조건

`out/throughput.json`에 각각 다섯 번씩 실행한 레이블이 두 개 이상 있고, `out/observation.md`가
A2–A5와 B3–B5에 답할 것.

```bash
python3 test_tasks.py --task 2
```

하네스는 파일이 존재하고 파싱되는지를 검사합니다. 여러분이 패킷을 읽었는지는 검사할 수 없습니다.
그것이 `observation.md`의 용도입니다.

## 경로 (B) · 캡처가 차단된 경우

- **파트 A** — `traces/`에 있는 공식 **Wireshark Lab: Exploring TCP** 트레이스를 사용하세요.
  그 트레이스로 A2–A5에 답하고, 다음을 추가하세요: 이것은 누구의 전송이었으며, 캡처만으로
  어떻게 알 수 있는지?
- **파트 B** — 여전히 두 관측 지점이 필요합니다. 휴대폰 테더링이 가장 쉬운 두 번째 관측 지점입니다.
  정말로 네트워크가 하나뿐이라면, 하루 중 매우 다른 두 시간대에 측정하고, 그에 맞게 레이블을
  붙이고, 그로 인해 무엇이 약해지는지 말하세요

## `observation.md`에 쓸 것

- 두 초기 순서 번호, 그리고 그것들이 0이 아닌 이유
- 스케일링된 수신 윈도, 그리고 그 대신 실제로 전송을 제한한 요인
- 두 중앙값, 편차, 그리고 B5의 메커니즘
