# Task 1 구현 메모: 반복 DNS 리졸버

이 파일은 강의 지시문 `task1.md`를 바꾸지 않고 구현 선택과 실행 방법을 설명한다.

## 동작 방식

`Resolver.resolve(name)`은 루트 서버에서 시작한다. 각 서버에는 반드시
`+norecurse`로 질의하며, 응답의 authority 섹션에 있는 NS 위임을 다음 단계로
따라간다. answer 섹션의 authoritative A 레코드에 도달해야 주소를 반환한다.
additional 섹션의 A 레코드는 NS 접착(glue) 주소로만 사용하고 최종 답으로
사용하지 않는다.

위임된 NS 이름에 glue가 없으면 그 NS 이름을 루트부터 별도로 반복 조회한다.
이때 발생한 질의도 `path`에 실제 순서대로 기록한다. 서버가 응답하지 않으면
같은 위임의 다음 서버를 시도한다. CNAME을 만나면 대상 이름으로 루트부터 다시
시작한다. 전체 질의 예산은 기본 32회이며 이름 순환도 별도로 차단한다.

## 실행

```bash
python3 task1_resolve.py www.korea.ac.kr
python3 task1_resolve.py --verify
python3 -m unittest -v test_task1_resolve.TestTask1Resolver
```

`--verify`는 실제 DNS 네트워크를 사용한다. 사용자가 허가한 네트워크에서만
실행한다. CDN 주소가 연속 질의 사이에 달라진 경우 `out/observation.md`에 그
사실과 CDN의 복수 replica 응답 때문이라고 판단한 근거를 기록한다.

## 관찰 기록

Task 1 관찰에는 루트가 주소 대신 위임을 준 이유, glue 없는 NS를 해결한 방법과
추가 질의 수, 한 이름에 실제로 물어본 서버 수를 포함한다. 일반 노트북은 보통
로컬 재귀 리졸버에 한 번만 묻는다는 점과 직접 수행한 반복 질의를 비교한다.

네트워크가 직접 질의를 막으면 `README.md`와 `traces/README.md`의 공식 trace
경로를 따른다. 이 경우에도 코드는 반복 조회 규칙을 구현하며, 실제 검증이
건너뛰어졌다는 사실을 숨기지 않는다.
