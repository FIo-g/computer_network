# 3주차 관찰 기록

## Task 1 · 반복적 리졸버

**결과** — `python3 task1_resolve.py --verify` 5/5 일치

| 이름 | 물은 서버 수 | 비고 |
|---|---:|---|
| www.korea.ac.kr | 3 | 루트 → `.kr` → `korea.ac.kr` |
| dns.google | 3 | |
| en.wikipedia.org | 6 | CNAME 1번 → 루트부터 다시 |
| www.stanford.edu | 6 | CNAME 1번 |
| www.microsoft.com | 10 | CNAME 2번 → 루트부터 3번 걸음. CDN 이름이지만 이번엔 dig 와 같은 주소 |

**루트가 주소를 바로 주지 않은 이유**
- 루트 존에는 TLD 위임(`kr.` 의 NS 와 글루)만 있음 — `www.korea.ac.kr` 의 A 레코드를 가지고 있지 않음
- 캡처 No. 2: 루트의 응답은 AA=0, answer 0개, authority 에 `kr.` NS 6개 → "모르니 저기 물어라"
- 루트는 재귀를 해 주지 않음. 13개 이름의 서버가 전 세계 모든 조회를 대신 걸어 주면 감당 불가 — 그 일은 각자의 리졸버 몫

**글루 없는 위임 (R3)**
- 검증용 5개 이름에서는 한 번도 안 일어남 — 모든 위임에 글루가 붙어 있었음
- 실제로 일어나는 예: `www.mit.edu` — `.edu` 서버가 넘긴 NS 8개가 전부 `*.akam.net`. `.edu` 서버는 `akam.net` 의 권한이 없으므로 글루를 줄 수 없음
- 처리 방법
  - 글루가 있는 서버를 먼저 시도 (추가 비용 없음)
  - 글루 없는 NS 이름은 그 뒤에 줄 세우고, 차례가 왔을 때 하나씩만 루트부터 해석
- 비용: 추가 걸음 1번 = 서버 3개 (루트 → `.net` → `akam.net`), `www.mit.edu` 전체 13개
- 처음 구현은 NS 8개를 모두 미리 해석해서 서버 34개 (추가 24개) → 하나씩 해석하도록 고침. `www.ox.ac.uk` (`ns0.ja.net`) 도 28개 → 10개

**한 이름에 물은 서버 수 vs 노트북**
- 직접 걸으면 3개(`www.korea.ac.kr`) ~ 13개(`www.mit.edu`). CNAME 하나마다 루트부터 다시 걸음
- 노트북은 시스템 리졸버(1.214.68.2, LG U+)에 질문 1번 — 걸음은 리졸버가 대신 하고, 루트와 TLD 의 답은 캐시해 두므로 대부분 마지막 한 단계만 묻게 됨

## Task 2 · DNS 는 정말 가까운 곳으로 보내 주는가

### Part A · 캡처 (`out/dns.pcapng`)

**위임과 답변의 차이 (한 문장)** — 위임(No. 2)과 답변(No. 6)은 헤더와 질문이 같은 형식이고, 위임은 AA=0 으로 answer 를 비운 채 authority 에 다음 존의 NS, additional 에 그 글루를 채우며, 답변은 AA=1 로 answer 에 A 레코드를 채운다 — 차이는 어느 섹션이 채워졌느냐뿐이다.

| # | 캡처에서 |
|---|---|
| A1 | 질의 3개 모두 출발지 192.168.219.57 (이 기계의 en0). 대상 순서가 같은 시각의 `task1_resolve.py` 경로와 일치 |
| A2 | No. 1 질의 → No. 2 응답, 둘 다 ID `0x0af8` |
| A3 위임 | No. 2 (루트): answer 0, authority `kr.` NS 6, additional 글루 10. No. 4 (`.kr`) 도 위임 |
| A3 답변 | No. 6 (163.152.11.6): answer `A 163.152.6.10`, AA=1 |
| A4 | No. 2 — DNS 메시지 **352 바이트** (프레임 394) |

- A4 가 큰 이유: additional 219 바이트 (글루 A 6 + AAAA 4 + EDNS OPT), authority 100 바이트 (NS 6) — 위임을 크게 만드는 것은 다음 서버들의 주소인 글루
- No. 4: `.kr` 서버가 `ac.kr` 을 건너뛰고 바로 `korea.ac.kr` NS 를 줌 → `ac.kr` 은 레이블일 뿐 별도 존이 아님
- 개인정보: 캡처 필터에서 시스템 리졸버(1.214.68.2, 61.41.153.2)를 제외 → 캡처에 있는 이름은 `www.korea.ac.kr` 하나뿐

### B4 · 제3자 판정 규칙

**규칙**
1. CNAME 체인 끝 이름의 eTLD+1 (공용 접미사 `co.uk`, `ac.kr` 고려) 이 사이트와 다르면 → 제3자
2. 같거나 CNAME 이 없으면 최종 주소를 광고하는 AS 확인 → CDN 이 본업인 회사(Akamai, Fastly, Cloudflare …)면 제3자 (CNAME 없는 애니캐스트 대비)
3. 둘 다 아니면 → 자체

**결과** — 12개 중 11개 정답

**틀린 사이트: `www.wikipedia.org`**
- 체인이 `dyna.wikimedia.org` 로 나감 → 규칙은 제3자로 판정
- 실제 주소는 Wikimedia 자신의 AS14907 (자체 캐시 데이터센터)
- 이유: 한 조직이 등록 도메인 두 개(`wikipedia.org`, `wikimedia.org`)를 씀 — 이름은 소유를 말해 주지 않음

**마지막 두 레이블 규칙**
- 같은 `www.wikipedia.org` 에서 틀림
- `www.korea.ac.kr`, `www.bbc.co.uk` 은 `ac.kr`, `co.uk` 를 "도메인"으로 보고도 우연히 맞음 — 같은 접미사의 다른 기관으로 CNAME 했다면 자체로 오판

**AS 만 보는 규칙도 답이 아님**
- adobe 의 일부 답은 LG U+ AS3786 안에 있는 Akamai 캐시
- github 은 한국에선 Microsoft AS8075 (Azure), 미국 ECS 로는 GitHub AS36459 — 관측 위치에 따라 판정이 바뀜

### B5 · 스티어링 수치

**관측 지점**
- `home-wifi` — LG U+ 가정 Wi-Fi (AS17858), resolver 1.214.68.2
- `lte` — SK Telecom 휴대폰 테더링 (AS9644)
- 공용 resolver: Google 8.8.8.8, Quad9 (LG U+ 에서는 9.9.9.9 가 닿지 않아 149.112.112.112 사용 → 싱가포르 PoP, LTE 에서는 9.9.9.9 → 오사카 PoP)
- 보조: ECS 로 고려대(163.152.0.0/24)·Stanford(171.64.0.0/24) 사용자를 흉내

**수치** — 제3자 CDN 사이트 **8개 중 7개**가 resolver 나 네트워크에 따라 다른 주소 집합으로 응답
- resolver 만 바꿔도 7/8
- 네트워크를 바꾸면 (같은 resolver 끼리) 3/8 — 셋 다 Akamai
- 같은 resolver 에 3번 물어도 바뀐 것 3/8 — "다르다"의 일부는 로드밸런싱 회전

**주장 (b) 를 뒷받침하는가 → 아니다**
- 교차 비교: 두 네트워크가 서로 다른 답을 받은 3개 사이트에서 "내 답"과 "남의 답"까지의 RTT 를 같은 네트워크에서 측정, 6번 중
  - 내 답이 5 ms 넘게 가까움 1번
  - 차이 없음 4번
  - 남의 답이 더 가까움 1번 (LTE 에서 adobe 36 ms vs 26 ms)
- "다르다"가 "가깝다"로 이어진 것은 resolver 를 바꿀 때뿐
  - 같은 집 회선에서 Akamai 를 LG U+ resolver 로 받으면 약 10 ms, 싱가포르 PoP 의 Quad9 로 받으면 39–42 ms
  - 기준은 내 위치가 아니라 **resolver 의 위치**
- 가까움을 DNS 가 만들지 않은 경우
  - Fastly 4개: 통신사 resolver 에는 146.75.x, 공용 resolver 에는 151.101.x 애니캐스트 — 주소는 달라도 RTT 는 같음 → 라우팅이 가까움을 만듦
  - Netlify(stanford): 어디서 물어도 같은 주소
- ECS 흉내: 답이 옮겨 간 CDN 사이트 0/8
  - Fastly 권한 서버는 `CLIENT-SUBNET …/0` 으로 "서브넷을 보지 않았다"고 답함
  - 옮겨 간 것은 CDN 이 아닌 github, wikipedia 뿐 (권한 서버가 ECS 를 보고 지역별로 응답)
- 결론: DNS 는 답을 바꾸지만 그 기준은 resolver 이고, 서울의 두 통신사 사이에서는 그 차이가 거리 차이로 이어지지 않음

## Task 3 · 기준 캐시 뛰어넘기

**결과** (`out/bench.txt`)

| | upstream | hit rate | stale |
|---|---:|---:|---:|
| baseline | 325 | 67.5% | 266 |
| yours | **275** | 72.5% | **0** |

**baseline 의 두 문제 — 원인은 하나: 레코드의 TTL 을 버리고 무엇이든 60초 보관**
- 정확성: TTL 이 60초보다 짧은 레코드를 만료 뒤에도 내줌 → stale 266개 (microsoft 189, cnn 77)
- 성능: TTL 이 60초보다 긴 레코드를 60초마다 버리고 다시 물음

  | 이름 | TTL | baseline 질의 | 필요한 최소 |
  |---|---:|---:|---:|
  | www.korea.ac.kr | 3600 | 25 | 1 |
  | www.stanford.edu | 3600 | 27 | 1 |
  | dns.google | 86400 | 21 | 1 |
  | a.root-servers.net | 86400 | 20 | 1 |
  | www.wikipedia.org | 600 | 31 | 6 |

- (부수) 목록을 선형 탐색 — 이름이 10개라 이번 워크로드에선 영향 없음
- 고친 것: `name → (address, 가져온 시각 + TTL)` 사전, `now ≤ 만료 시각` 일 때만 캐시에서 응답

**하한 (R5) — 275**
- 하네스는 그 질의를 처리하면서 그 이름을 가져온 경우에만 신선하다고 인정 → 가져오기는 질의 시각에만 일어날 수 있음
- 시각 t 에 가져온 레코드는 [t, t + TTL] 의 질의만 덮음 → 질의 q 를 덮는 가장 늦은 가져오기는 q 자신
- 그러므로 이름마다 "만료된 뒤 처음 온 질의에서만 가져오기"가 최소 — 더 일찍 가져와도 뒤의 질의를 더 덮지 못함
- 이름별 최소: microsoft 118, cnn 76, netflix 37, spotify 23, github 11, wikipedia 6, 긴 TTL 4개 각 1 → **합 275**
  - 이름 10개의 첫 조회 10번은 피할 수 없고, 나머지 265번은 TTL 만료가 강제함
- `YourCache` 가 정확히 275 → 더 줄일 여지 없음. 하한을 정하는 것은 자료구조가 아니라 TTL 과 워크로드

**baseline 이 가장 못 다루는 레코드: `www.microsoft.com`**
- TTL 20초인데 60초 보관 → 받아 온 뒤 40초 동안 만료된 답을 내줌
- 가장 인기 있는 이름 (Zipf 1위, 1000 중 322번) → stale 266개 중 189개 (71%)
- baseline 이 이 이름을 52번만 묻는 것(하한 118보다 적음)은 효율이 아니라 틀린 답의 대가
