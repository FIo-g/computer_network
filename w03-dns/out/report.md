# Task 2 · DNS는 정말 가까운 복제 서버로 보내 주는가

수집 `home-wifi` (LG POWERCOMM, AS17858) `2026-10-06T22:05:32+09:00`, `lte` (SK Telecom, AS9644) `2026-10-06T22:18:12+09:00` · `python3 task2_steering.py --collect --network <이름>` 후 `--report` 로 생성. 원시 데이터 `out/chains.json`, 관측 지점과 주소 정보 `out/probe.json`.

## 관측 지점

| network | 종류 | resolver | 실제로 물은 주소 | 권한 서버가 본 리졸버 (Akamai whoami) |
|---|---|---|---|---|
| home-wifi | 물리 · 공인 IP 182.218.46.139 (AS17858 LG POWERCOMM, KR) | system | 1.214.68.2 | 2001:270:0:a1::f5:201 AS3786 |
| home-wifi |  | google | 8.8.8.8 | 74.125.179.158 AS15169 · ECS 182.218.46.0/24/24 |
| home-wifi |  | quad9 | 149.112.112.112 (9.9.9.9 응답 없음) | 2a04:c607:33:14:9999::145 AS49544 · PoP `res720.qsin6` |
| lte | 물리 · 공인 IP 211.235.73.246 (AS9644 SK Telecom, KR) | system | fe80::8c98:6bff:fedb:564%en0 | 223.62.68.29 AS9644 |
| lte |  | google | 8.8.8.8 | 172.217.108.220 AS15169 · ECS 211.235.73.0/24/24 |
| lte |  | quad9 | 9.9.9.9 | 2620:171:f5:f003:9999::244 AS42 · PoP `res700.itm` |
| ecs-kr-campus | ECS 시뮬레이션 · `163.152.0.0/24` 을 Google(8.8.8.8)에 실어 보냄 | google | 8.8.8.8 | Google 이 권한 서버로 넘긴 ECS: 163.152.0.0/24 |
| ecs-us-stanford | ECS 시뮬레이션 · `171.64.0.0/24` 을 Google(8.8.8.8)에 실어 보냄 | google | 8.8.8.8 | Google 이 권한 서버로 넘긴 ECS: 171.64.0.0/24 |

## Part A · 캡처에서 본 것

`out/dns.pcapng`: DNS 메시지 6개 (질의 3, 응답 3), 질의를 보낸 주소 192.168.219.57. 번호는 Wireshark 의 No. 열입니다.

| No. | 방향 | 서버 | 질의 이름 | ID | an/ns/ar | 종류 | DNS 바이트 |
|---:|---|---|---|---|---|---|---:|
| 1 | → | 198.41.0.4 | `www.korea.ac.kr.` | 0x0af8 | 0/0/1 | query | 44 |
| 2 | ← | 198.41.0.4 | `www.korea.ac.kr.` | 0x0af8 | 0/6/11 | delegation | 352 |
| 3 | → | 210.101.61.1 | `www.korea.ac.kr.` | 0xeec9 | 0/0/1 | query | 44 |
| 4 | ← | 210.101.61.1 | `www.korea.ac.kr.` | 0xeec9 | 0/2/3 | delegation | 116 |
| 5 | → | 163.152.11.6 | `www.korea.ac.kr.` | 0xb916 | 0/0/1 | query | 44 |
| 6 | ← | 163.152.11.6 | `www.korea.ac.kr.` | 0xb916 | 1/0/1 | answer | 60 |

| # | 요구 | 캡처에서 |
|---|---|---|
| A1 | 내 기계에서 뜬 내 질의 | 모든 질의의 출발지가 192.168.219.57 — 이 기계의 현재 기본 인터페이스 주소와 같음; 질의 대상 3개가 같은 시간에 돌린 `task1_resolve.py` 의 경로 3단계와 순서까지 일치 |
| A2 | 질의와 응답의 짝 | No. 1 질의 → No. 2 응답, 둘 다 ID 0x0af8, `www.korea.ac.kr.` @ 198.41.0.4 |
| A3 | 위임 | No. 2: 198.41.0.4 의 응답, answer 0개, authority NS 6개 (b.dns.kr., c.dns.kr., d.dns.kr. …), additional 글루 10개, AA=0 |
| A3 | 답변 | No. 6: 163.152.11.6 의 응답, answer 에 A 163.152.6.10, AA=1 |
| A4 | 가장 큰 응답 | No. 2: DNS 메시지 **352 바이트** (프레임 394 바이트), `www.korea.ac.kr.` @ 198.41.0.4. answer 0B [-] · authority 100B [NS×6] · additional 219B [A×6, AAAA×4, OPT×1] |

캡처에 나온 질의 이름 전체 (개인정보 확인용): `www.korea.ac.kr.`

## B1 · B4 · CNAME 체인과 제3자 판정

체인은 `home-wifi/system` 리졸버가 준 것입니다. final zone 은 SOA 로 찾은 실제 존의 apex 입니다.

| site | chain length | 체인 | final zone | 주소의 AS | third party? (사람) | rule verdict | last-two-labels |
|---|---:|---|---|---|---|---|---|
| www.microsoft.com | 2 | `www.microsoft.com-c-3.edgekey.net` → `e13678.dscb.akamaiedge.net` | `dscb.akamaiedge.net` | AS16625 Akamai | yes — Akamai 가 서비스 (AS16625) | yes ✓ (체인이 `akamaiedge.net` 로 나감) | yes ✓ (`microsoft.com` vs `akamaiedge.net`) |
| www.netflix.com | 1 | `www.prod.ftl.netflix.com` | `prod.ftl.netflix.com` | AS40027 Netflix | no — Netflix 자체 AS40027 (상위 /22 는 AS2906) | no ✓ (체인이 자기 도메인 안에서 끝나고 주소도 CDN AS 아님) | no ✓ (`netflix.com` vs `netflix.com`) |
| www.adobe.com | 2 | `www.adobe.com.edgesuite.net` → `a1319.dscr.akamai.net` | `dscr.akamai.net` | AS20940 Akamai | yes — Akamai. 일부 응답은 LG U+ 망(AS3786) 안의 Akamai 캐시 | yes ✓ (체인이 `akamai.net` 로 나감) | yes ✓ (`adobe.com` vs `akamai.net`) |
| www.cnn.com | 1 | `cnn-tls.map.fastly.net` | `fastly.net` | AS54113 Fastly | yes — Fastly (AS54113) | yes ✓ (체인이 `fastly.net` 로 나감) | yes ✓ (`cnn.com` vs `fastly.net`) |
| www.apple.com | 3 | `www-apple-com.v.aaplimg.com` → `www.apple.com.edgekey.net` → `e6858.dsce9.akamaiedge.net` | `dsce9.akamaiedge.net` | AS16625 Akamai | yes — Apple 의 aaplimg.com 이 Akamai 로 넘김 | yes ✓ (체인이 `akamaiedge.net` 로 나감) | yes ✓ (`apple.com` vs `akamaiedge.net`) |
| www.korea.ac.kr | 0 | (CNAME 없음) | `korea.ac.kr` | AS9452 Korea University | no — 고려대학교 자체 AS9452 | no ✓ (체인이 자기 도메인 안에서 끝나고 주소도 CDN AS 아님) | no ✓ (`ac.kr` vs `ac.kr`) |
| www.stanford.edu | 1 | `stanford.netlifyglobalcdn.com` | `netlifyglobalcdn.com` | AS16509 Amazon | yes — Netlify, AWS Global Accelerator 애니캐스트(AS16509) 위 | yes ✓ (체인이 `netlifyglobalcdn.com` 로 나감) | yes ✓ (`stanford.edu` vs `netlifyglobalcdn.com`) |
| www.bbc.co.uk | 2 | `www.bbc.co.uk.pri.bbc.co.uk` → `bbc.map.fastly.net` | `fastly.net` | AS54113 Fastly | yes — Fastly (AS54113) | yes ✓ (체인이 `fastly.net` 로 나감) | yes ✓ (`co.uk` vs `fastly.net`) |
| www.spotify.com | 1 | `atc.spotify.map.fastly.net` | `fastly.net` | AS54113 Fastly | yes — Fastly (AS54113) | yes ✓ (체인이 `fastly.net` 로 나감) | yes ✓ (`spotify.com` vs `fastly.net`) |
| www.github.com | 1 | `github.com` | `github.com` | AS8075 Microsoft | no — GitHub 자체. 한국에선 모회사 Azure(AS8075), 미국에선 GitHub AS36459 | no ✓ (체인이 자기 도메인 안에서 끝나고 주소도 CDN AS 아님) | no ✓ (`github.com` vs `github.com`) |
| www.wikipedia.org | 1 | `dyna.wikimedia.org` | `wikimedia.org` | AS14907 Wikimedia | no — Wikimedia 자체 캐시 데이터센터 (AS14907) | yes **✗** (체인이 `wikimedia.org` 로 나감) | yes **✗** (`wikipedia.org` vs `wikimedia.org`) |
| www.nytimes.com | 3 | `www.prd.map.nytimes.com` → `www.prd.map.nytimes.xovr.nyt.net` → `nytimes.map.fastly.net` | `fastly.net` | AS54113 Fastly | yes — Fastly (AS54113) | yes ✓ (체인이 `fastly.net` 로 나감) | yes ✓ (`nytimes.com` vs `fastly.net`) |

### 규칙

1. CNAME 체인을 끝까지 따라가 마지막 이름의 **등록 가능 도메인(eTLD+1)** 을 구한다. `co.uk`, `ac.kr` 처럼 두 레이블짜리 공용 접미사는 한 덩어리로 본다. 사이트의 eTLD+1 과 다르면 → 제3자.
2. 체인이 자기 도메인 안에서 끝나거나 CNAME 이 없으면, 최종 주소를 광고하는 AS 를 Team Cymru 에 DNS 로 묻는다. CDN 이 본업인 회사의 AS(Akamai, CDN77, Cloudflare, Edgio, Fastly) 이면 → 제3자. CNAME 없는 애니캐스트를 잡기 위한 단계다.
3. 둘 다 아니면 → 자체.

정답과 일치: **11 / 12**

### 규칙이 틀린 곳

- **www.wikipedia.org** — 규칙은 "체인이 `wikimedia.org` 로 나감" 라서 제3자로 판정했다. 그러나 `dyna.wikimedia.org` 의 주소 103.102.166.224 를 광고하는 것은 AS14907 WIKIMEDIA - Wikimedia Foundation Inc., US 이다. 정답: Wikimedia 자체 캐시 데이터센터 (AS14907). 한 조직이 서로 다른 등록 도메인 두 개를 쓰면, 이름만 보는 규칙은 같은 조직임을 알 수 없다.

마지막 두 레이블만 비교하는 규칙:

- **www.korea.ac.kr** — 우연히 맞음. 사이트의 "마지막 두 레이블" `ac.kr` 는 공용 접미사라서 이 규칙은 `ac.kr` 아래의 모든 조직을 같은 조직으로 본다. CNAME 이 같은 접미사의 다른 기관으로 갔다면 자체라고 잘못 판정했을 것이다.
- **www.bbc.co.uk** — 우연히 맞음. 사이트의 "마지막 두 레이블" `co.uk` 는 공용 접미사라서 이 규칙은 `co.uk` 아래의 모든 조직을 같은 조직으로 본다. CNAME 이 같은 접미사의 다른 기관으로 갔다면 자체라고 잘못 판정했을 것이다.
- **www.wikipedia.org** — 틀림. `wikipedia.org` ≠ `wikimedia.org` 이라 제3자라고 하지만 같은 운영 주체다.

## B2 · B3 · B5 · 스티어링

각 칸: 응답 주소를 광고하는 조직, 첫 주소(+나머지 개수), 그 열의 네트워크에서 잰 TCP/443 핸드셰이크 RTT 의 최솟값(ms) (ECS 열은 수집한 네트워크에서 잼). 리졸버마다 3번 물어 합집합을 냈고, ↻ 는 그 3번 사이에 집합이 바뀐 것(회전)이다.

| site | 3rd | home-wifi/system | home-wifi/google | home-wifi/quad9 | lte/system | lte/google | lte/quad9 | ecs-kr-campus/google | ecs-us-stanford/google |
|---|---|---|---|---|---|---|---|---|---|
| www.microsoft.com | yes | Akamai 104.75.39.192 · 9 | Akamai 104.75.39.192 · 9 | Akamai 23.35.101.225 +1 · 39 ↻ | Akamai 23.49.206.40 · 40 | Akamai 23.49.206.40 · 40 | Akamai 23.0.194.92 +1 · 65 ↻ | Akamai 23.49.206.40 · 40 | Akamai 23.49.206.40 · 40 |
| www.netflix.com | no | Netflix 207.45.72.1 +1 · 43 | Netflix 207.45.72.1 +1 · 43 | Netflix 207.45.72.1 +1 · 43 | Netflix 207.45.72.1 +1 · 66 | Netflix 207.45.72.1 +1 · 66 | Netflix 207.45.72.1 +1 · 66 | Netflix 207.45.72.1 +1 · 66 | Netflix 207.45.72.1 +1 · 66 |
| www.adobe.com | yes | Akamai 23.32.4.146 +7 · 9 | LG DACOM 182.162.106.137 +2 · 8 ↻ | Akamai 23.44.5.194 +6 · 39 ↻ | Akamai 23.32.4.34 +8 · 36 | Akamai 23.35.218.227 +1 · 35 | Akamai 23.62.21.78 +3 · 66 ↻ | Akamai 23.35.218.227 +1 · 35 | Akamai 23.35.218.227 +1 · 35 |
| www.cnn.com | yes | Fastly 146.75.51.5 · 9 | Fastly 151.101.3.5 +3 · 11 | Fastly 151.101.3.5 +3 · 11 | Fastly 146.75.51.5 · 27 | Fastly 151.101.3.5 +3 · 37 | Fastly 151.101.3.5 +3 · 37 | Fastly 151.101.3.5 +3 · 37 | Fastly 151.101.3.5 +3 · 37 |
| www.apple.com | yes | Akamai 23.41.89.203 +1 · 10 ↻ | Akamai 104.115.218.183 · 72 | Akamai 23.197.225.61 +1 · 42 ↻ | Akamai 23.49.205.28 · 40 | Akamai 23.49.205.28 +1 · 40 ↻ | Akamai 23.0.193.49 +1 · 56 ↻ | Akamai 23.49.205.28 +2 · 40 ↻ | Akamai 23.49.205.28 +1 · 40 ↻ |
| www.korea.ac.kr | no | Korea University 163.152.6.10 · 11 | Korea University 163.152.6.10 · 11 | Korea University 163.152.6.10 · 11 | Korea University 163.152.6.10 · 42 | Korea University 163.152.6.10 · 42 | Korea University 163.152.6.10 · 42 | Korea University 163.152.6.10 · 42 | Korea University 163.152.6.10 · 42 |
| www.stanford.edu | yes | Amazon 3.33.186.135 +1 · 10 | Amazon 3.33.186.135 +1 · 10 | Amazon 3.33.186.135 +1 · 10 | Amazon 3.33.186.135 +1 · 52 | Amazon 3.33.186.135 +1 · 52 | Amazon 3.33.186.135 +1 · 52 | Amazon 3.33.186.135 +1 · 52 | Amazon 3.33.186.135 +1 · 52 |
| www.bbc.co.uk | yes | Fastly 146.75.48.81 · 9 | Fastly 151.101.0.81 +3 · 11 | Fastly 151.101.0.81 +3 · 11 | Fastly 146.75.48.81 · 40 | Fastly 151.101.0.81 +3 · 29 | Fastly 151.101.0.81 +3 · 29 | Fastly 151.101.0.81 +3 · 29 | Fastly 151.101.0.81 +3 · 29 |
| www.spotify.com | yes | Fastly 146.75.51.42 · 9 | Fastly 151.101.3.42 +3 · 10 | Fastly 151.101.3.42 +3 · 10 | Fastly 146.75.51.42 · 34 | Fastly 151.101.3.42 +3 · 39 | Fastly 151.101.3.42 +3 · 39 | Fastly 151.101.3.42 +3 · 39 | Fastly 151.101.3.42 +3 · 39 |
| www.github.com | no | Microsoft 20.200.245.247 · 10 | Microsoft 20.200.245.247 · 10 | Microsoft 20.205.243.166 · 74 | Microsoft 20.200.245.247 · 52 | Microsoft 20.200.245.247 · 52 | Microsoft 20.27.177.113 · 59 | Microsoft 20.200.245.247 · 52 | GitHub 140.82.116.3 · 295 |
| www.wikipedia.org | no | Wikimedia 103.102.166.224 · 120 | Wikimedia 103.102.166.224 · 120 | Wikimedia 103.102.166.224 · 120 | Wikimedia 103.102.166.224 · 92 | Wikimedia 103.102.166.224 · 92 | Wikimedia 103.102.166.224 · 92 | Wikimedia 103.102.166.224 · 92 | Wikimedia 198.35.26.224 · 176 |
| www.nytimes.com | yes | Fastly 146.75.49.164 · 9 | Fastly 151.101.1.164 +3 · 11 | Fastly 151.101.1.164 +3 · 11 | Fastly 146.75.49.164 · 46 | Fastly 151.101.1.164 +3 · 37 | Fastly 151.101.1.164 +3 · 37 | Fastly 151.101.1.164 +3 · 37 | Fastly 151.101.1.164 +3 · 37 |

### 스티어링 수치 (B5)

네트워크: `home-wifi` (LG POWERCOMM, AS17858) · `lte` (SK Telecom, AS9644), ECS 흉내 `ecs-kr-campus` (163.152.0.0/24) · `ecs-us-stanford` (171.64.0.0/24).

제3자 CDN 사이트 N = **8** (사람 판정 기준: microsoft.com, adobe.com, cnn.com, apple.com, stanford.edu, bbc.co.uk, spotify.com, nytimes.com).

- **7 / 8** 사이트가 다른 resolver 나 다른 네트워크에 다른 주소 집합으로 응답했다.
  - 같은 네트워크(`home-wifi`, `lte`)에서 resolver 만 바꿨을 때: **7 / 8** — 그중 /24 가 하나도 겹치지 않는 것: 7 / 8
  - 관측 지점(`home-wifi`, `lte`, `ecs-kr-campus`, `ecs-us-stanford`)을 바꿨을 때 (같은 resolver 끼리): **3 / 8** — 그중 /24 가 하나도 겹치지 않는 것: 3 / 8
  - 같은 resolver 에 3번 물었는데 집합이 바뀐 것(회전): 3 / 8 — "다르다"의 일부는 위치가 아니라 로드밸런싱이다.

- ECS `163.152.0.0/24` (`ecs-kr-campus`) 로 답이 `lte/google` 과 다른 /24 로 옮겨 간 사이트: 제3자 CDN 0 / 8, 나머지 0 / 4
- ECS `171.64.0.0/24` (`ecs-us-stanford`) 로 답이 `lte/google` 과 다른 /24 로 옮겨 간 사이트: 제3자 CDN 0 / 8, 나머지 2 / 4 (www.github.com, www.wikipedia.org)

가까움 — 사이트별로 본 모든 복제 서버 중 가장 빠른 것보다 5 ms 이내인 답을 준 횟수, 그리고 그 답의 RTT 중앙값 (각 열의 네트워크에서 측정):

| 관측 지점 | 가까운 답 | RTT 중앙값 (ms) |
|---|---:|---:|
| `home-wifi/system` | 8 / 8 | 9 |
| `home-wifi/google` | 7 / 8 | 10 |
| `home-wifi/quad9` | 5 / 8 | 11 |
| `lte/system` | 5 / 8 | 40 |
| `lte/google` | 6 / 8 | 38 |
| `lte/quad9` | 4 / 8 | 45 |
| `ecs-kr-campus/google` | 6 / 8 | 38 |
| `ecs-us-stanford/google` | 6 / 8 | 38 |

### 두 네트워크 교차 비교 (B3) — `home-wifi` 와 `lte`

두 네트워크의 system resolver 가 서로 다른 답을 준 제3자 CDN 사이트에서, 각 네트워크가 받은 답과 상대가 받은 답까지의 RTT 를 **같은 네트워크에서** 잰 것. 주장 (b) 가 맞다면 "내 답"이 "남의 답"보다 가까워야 한다.

| site | `home-wifi` 에서: 내 답 / 남의 답 | `lte` 에서: 내 답 / 남의 답 |
|---|---|---|
| www.microsoft.com | 9 / 10 ≈ 차이 없음 | 40 / 38 ≈ 차이 없음 |
| www.adobe.com | 9 / 9 ≈ 차이 없음 | 36 / 26 ✗ 남의 답이 가까움 |
| www.apple.com | 10 / 9 ≈ 차이 없음 | 40 / 45 ✓ 내 답이 가까움 |

system resolver 가 네트워크마다 다른 답을 준 사이트 **3 / 8**, 그 비교 6번 중 내 답이 5 ms 넘게 가까움 **1**, 차이 없음 4, 남의 답이 더 가까움 **1** (나머지 5개는 두 네트워크에 같은 주소를 줬다 — 애니캐스트이거나 같은 PoP).
