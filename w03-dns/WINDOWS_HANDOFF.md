# Week 03 DNS · Windows 작업 인계

이 문서는 macOS에서 작성한 `w03-dns` 구현을 Windows에서 이어서 측정하고
제출 준비하기 위한 진행 기록이다. 현재 작업 브랜치는 `feature/03-dns`이다.

## Git 상태와 원격 저장소

- 개인 저장소(`origin`): `https://github.com/FIo-g/computer_network.git`
- 강의 저장소(`upstream`):
  `https://github.com/codingchild2424/2026-lecture-network-practice.git`
- 구현 완료 지점: `d879677` (`test: cover DNS steering validation guards`)
- 강의에서 제공한 요구사항 문서, `bench.py`, `test_tasks.py`, `check.py`는
  수정하지 않았다.
- 이 문서까지 포함한 최신 커밋 hash는 `git log -1 --oneline`으로 확인한다.

현재 이 브랜치는 개인 GitHub 원격에 아직 올라가지 않았다. Windows로 이동하기
전에 현재 Mac에서 다음 명령을 실행해야 한다.

```bash
git push -u origin feature/03-dns
```

## 완료된 구현

### Task 1 · 반복 DNS 리졸버

- `task1_resolve.py`에 루트 서버부터 시작하는 반복 조회를 구현했다.
- 모든 DNS 서버 질의는 `dig +norecurse`를 사용한다.
- Answer, Authority, Additional 섹션을 구분하며 glue가 없는 NS 이름도 직접
  해결한다.
- 서버 재시도, CNAME 재시작, 순환 방지, 전체 질의 횟수 제한을 구현했다.
- 자세한 설명은 `task1_README.md`에 있다.

### Task 2 · DNS steering 측정 도구

- 12개 사이트의 CNAME chain, authoritative zone, 세 resolver의 IPv4 주소를
  수집한다.
- 동일 파일에 서로 다른 두 네트워크의 결과를 합치고, 실수로 같은 네트워크
  이름을 덮어쓰지 않는다.
- 불완전하거나 사람이 확인하지 않은 자료로는 보고서를 생성하지 않는다.
- 캡처 증거, 사이트별 CDN/제3자 판단과 steering 결론은 사용자가 직접 작성해야
  한다.
- 자세한 측정·증거 형식은 `task2_README.md`에 있다.

### Task 3 · TTL cache

- authoritative TTL을 사용하고 `now < expires_at`인 경우에만 cache hit로
  처리한다.
- 정확히 만료된 시각에는 upstream을 다시 조회하고 TTL이 0 이하이면 저장하지
  않는다.
- 자세한 최저 호출 수 계산은 `task3_README.md`에 있다.

## 완료된 자동 검증

마지막 검증 결과는 다음과 같다.

```text
단위 테스트       36 passed, 0 failed
Task 3 upstream   275
Task 3 cache hit  725
Task 3 stale      0
Task 3 sim time   5.5s
제공 harness      2 passed, 0 failed, 1 human-review skip
SOL 최종 검토     Critical 0, Important 0, Minor 0
```

Task 3의 skip 한 건은 오류가 아니라 `out/observation.md`의 최저 호출 수 논증을
사람이 평가하는 항목이다.

## Windows에서 브랜치 받기

GitHub에 브랜치를 push한 뒤 Windows PowerShell에서 새로 clone하려면 다음을
실행한다.

```powershell
git clone https://github.com/FIo-g/computer_network.git
cd computer_network
git fetch origin
git switch --track origin/feature/03-dns
git remote add upstream https://github.com/codingchild2424/2026-lecture-network-practice.git
```

`upstream`이 이미 존재한다면 마지막 명령은 생략한다. Windows에 저장소가 이미
있다면 다음처럼 갱신한다.

```powershell
git fetch origin
git switch feature/03-dns
git pull --ff-only
```

## Windows에서 결정론적 테스트 다시 실행

Docker Desktop을 실행한 뒤 저장소 루트에서 다음 명령을 실행한다.

```powershell
docker compose build
docker compose run --rm lab
```

열린 Ubuntu shell 안에서 실행한다.

```bash
cd w03-dns
python3 -m unittest -v test_task1_resolve test_task2_steering test_task3_cache
python3 bench.py --yours | tee out/bench.txt
python3 test_tasks.py --task 3
```

예상 결과는 단위 테스트 36개 통과, Task 3의 275 upstream과 0 stale이다.

## Windows에서 직접 해야 하는 작업

### 1. Task 1 실제 네트워크 확인

허가된 네트워크에서 컨테이너 안의 `w03-dns` 폴더에서 실행한다.

```bash
python3 task1_resolve.py --verify
```

직접 DNS 53번 포트가 차단된 네트워크에서는 실패할 수 있다. 이 경우 실패를
숨기지 말고 `task1_README.md`와 `../traces/README.md`의 공식 trace 경로를
검토한다.

### 2. Wireshark 캡처

Wireshark는 Windows host에서 실행한다. 실제 사용 중인 인터페이스를 선택하고
capture filter를 `port 53`으로 설정한다. 다른 앱을 최대한 종료한 뒤 컨테이너에서
다음을 한 번 실행한다.

```bash
python3 task1_resolve.py www.korea.ac.kr
```

캡처를 짧게 끝내고 Windows의 저장소 경로 아래
`w03-dns\out\dns.pcapng`로 저장한다. 제출 전 반드시 unrelated DNS 요청이나
개인정보가 포함되지 않았는지 확인한다. 정리할 수 없다면 파일을 삭제하고 다시
캡처하거나 공식 trace 경로를 사용한다.

캡처에서 직접 확인할 내용은 다음과 같다.

- 같은 transaction ID를 가진 query/response packet 번호
- Authority 섹션에 NS가 있는 delegation response packet 번호
- 최종 A answer가 있는 response packet 번호
- 가장 큰 응답의 packet 번호, DNS message byte, 전체 frame byte
- 그 응답이 커진 이유(예: Authority 및 Additional 레코드)

### 3. 서로 다른 두 네트워크 측정

첫 번째 네트워크에서 다음을 실행한다. label은 실제 네트워크를 설명하는 이름을
사용한다.

```bash
python3 task2_steering.py --collect --network home-wifi
```

Windows PC를 두 번째로 사용 허가를 받은 네트워크로 실제 전환한 뒤 실행한다.

```bash
python3 task2_steering.py --collect --network phone-tethering
```

같은 label을 다시 사용하면 덮어쓰기를 막기 위해 실패한다. 재측정이 명확히
필요할 때만 `--replace`를 추가한다. 강의 시설에 부하 테스트를 실행하거나 다른
사람의 네트워크를 측정하면 안 된다.

### 4. 사람이 작성할 증거와 보고서

`task2_README.md`를 참고하여 `out/task2_evidence.json`을 작성한다.

- 12개 사이트 각각의 `cdn_hosted`, `third_party`, `reason`
- 두 실제 네트워크에 관한 설명
- 위에서 확인한 packet 번호와 크기
- 주소 차이가 의미하는 것과 anycast/cache/load balancing이라는 한계
- 자동 제3자 판정 규칙과 실제 판단이 다른 사이트 최소 한 개

작성 후 다음을 실행한다.

```bash
python3 task2_steering.py --report
```

코드는 자료가 불완전하거나 캡처 출처가 확인되지 않으면 보고서 생성을 거부한다.

### 5. 관찰문과 최종 검사

`out/observation.md`에 Task별 2~3줄을 실제 관찰을 바탕으로 작성한다. Task 3에는
올바른 cache가 이 workload에서 275 upstream보다 낮아질 수 없는 이유를 포함한다.

```bash
python3 test_tasks.py
python3 ../check.py w03
```

공식 trace 경로에는 알려진 검사 불일치가 있다. `check.py`는 pcap을 선택 사항으로
취급하지만 `test_tasks.py`는 `out/dns.pcapng`가 없으면 실패한다. 강의 harness를
수정하지 말고 공식 trace를 사용했다는 출처를 보고서에 정확히 기록한다.

## Git으로 자동 동기화되지 않는 파일

`.gitignore`가 모든 주차의 `out/` 폴더를 제외한다. 따라서 아래 파일은 commit이나
push로 Windows와 다른 PC 사이에 자동 동기화되지 않는다.

```text
w03-dns/out/bench.txt
w03-dns/out/dns.pcapng
w03-dns/out/chains.json
w03-dns/out/task2_evidence.json
w03-dns/out/report.md
w03-dns/out/observation.md
```

특히 packet capture에는 개인정보가 들어갈 수 있으므로 무심코 `git add -f`로
공개 저장소에 올리지 않는다. 컴퓨터를 다시 옮겨야 한다면 개인정보 검토 후
안전한 개인 저장장치로 별도 전송한다.

## 최종 제출 전 체크리스트

- [ ] `feature/03-dns` 브랜치인지 확인했다.
- [ ] 결정론적 테스트 36개가 통과했다.
- [ ] Task 1 `--verify` 결과를 확인했다.
- [ ] 짧은 DNS 캡처의 개인정보를 검토했다.
- [ ] 실제 서로 다른 두 네트워크 측정이 `chains.json`에 들어 있다.
- [ ] 12개 사이트의 분류와 근거를 직접 작성했다.
- [ ] `report.md`를 생성했다.
- [ ] `observation.md`에 Task별 2~3줄을 작성했다.
- [ ] `test_tasks.py`와 `../check.py w03` 결과를 읽고 확인했다.
