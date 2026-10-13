# Week 4 Lab · TCP — Reliability, Measurement, Congestion

**Theory** — 4-1 TCP (§3.5 handshake, sequence numbers) · 4-2 TCP congestion control (§3.7)
**Textbook lab (path B)** — Wireshark Lab: Exploring TCP
**Submit to** — `w04-tcp/out/`

TCP does three things that IP does not: it numbers what you send, it notices what
went missing, and it slows down when the network is full. This week you build the
first, measure the second on your own link, and fight over the third.

```bash
cd w04-tcp
```

| | Task | You build |
|---|---|---|
| 1 | Reliable delivery over a bad channel | a sender and receiver that survive 10% loss |
| 2 | Measure your own link, twice | a throughput study and a captured handshake |
| 3 | Beat the fixed window | congestion control, judged on a shared link |

Details and requirements are in **`task1.md`**, **`task2.md`**, **`task3.md`**.

---

## Running everything

```bash
python3 task1_rdt.py --verify              # Task 1
python3 task2_measure.py --label "campus"  # Task 2, once per network
python3 bench.py --yours                   # Task 3
python3 test_tasks.py                      # all of it
```

## What to submit

| File | From |
|---|---|
| `task1_rdt.py` | your sender and receiver |
| `out/throughput.json` | at least two labelled networks |
| `out/tcp.pcapng` | your own handshake capture |
| `task3_congestion.py` | your congestion control |
| `out/bench.txt` | output of `python3 bench.py --yours` |
| `out/observation.md` | 2–3 lines per task |

```bash
python3 ../check.py w04
```

## Path (B) · when measurement is blocked

- **Task 1** — unaffected. The channel is simulated
- **Task 2** — if you cannot capture, use the official **Wireshark Lab: Exploring TCP**
  trace in `traces/`. You still need two networks for the throughput half; phone
  tethering counts. If you truly have one network, measure at two very different
  times of day instead and say so
- **Task 3** — unaffected. Fully simulated

---

## 한국어 번역본 (Korean Translation)

# 4주차 실습 · TCP — 신뢰성, 측정, 혼잡

**이론** — 4-1 TCP (§3.5 핸드셰이크, 순서 번호) · 4-2 TCP 혼잡 제어 (§3.7)
**교재 실습 (경로 B)** — Wireshark Lab: Exploring TCP
**제출 위치** — `w04-tcp/out/`

TCP는 IP가 하지 않는 세 가지 일을 합니다: 보내는 것에 번호를 매기고, 무엇이 사라졌는지
알아차리고, 네트워크가 가득 차면 속도를 줄입니다. 이번 주에는 첫 번째를 직접 만들고,
두 번째를 여러분 자신의 링크에서 측정하고, 세 번째를 두고 겨룹니다.

```bash
cd w04-tcp
```

| | 과제 | 만들 것 |
|---|---|---|
| 1 | 나쁜 채널 위에서의 신뢰적 전달 | 10% 손실에서도 살아남는 송신자와 수신자 |
| 2 | 자신의 링크를 두 번 측정하기 | 처리량 연구와 직접 캡처한 핸드셰이크 |
| 3 | 고정 윈도 뛰어넘기 | 공유 링크에서 평가받는 혼잡 제어 |

세부 사항과 요구 사항은 **`task1.md`**, **`task2.md`**, **`task3.md`**에 있습니다.

---

## 전체 실행하기

```bash
python3 task1_rdt.py --verify              # 과제 1
python3 task2_measure.py --label "campus"  # 과제 2, 네트워크마다 한 번씩
python3 bench.py --yours                   # 과제 3
python3 test_tasks.py                      # 전부 실행
```

## 제출할 것

| 파일 | 내용 |
|---|---|
| `task1_rdt.py` | 여러분의 송신자와 수신자 |
| `out/throughput.json` | 레이블을 붙인 네트워크 최소 두 개 |
| `out/tcp.pcapng` | 직접 캡처한 핸드셰이크 |
| `task3_congestion.py` | 여러분의 혼잡 제어 |
| `out/bench.txt` | `python3 bench.py --yours`의 출력 |
| `out/observation.md` | 과제별 2–3줄 |

```bash
python3 ../check.py w04
```

## 경로 (B) · 측정이 차단된 경우

- **과제 1** — 영향 없음. 채널이 시뮬레이션됩니다
- **과제 2** — 캡처할 수 없다면 `traces/`에 있는 공식 **Wireshark Lab: Exploring TCP**
  트레이스를 사용하세요. 처리량 측정 부분에는 여전히 두 개의 네트워크가 필요하며, 휴대폰
  테더링도 인정됩니다. 정말로 네트워크가 하나뿐이라면, 대신 하루 중 매우 다른 두 시간대에
  측정하고 그렇게 명시하세요
- **과제 3** — 영향 없음. 완전 시뮬레이션입니다
