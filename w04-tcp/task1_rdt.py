#!/usr/bin/env python3
"""Week 4 · Task 1 — 신뢰할 수 없는 채널 위에 신뢰적 전송을 만드세요.

교재 §3.4 (신뢰적 데이터 전송)와 §3.5 (TCP의 순서 번호).

아래 `UnreliableChannel`은 패킷을 잃어버리고, 순서를 바꾸고, 복제하고, 지연시킵니다.
§3.4가 모델링하는 네트워크 그대로입니다. 여러분이 할 일은 파일 하나를 이 채널 너머로
옮겨서, 바이트가 온전히 그리고 순서대로 도착하게 하는 것입니다.

혼잡 제어를 뺀 TCP 신뢰성 이야기의 전부이며, 소켓을 다시 믿기 전에 한 번은 손으로
만들어 볼 가치가 있습니다.

    python3 task1_rdt.py --verify
"""
import argparse, hashlib, random

PAYLOAD = 8            # 패킷당 바이트 - 순서 번호가 눈에 보이도록 작게


class UnreliableChannel:
    """10%를 잃고, 3%를 복제하고, 순서를 바꾸고, 지연시킵니다. 시드로 결정됩니다.

    더 친절하게 만들면 안 됩니다. 내부를 읽어도 안 됩니다. 여러분의 송신자가
    수신자에게 닿는 유일한 길입니다.
    """

    def __init__(self, seed=246, loss=0.10, dup=0.03, reorder=0.10):
        self.rng = random.Random(seed)
        self.loss, self.dup, self.reorder = loss, dup, reorder
        self.wire = []          # 전송 중인 패킷, 순서 보장 없음
        self.stats = {"sent": 0, "lost": 0, "duplicated": 0, "delivered": 0}

    def send(self, packet):
        """패킷을 네트워크에 넘깁니다. 영영 나오지 않을 수도 있습니다."""
        self.stats["sent"] += 1
        if self.rng.random() < self.loss:
            self.stats["lost"] += 1
            return
        copies = 2 if self.rng.random() < self.dup else 1
        self.stats["duplicated"] += copies - 1
        for _ in range(copies):
            if self.rng.random() < self.reorder and self.wire:
                self.wire.insert(self.rng.randrange(len(self.wire)), packet)
            else:
                self.wire.append(packet)

    def receive(self):
        """다음 패킷을 꺼냅니다. 네트워크에 아무것도 없으면 None."""
        if not self.wire:
            return None
        self.stats["delivered"] += 1
        return self.wire.pop(0)


class Sender:
    """여러분의 송신자.

    요구 사항은 task1.md에 있습니다. 짧게 말하면:

      - `data`를 PAYLOAD 크기 조각으로 나누고 번호를 붙일 것
      - 확인받지 못한 것은 재전송할 것
      - ACK에 적힌 번호를 확인하기 전까지는, 그 ACK가 여러분이 생각하는 의미라고
        가정하지 말 것

    프로토콜은 여러분이 고릅니다: 정지-대기(stop-and-wait)는 맞게 만들기 가장 쉽고
    가장 느립니다. 슬라이딩 윈도가 §3.4.3의 핵심입니다. 무엇을 골랐고 왜 골랐는지
    observation.md에 쓰세요.

    구현 - 선택적 반복(Selective Repeat) 슬라이딩 윈도.

      패킷   ("DATA", 번호, 조각)
      ACK    ("ACK", 누적 번호, 이 ACK를 만든 데이터의 번호)
             누적 번호 = 수신자가 순서대로 다 받은 다음 번호 (TCP 의 ACK 번호)
             두 번째 값 = 방금 받은 하나 (TCP 의 SACK 블록과 같은 역할)

    누적 번호 덕분에 ACK 하나가 사라져도 다음 ACK 가 그 몫까지 확인해 주고, 두 번째
    값 덕분에 구멍 뒤의 조각을 다시 보내지 않습니다. 확인받지 못한 조각마다 타이머를
    두고, 타임아웃은 §3.5.3 의 방식(SRTT + 4·RTTVAR, 단위는 step)으로 잽니다.
    """

    WINDOW = 16          # 확인 없이 띄워 둘 수 있는 조각 수. 1 이면 정지-대기와 같습니다
    MIN_RTO = 2          # step. 시계 단위가 1 step 이므로 RTT 표본은 정수입니다

    def __init__(self, data_channel, ack_channel, data):
        self.out, self.inbox = data_channel, ack_channel
        # R1: PAYLOAD 크기로 자르고 번호를 붙입니다. 번호는 조각 단위입니다.
        self.chunks = [data[i:i + PAYLOAD] for i in range(0, len(data), PAYLOAD)]
        self.base = 0          # 아직 확인받지 못한 가장 작은 번호
        self.next = 0          # 처음 보낼 다음 번호
        self.acked = set()     # base 위에서 따로 확인받은 번호 (구멍 뒤의 조각)
        self.sent_at = {}      # 번호 -> 마지막으로 보낸 step
        self.resent = set()    # 재전송한 번호. 그 ACK는 RTT 표본으로 쓰지 않음 (Karn)
        self.now = 0
        self.srtt = self.rttvar = None
        self.rto = 3
        self.stats = {"data": 0, "retransmits": 0, "acks": 0, "stale_acks": 0}

    def _send(self, seq):
        if seq in self.sent_at:
            self.resent.add(seq)
            self.stats["retransmits"] += 1
        self.sent_at[seq] = self.now
        self.stats["data"] += 1
        self.out.send(("DATA", seq, self.chunks[seq]))

    def _sample(self, rtt):
        """RFC 6298 그대로. 교재 §3.5.3 의 EstimatedRTT / DevRTT 입니다."""
        if self.srtt is None:
            self.srtt, self.rttvar = rtt, rtt / 2
        else:
            self.rttvar = 0.75 * self.rttvar + 0.25 * abs(self.srtt - rtt)
            self.srtt = 0.875 * self.srtt + 0.125 * rtt
        self.rto = max(self.MIN_RTO, self.srtt + max(1, 4 * self.rttvar))

    def _ack(self, seq):
        """seq 를 확인받은 것으로 표시합니다. 새로 알게 된 것이 없으면 False."""
        if seq in self.acked or not (self.base <= seq < self.next):
            return False
        if seq not in self.resent:
            self._sample(self.now - self.sent_at[seq])
        self.acked.add(seq)
        return True

    def step(self):
        """한 단위의 일을 합니다. 끝났다고 판단하면 False를 반환합니다."""
        self.now += 1

        # 1. 돌아온 ACK. 번호부터 확인합니다: 창 밖(이미 지난 것)이거나 이미 받은
        #    번호라면 아무것도 바꾸지 않습니다. 중복 ACK 가 여기서 걸러집니다.
        while True:
            pkt = self.inbox.receive()
            if pkt is None:
                break
            kind, cum, seq = pkt
            if kind != "ACK":
                continue
            self.stats["acks"] += 1
            new = self._ack(seq)
            for s in range(self.base, min(cum, self.next)):
                new = self._ack(s) or new
            if not new:
                self.stats["stale_acks"] += 1
        while self.base in self.acked:              # 창을 앞으로 밉니다
            self.acked.discard(self.base)
            self.sent_at.pop(self.base, None)
            self.resent.discard(self.base)
            self.base += 1

        # 2. R4: 타이머가 지난 조각만 다시 보냅니다 (Go-Back-N 처럼 전부가 아니라).
        for seq in range(self.base, self.next):
            if seq not in self.acked and self.now - self.sent_at[seq] >= self.rto:
                self._send(seq)

        # 3. 창에 자리가 있으면 새 조각을 보냅니다.
        while self.next < len(self.chunks) and self.next < self.base + self.WINDOW:
            self._send(self.next)
            self.next += 1

        return self.base < len(self.chunks)


class Receiver:
    """여러분의 수신자. 재조립한 바이트를 `.data()`로 돌려줍니다.

    구현 - 순서보다 먼저 온 조각은 버퍼에 두었다가 구멍이 메워지면 이어 붙입니다 (R2).
    이미 받은 번호가 또 오면 내용은 버리고 ACK 만 다시 보냅니다 (R3). 그 데이터가 다시
    왔다는 것은 앞서 보낸 ACK 가 사라졌다는 뜻일 수 있기 때문입니다.
    """

    def __init__(self, data_channel, ack_channel):
        self.inbox, self.out = data_channel, ack_channel
        self.expected = 0          # 순서대로 받아야 할 다음 번호
        self.buffer = {}           # 번호 -> 조각, expected 보다 앞서 도착한 것
        self.assembled = bytearray()
        self.stats = {"data": 0, "duplicates": 0, "buffered": 0}

    def step(self):
        while True:
            pkt = self.inbox.receive()
            if pkt is None:
                return True
            kind, seq, payload = pkt
            if kind != "DATA":
                continue
            self.stats["data"] += 1
            if seq < self.expected or seq in self.buffer:
                self.stats["duplicates"] += 1          # R3: 내용은 다시 쓰지 않음
            else:
                if seq > self.expected:
                    self.stats["buffered"] += 1        # 앞에 구멍이 있어 기다리는 조각
                self.buffer[seq] = payload
                while self.expected in self.buffer:    # R2: 순서대로만 내보냄
                    self.assembled += self.buffer.pop(self.expected)
                    self.expected += 1
            self.out.send(("ACK", self.expected, seq))

    def data(self):
        """지금까지 재조립한 바이트."""
        return bytes(self.assembled)


# ------------------------------------------------------------------- 하네스
def verify(seed=246, size=2000, max_steps=200_000):
    rng = random.Random(seed)    # 바이트마다 새 Random(seed) 를 만들면 2000바이트가 모두 같아져
    original = bytes(rng.getrandbits(8) for _ in range(size))   # 순서가 틀려도 해시가 같아집니다
    up, down = UnreliableChannel(seed), UnreliableChannel(seed + 1)

    # 데이터는 `up`으로 나가고, ACK는 `down`으로 돌아옵니다. 둘 다 신뢰할 수 없습니다.
    sender = Sender(up, down, original)
    receiver = Receiver(up, down)

    for _ in range(max_steps):
        alive = sender.step()
        receiver.step()
        if not alive and len(receiver.data() or b"") >= size:
            break

    got = receiver.data() or b""
    ok = hashlib.sha256(got).hexdigest() == hashlib.sha256(original).hexdigest()
    print(f"  bytes    sent {size}   received {len(got)}")
    print(f"  channel  {up.stats}")
    print(f"  result   {'IDENTICAL' if ok else 'CORRUPTED OR INCOMPLETE'}")
    return 0 if ok else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--verify", action="store_true")
    p.add_argument("--seed", type=int, default=246)
    a = p.parse_args()
    raise SystemExit(verify(a.seed) if a.verify else p.print_help())
