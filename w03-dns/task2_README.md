# Task 2 측정 메모: DNS steering

이 파일은 강의 지시문을 보충한다. 코드는 자료를 수집하고 계산할 수 있지만,
사용자의 실제 packet capture와 두 네트워크를 대신 만들거나 관찰 내용을 추측하지
않는다.

## 직접 해야 하는 단계

1. 사용 중인 인터페이스에서 Wireshark capture filter `port 53`을 적용한다.
2. 다른 앱을 닫고 `python3 task1_resolve.py www.korea.ac.kr`를 실행한다.
3. 짧게 캡처한 뒤 조회 이름에 개인정보가 없는지 확인하고 `out/dns.pcapng`로
   저장한다.
4. 같은 transaction ID의 query/response, authority NS가 있는 delegation 응답,
   answer A가 있는 최종 응답의 packet 번호를 기록한다.
5. 가장 큰 응답의 DNS message byte와 frame byte를 모두 기록하고, authority 및
   additional 레코드처럼 크기를 키운 내용을 설명한다.
6. 서로 다른 두 네트워크에서 아래 수집 명령을 각각 실행한다.

```bash
python3 task2_steering.py --collect --network campus-wifi
python3 task2_steering.py --collect --network phone-tethering
```

같은 label은 실수로 덮어쓰지 않는다. 의도적으로 다시 잴 때만 `--replace`를
붙인다. `network-1`은 호환용 기본값이라 최종 보고서에는 사용할 수 없다.

## 원시 자료와 사람의 증거

`out/chains.json`은 12개 사이트를 최상위 key로 두고, 각 사이트의
`measurements` 아래에 network별 `chain`, `original_zone`, `final_zone`,
`resolver_addresses`, `errors`를 보관한다. chain length는 이름 수가 아니라
CNAME 간선 수인 `len(chain) - 1`이다. `errors`가 남거나 세 resolver 주소 중
하나라도 비어 있으면 보고서를 만들지 않는다.

`out/task2_evidence.json`은 사용자가 캡처를 직접 보고 작성한다. 최상위 key는
`capture`, `network_notes`, `classifications`, `steering_conclusion`이다.
`classifications`에는 12개 사이트가 모두 있어야 하며 각 값은 boolean
`cdn_hosted`, boolean `third_party`, 비어 있지 않은 `reason`을 가진다.
Netflix 같은 자체 CDN은 `cdn_hosted`와 `third_party`가 서로 다를 수 있다.

자동 규칙은 원본 authoritative zone과 최종 authoritative zone이 다르면 제3자
서비스라고 판정한다. 표의 `third party?`는 사용자가 검토한 소유 관계이고
`rule verdict`는 이 자동 규칙이다. 둘이 다른 사이트가 적어도 하나 있어야 하며
그 이유를 `reason`에 쓴다.

`capture`에는 `source_type`, matched query/response packet, `transaction_id`,
delegation/answer response packet, largest response의 packet, `dns_message_bytes`,
`frame_bytes`, `reason`을 기록한다. `source_type`이 `own-capture`이면 실제
`out/dns.pcapng`가 필요하다.

## 보고서

```bash
python3 task2_steering.py --report
```

보고서는 CDN으로 검토된 N개 중 서로 다른 `(network, resolver)` 주소 집합이
관측된 사이트 수 X를 센다. 주소가 다르다는 사실은 steering과 일치하는
증거이지만 replica가 실제로 가깝다는 증명은 아니다. resolver cache, 시간에
따른 load balancing, anycast를 결론의 한계로 검토한다.

## 공식 trace 경로

직접 캡처가 막히면 `traces/README.md`의 9판 공식 trace와 정확한 출처 표기를
사용한다. 이 경우 `source_type`은 `official-trace`이고
`whose_machine_and_evidence`와 아래 문자열 그대로의 `attribution`이 필요하다.

```text
Wireshark lab trace files from J.F. Kurose and K.W. Ross,
*Computer Networking: A Top-Down Approach*, 9th ed.
<https://gaia.cs.umass.edu/kurose_ross/>
Copyright 1996-2025 J.F. Kurose, K.W. Ross. All Rights Reserved.
```

`check.py`는 이 경로에서 pcap을 선택 사항으로 보지만 `test_tasks.py`는 파일이
없으면 실패한다. harness는 수정하지 않는다. 공식 파일을 예상 경로로 복사하거나
변환했다면 보고서에서 공식 trace임을 명확히 밝힌다. Google과 Quad9은 anycast라
지리적으로 먼 두 resolver라고 자동으로 간주하지 않는다.
