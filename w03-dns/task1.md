# Task 1 · Build Your Own Iterative Resolver

**File** — `task1_resolve.py`
**Theory** — §2.4.2 DNS hierarchy, §2.4.3 DNS records
**Kind** — implementation · can be done entirely in code

---

## What you are building

`dig +trace` walks root → TLD → authoritative for you. In this task you do that walk
yourself: start at a root server, read the delegation it returns, ask the next server,
and keep going until somebody answers authoritatively.

You may shell out to `dig` for transport or use `dnspython` (it is in the container).
What matters is that **you** follow the delegations. The flag that stops a server from
doing the work for you is `+norecurse`:

```bash
dig @198.41.0.4 www.korea.ac.kr +norecurse
```

## Requirements

| # | Requirement |
|---|---|
| R1 | `Resolver.resolve(name)` returns `(address, path)` where `path` is the servers you asked, in order |
| R2 | You start at a root server in `ROOT_SERVERS`. No recursive query to anyone's resolver |
| R3 | Handle a delegation that arrives **without glue** — you must resolve the nameserver's own name first |
| R4 | Handle a server that does not answer: move to the next one rather than failing |
| R5 | Handle `CNAME`: if the answer is for a different name, restart the walk with that name |
| R6 | Cap the depth. A malformed zone must not hang you forever |

R3 and R6 are the ones people skip. R3 is where the recursion in "recursive resolver"
actually comes from.

## Pass condition

```bash
python3 task1_resolve.py --verify
```

Five names are resolved by your resolver and by `dig`, and the addresses must agree.

```
  ok    www.korea.ac.kr        you=163.152.6.10    dig=163.152.6.10   hops=3
```

A CDN-hosted name may legitimately return a different address on each query. If that is
what happened, that is not a failure — record it in `observation.md` and say why you know
the difference.

Run the whole week's checks with:

```bash
python3 test_tasks.py
```

## What to write in `observation.md`

- Why did the root server not simply hand you the address?
- What did you do when a delegation arrived **without glue**, and how many extra
  lookups did that cost you?
- How many servers did you end up asking for one name? Compare that with the single
  question your laptop normally asks its resolver.

---

## 한국어 번역본 (Korean Translation)

# 과제 1 · 직접 반복적 리졸버 만들기

**파일** — `task1_resolve.py`
**이론** — §2.4.2 DNS 계층 구조, §2.4.3 DNS 레코드
**종류** — 구현 · 코드만으로 완전히 수행 가능

---

## 만드는 것

`dig +trace`는 루트 → TLD → 권한 서버를 대신 탐색해 줍니다. 이 과제에서는 그 탐색을
직접 수행합니다: 루트 서버에서 시작해 반환된 위임을 읽고, 다음 서버에 질의하고,
권한 있는 응답을 받을 때까지 계속 진행합니다.

전송을 위해서는 `dig`를 사용하거나 `dnspython`(컨테이너에 포함됨)을 사용해도 됩니다.
중요한 것은 **여러분이** 위임을 직접 따라가는 것입니다. 서버가 대신 작업을 수행하지
못하도록 막는 플래그는 `+norecurse`입니다:

```bash
dig @198.41.0.4 www.korea.ac.kr +norecurse
```

## 요구 사항

| # | 요구 사항 |
|---|---|
| R1 | `Resolver.resolve(name)`은 `(address, path)`를 반환하며, `path`는 순서대로 질의한 서버들 |
| R2 | `ROOT_SERVERS`의 루트 서버에서 시작. 누구의 리졸버에게도 재귀 질의 금지 |
| R3 | 글루 **없이** 도착한 위임 처리 — 네임서버 자신의 이름을 먼저 해석해야 함 |
| R4 | 응답하지 않는 서버 처리: 실패로 끝내지 말고 다음 서버로 이동 |
| R5 | `CNAME` 처리: 답이 다른 이름에 대한 것이면 그 이름으로 탐색을 다시 시작 |
| R6 | 깊이에 상한을 둠. 잘못된 존 때문에 영원히 멈추지 않아야 함 |

R3와 R6이 사람들이 건너뛰는 항목입니다. "재귀 리졸버"의 재귀가 실제로 나오는 곳이 R3입니다.

## 통과 조건

```bash
python3 task1_resolve.py --verify
```

5개의 이름을 여러분의 리졸버와 `dig`로 각각 해석하며, 주소가 일치해야 합니다.

```
  ok    www.korea.ac.kr        you=163.152.6.10    dig=163.152.6.10   hops=3
```

CDN에 호스팅된 이름은 질의마다 정당하게 다른 주소를 반환할 수 있습니다. 그런 경우라면
실패가 아닙니다 — `observation.md`에 기록하고 왜 다르다고 확신하는지 설명하세요.

전체 주간 검사는 다음으로 실행합니다:

```bash
python3 test_tasks.py
```

## `observation.md`에 쓸 것

- 루트 서버가 왜 주소를 그냥 주지 않았는지?
- 글루 **없이** 위임이 도착했을 때 무엇을 했으며, 그 때문에 추가 조회가 몇 번 들었는지?
- 하나의 이름에 대해 결국 몇 대의 서버에 질의했는지? 평소 노트북이 리졸버에게 묻는
  단 한 번의 질문과 비교하세요.
