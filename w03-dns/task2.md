# Task 2 · On the Wire, and Does DNS Really Steer You?

**Files** — `task2_steering.py`, and a capture you take yourself
**Theory** — §2.4.3 DNS records, §2.5 Video streaming and CDNs
**Kind** — **hands-on. This one cannot be done from code alone.**

---

## Why this task exists

Tasks 1 and 3 are programs. You could write both without a network card.
This is a networking course, so one task each week makes you **look at the real thing**:
your own machine, your own traffic, your own two networks.

Nobody can hand you this capture. It has to come off your interface.

---

## Part A · Capture the exchange

Run Wireshark on the interface you actually use, with capture filter `port 53`,
then run your Task 1 resolver in another window.

```bash
python3 task1_resolve.py www.korea.ac.kr
```

Stop the capture and save as `out/dns.pcapng`.

| # | Requirement |
|---|---|
| A1 | The capture contains **your own** queries, taken on your machine |
| A2 | You can point to one query and its matching response, and read the transaction ID on both |
| A3 | You can point to a response that is a **delegation** (answer count 0, authority section with `NS`) and one that is an **answer** (`A` in the answer section) |
| A4 | Report the size in bytes of the largest DNS response you captured, and say what made it large |

A3 is the point of the whole exercise. In Task 1 you *inferred* the delegation from
parsed text. Here you see that a delegation and an answer are the **same packet format**
with different sections filled in.

> **Privacy** — a `port 53` capture records every name your machine looked up, which
> includes browser tabs and background apps. Before you submit, open the file and check.
> Close other applications first, or capture for a shorter window. If you cannot clean it,
> use path (B) below.

## Part B · Measure the steering

The lecture claims two things. One is easy to show and one is not:

- **(a)** most large sites are served by a CDN, reached through a `CNAME` chain
- **(b)** DNS steers each user to a *nearby* replica

Build the measurement over the 12 sites in `SITES` and the three resolvers in `RESOLVERS`.

| # | Requirement |
|---|---|
| B1 | For each site, follow the `CNAME` chain to its end and record every hop → `out/chains.json` |
| B2 | Ask **each resolver** for each site and record the address sets |
| B3 | Repeat from a **second network** — campus Wi-Fi and phone tethering, for example — and keep both results |
| B4 | Decide which sites are served by a **third party**, and write down the rule you used |
| B5 | Report: of N CDN-hosted sites, how many answered differently from a different resolver or network? |

B3 is the other part you cannot fake. Claim (b) is about *where you are*, so one
vantage point cannot test it.

### The hard part is B4

There is no single right rule.

| Site | What it does |
|---|---|
| `www.microsoft.com` | ends at `akamaiedge.net` — clearly a third party |
| `www.netflix.com` | stops inside `netflix.com` — runs its **own** CDN |
| `www.korea.ac.kr` | no `CNAME`, and no CDN either |
| some sites | sit behind a CDN with **no `CNAME` at all** (anycast) |

A rule that just compares the last two labels **will be wrong on at least one site in
the list.** Find which, and say so. Being wrong and knowing why scores better than a
rule that happens to work.

## Pass condition

`out/report.md` contains:

- the table: site · chain length · final zone · third party? · your rule's verdict
- the steering number from B5, with both networks named
- at least one site your rule got wrong, and why
- from Part A: the two packet numbers for A3, and the byte count for A4

```bash
python3 test_tasks.py        # checks the files exist and the capture is readable
```

The harness can check that your capture parses and that the report has its sections.
It cannot check that you understood the packets. That is what `observation.md` is for.

## Path (B) · If capture is blocked

Some campus and corporate networks block `dig +trace`, or outbound port 53 to public
resolvers, or you may not be able to install Wireshark.

- **Part A** — use the official **Wireshark Lab: DNS** trace in `traces/`. You lose
  "it is my own traffic", so instead answer: whose machine was this, and how can you tell?
- **Part B** — you still need two vantage points. If only one network is available,
  compare **two resolvers at very different distances** (a Korean ISP resolver and
  a US one) and say that is what you did, and what it weakens about your conclusion
- Source and attribution: `traces/README.md`

## What to write in `observation.md`

- The one-sentence difference between a delegation response and an answer response,
  written from what you saw in the capture rather than from the slide
- Your third-party rule, the site it got wrong, and why
- The steering number — and whether it supports claim (b) or not. It is allowed not to.

---

## 한국어 번역본 (Korean Translation)

# 과제 2 · 와이어 위에서, 그리고 DNS는 정말 트래픽을 유도하는가?

**파일** — `task2_steering.py`, 그리고 직접 캡처한 캡처본
**이론** — §2.4.3 DNS 레코드, §2.5 비디오 스트리밍과 CDN
**종류** — **실습. 코드만으로는 수행할 수 없음.**

---

## 이 과제가 존재하는 이유

과제 1과 3은 프로그램입니다. 네트워크 카드 없이도 작성할 수 있습니다.
이 과목은 네트워킹 과목이므로, 매주 하나의 과제는 여러분이 **실물을 보도록** 합니다:
여러분의 기계, 여러분의 트래픽, 여러분의 두 네트워크.

아무도 이 캡처를 대신해 줄 수 없습니다. 여러분의 인터페이스에서 직접 떠야 합니다.

---

## 파트 A · 교환 캡처하기

실제로 사용하는 인터페이스에서 캡처 필터 `port 53`으로 Wireshark를 실행한 뒤,
다른 창에서 과제 1의 리졸버를 실행하세요.

```bash
python3 task1_resolve.py www.korea.ac.kr
```

캡처를 중지하고 `out/dns.pcapng`로 저장하세요.

| # | 요구 사항 |
|---|---|
| A1 | 캡처에 **여러분 자신의** 쿼리가 포함되며, 여러분의 기계에서 취득했을 것 |
| A2 | 하나의 쿼리와 이에 대응하는 응답을 가리키고, 양쪽의 트랜잭션 ID를 읽을 수 있을 것 |
| A3 | **위임**인 응답(답변 개수 0, 권한 섹션에 `NS`)과 **답변**인 응답(답변 섹션에 `A`)을 각각 가리킬 수 있을 것 |
| A4 | 캡처한 가장 큰 DNS 응답의 바이트 크기를 보고하고, 무엇 때문에 커졌는지 말할 것 |

A3이 전체 실습의 핵심입니다. 과제 1에서는 파싱된 텍스트에서 위임을 *추론*했습니다.
여기서는 위임과 답변이 채워진 섹션만 다를 뿐 **같은 패킷 형식**임을 봅니다.

> **개인정보** — `port 53` 캡처는 여러분의 기계가 조회한 모든 이름을 기록하며, 여기에는
> 브라우저 탭과 백그라운드 앱도 포함됩니다. 제출 전에 파일을 열어 확인하세요.
> 다른 애플리케이션을 먼저 닫거나, 캡처 시간을 짧게 하세요. 정리할 수 없다면
> 아래 경로 (B)를 사용하세요.

## 파트 B · 스티어링 측정하기

수업에서는 두 가지를 주장합니다. 하나는 보이기 쉽고, 다른 하나는 그렇지 않습니다:

- **(a)** 대부분의 대형 사이트는 `CNAME` 체인을 거쳐 CDN으로 서비스된다
- **(b)** DNS는 각 사용자를 *가까운* 복제 서버로 유도한다

`SITES`의 12개 사이트와 `RESOLVERS`의 3개 리졸버에 대해 측정을 수행하세요.

| # | 요구 사항 |
|---|---|
| B1 | 각 사이트마다 `CNAME` 체인을 끝까지 따라가며 모든 홉을 기록 → `out/chains.json` |
| B2 | 각 사이트를 **각 리졸버**에 질의하고 주소 집합을 기록 |
| B3 | **두 번째 네트워크**에서도 반복 — 예: 캠퍼스 와이파이와 휴대폰 테더링 — 두 결과를 모두 보관 |
| B4 | 어떤 사이트가 **제3자**에 의해 서비스되는지 정하고, 사용한 규칙을 적음 |
| B5 | 보고: CDN 호스팅 사이트 N개 중 리졸버나 네트워크에 따라 다르게 응답한 곳이 몇 개인지? |

B3은 속일 수 없는 또 다른 부분입니다. 주장 (b)는 *여러분이 어디에 있는지*에 관한 것이므로,
하나의 관측 지점만으로는 검증할 수 없습니다.

### 어려운 부분은 B4

정답인 규칙은 하나만 있지 않습니다.

| 사이트 | 특징 |
|---|---|
| `www.microsoft.com` | `akamaiedge.net`에서 끝남 — 명확히 제3자 |
| `www.netflix.com` | `netflix.com` 내부에서 끝남 — **자체** CDN 운영 |
| `www.korea.ac.kr` | `CNAME`도 없고, CDN도 없음 |
| 일부 사이트 | **`CNAME` 없이** CDN 뒤에 있음 (애니캐스트) |

마지막 두 레이블만 비교하는 규칙은 목록 중 **적어도 하나의 사이트에서는 틀립니다.**
어느 사이트인지 찾고, 그렇게 말하세요. 우연히 맞는 규칙보다, 틀리고 왜 틀렸는지
아는 것이 더 좋은 점수를 받습니다.

## 통과 조건

`out/report.md`에 다음이 포함될 것:

- 표: 사이트 · 체인 길이 · 최종 존 · 제3자 여부 · 여러분 규칙의 판정
- 두 네트워크의 이름을 명시한 B5의 스티어링 수치
- 여러분의 규칙이 틀린 사이트가 최소 하나, 그리고 그 이유
- 파트 A에서: A3에 해당하는 두 패킷 번호, 그리고 A4의 바이트 수

```bash
python3 test_tasks.py        # 파일 존재 여부와 캡처 판독 가능성을 검사
```

하네스는 캡처가 파싱되는지와 보고서에 해당 섹션이 있는지를 검사할 수 있습니다.
패킷을 이해했는지는 검사할 수 없습니다. 그것이 `observation.md`의 용도입니다.

## 경로 (B) · 캡처가 차단된 경우

일부 캠퍼스 및 기업 네트워크에서는 `dig +trace`나 공용 리졸버로의 아웃바운드 53번 포트를
차단하거나, Wireshark를 설치하지 못할 수 있습니다.

- **파트 A** — `traces/`에 있는 공식 **Wireshark Lab: DNS** 트레이스를 사용하세요. "내 트래픽이다"를
  잃는 대신 이렇게 답하세요: 누구의 기계였으며, 어떻게 알 수 있는지?
- **파트 B** — 여전히 두 관측 지점이 필요합니다. 하나의 네트워크만 가능하다면,
  **거리가 매우 다른 두 리졸버**(한국 ISP 리졸버와 미국 리졸버)를 비교하고, 그렇게 했으며
  결론의 무엇이 약해지는지 명시하세요
- 출처 및 저작권 표시: `traces/README.md`

## `observation.md`에 쓸 것

- 슬라이드가 아니라 캡처에서 본 것을 바탕으로 쓴, 위임 응답과 답변 응답의 한 문장 차이
- 여러분의 제3자 판정 규칙, 그 규칙이 틀린 사이트, 그리고 이유
- 스티어링 수치 — 그리고 그것이 주장 (b)를 뒷받침하는지 여부. 뒷받침하지 않아도 됩니다.
