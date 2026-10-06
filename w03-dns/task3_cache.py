#!/usr/bin/env python3
"""Week 3 · Task 3 — 기준 캐시를 뛰어넘으세요.

교재 §2.4.2 (캐싱)와 §2.4.3 (TTL).

아래 `BaselineCache`는 동작합니다. 하지만 여러 면에서 나쁘며, 그중 한 문제는
느리다는 것보다 더 심각합니다. 문제점을 찾고, `YourCache`를 작성하고,
하네스로 개선을 증명하세요:

    python3 bench.py                 # 기준선만 실행
    python3 bench.py --yours         # 기준선과 여러분 것을 나란히 비교

규칙
-----
* `bench.py`를 바꾸지 마세요. 고쳐야 이긴다면 이긴 것이 아닙니다.
  대신 그 사실을 observation.md에 적으세요.
* `YourCache`는 `BaselineCache`와 같은 두 메서드를 제공해야 합니다.
* 속도만이 평가 기준이 아닙니다. 하네스는 **만료된 답변**도 셉니다 -
  TTL이 이미 지난 레코드를 제공한 횟수입니다. 모든 것을 영원히 보관하는 캐시는
  매우 빠르지만 완전히 틀린 것입니다.

목표
-------
기준선은 **업스트림 쿼리 325회, 적중률 67.5%, 만료된 답변 266개**를 기록합니다.

  통과 : 만료된 답변 0개
  양호 : 만료 0개, 그리고 기준선과 같거나 더 적은 업스트림 쿼리 수
  우수 : 위 조건을 모두 만족하고, observation.md에 **이 워크로드에서 올바른 캐시가 만들 수 있는
        최소 업스트림 쿼리 수는 몇 개이며, 왜 그 이하로 내려갈 수 없는지**를 설명할 수 있음

마지막 항목이 진짜 질문입니다. 최적화를 시작하기 전에 읽어보세요 -
어디서 멈춰야 하는지 알려줍니다.
"""
import time


class BaselineCache:
    """누군가 급하게 작성한 DNS 캐시입니다.

    캐싱 동작은 하지만, 정확하지도 빠르지도 않습니다. 둘 다 여러분이 해결할 문제입니다.
    """

    FIXED_LIFETIME = 60          # TTL과 무관하게 보관하는 시간(초)

    def __init__(self, upstream):
        self.upstream = upstream  # upstream(name) -> (address, ttl)
        self.entries = []         # [이름, 주소, 저장 시각] 목록

    def lookup(self, name, now):
        """`name`에 대한 주소를 반환하며, 필요할 때만 업스트림에 물어봅니다."""
        for entry in self.entries:                      # 선형 탐색
            if entry[0] == name:
                if now - entry[2] < self.FIXED_LIFETIME:
                    return entry[1]
                self.entries.remove(entry)
                break
        address, ttl = self.upstream(name)
        self.entries.append([name, address, now])
        return address

    def stats(self):
        return {"entries": len(self.entries)}


class YourCache:
    """여러분의 캐시.

    같은 인터페이스입니다: __init__(upstream), lookup(name, now) -> address, stats().
    `upstream(name)` 호출은 네트워크 왕복 비용이 들고 (address, ttl)을 반환합니다.
    TTL은 초 단위이며 권한 답변 자체의 TTL입니다 -
    기준선은 이것을 버립니다.
    """

    def __init__(self, upstream):
        self.upstream = upstream
        # name -> (address, expires_at). expires_at = fetch_time + ttl.
        self.entries = {}

    def lookup(self, name, now):
        hit = self.entries.get(name)
        if hit is not None:
            address, expires_at = hit
            if now <= expires_at:
                return address
        address, ttl = self.upstream(name)
        self.entries[name] = (address, now + ttl)
        return address

    def stats(self):
        return {"entries": len(self.entries)}
