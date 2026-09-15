# Task 3 구현 메모: TTL 캐시

이 구현은 `bench.py`를 바꾸지 않고 authoritative answer가 준 TTL을 그대로
사용한다. cache entry는 이름을 key로 하고 `(address, expires_at)`을 value로 하는
dictionary에 저장한다. `now < expires_at`일 때만 hit이며, 정확히 만료 시각에
도달하면 다시 조회한다. TTL이 0 이하인 답은 현재 호출에는 반환하지만 저장하지
않는다.

## baseline의 문제

baseline은 모든 TTL을 버리고 60초를 사용한다. 이 한 원인 때문에 두 문제가
생긴다.

- 20초와 30초 TTL 레코드를 60초 동안 보관해 만료된 답을 반환하는 정확성 문제
- 60초보다 긴 TTL 레코드를 너무 일찍 버려 upstream 질의를 늘리는 성능 문제

list를 선형 검색하는 비용도 있지만 위 두 TTL 문제와는 별개의 자료구조 문제다.
가장 나쁜 레코드는 TTL 20초이면서 질의 빈도가 가장 높은
`www.microsoft.com`이다. baseline stale 266개 중 189개를 만든다.

## 최저 upstream 횟수

고정 workload에서 올바른 cache의 최저값은 275회다. 각 이름의 첫 질의에는
upstream 답이 필요하고, 그 답의 TTL이 끝난 뒤 처음 들어온 질의에도 새 답이
필요하다. 다음 질의까지 기다렸다가 가져오는 것이 가장 늦은 만료 시각을 주므로
미리 가져와도 호출 수를 줄일 수 없다. 이전 답을 재사용하면 stale이 된다.

```text
upstream 275
hit rate 72.5%
stale 0
sim time 5.5s
```

레코드별 최저 호출 수는 microsoft 118, cnn 76, netflix 37, spotify 23,
github 11, wikipedia 6, korea 1, stanford 1, dns.google 1, root server 1이며
합계가 275다.

## 실행과 관찰

```bash
python3 -m unittest -v test_task3_cache.TestTask3Cache
python3 bench.py --yours | tee out/bench.txt
python3 test_tasks.py --task 3
```

`out/observation.md`에는 baseline의 정확성 문제와 성능 문제를 따로 쓰고, 275보다
낮출 수 없는 이유와 microsoft 레코드가 가장 나쁜 이유를 기록한다.
