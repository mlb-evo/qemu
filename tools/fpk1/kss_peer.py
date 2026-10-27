#!/usr/bin/env python3
"""Host stand-in for FPK1's KSS microcontroller on the GSS<->KSS SPI link.

Connects to QEMU's tegra30-slink chardev (-chardev socket,id=kss,...) and acts
as SPI master the way libnvspislave expects (recovered from Q7 0378):

  raise DD7 -> CC6 rises: clock 64 bytes -> CC6 falls: clock 64 bytes
  -> CC6 rises: clock the 1-byte ACK/NACK -> CC6 falls: drop DD7.

The Tegra may also raise CC6 while DD7 is low to request a cycle. Above that
it speaks the gss_ipc frame format (gss_ipc_frames.py): answers GSS_STATUS
by sending the VS_HMI_VersionsInfo RTE signal and, once that is delivered,
GSS_MODE_REQUEST(1, 2) (application run), sends GSS_ALIVE_REQUEST together
with Clamp 15 and Clamp S on every second and logs everything else it
receives. gss_ipc reads
VersionsScreen_VS_VersionInfo right after Rte_Start ("Update HOOK from RTE")
and logs "returned 1" (never received) if KSS has not sent it by then. This is a research stand-in; it
knows nothing of KSS's real behaviour beyond those messages.
"""
import argparse
import select
import socket
import sys
import time

import gss_ipc_frames as ipc

IDLE, FIRST, SECOND, ACK, END = 'idle', 'first', 'second', 'ack', 'end'
HALF = ipc.FRAME_SIZE // 2


class Link:
    """SPI master state machine over the tegra30-slink chardev protocol."""

    def __init__(self, sock, log, period=0.01, timeout=2.0):
        self.sock, self.log = sock, log
        self.period, self.timeout = period, timeout
        self.buffer = b''
        self.cc6 = False
        self.state, self.since, self.next_cycle = IDLE, time.monotonic(), 0.0
        self.tx = self.rx = b''
        self.cycles = self.delivered = 0

    def send(self, data):
        self.sock.sendall(data)

    def dd7(self, level):
        self.send(b'D' + bytes([level]))

    def exchange(self, data):
        self.send(b'X' + bytes([len(data)]) + data)

    def enter(self, state):
        self.state, self.since = state, time.monotonic()

    def start_cycle(self, frame):
        self.tx, self.rx = frame, b''
        self.cycles += 1
        self.enter(FIRST)
        self.dd7(1)
        if self.cc6:
            # The Tegra requested this cycle and is already armed.
            self.exchange(self.tx[:HALF])

    def on_cc6(self, level):
        self.cc6 = level
        if self.state == FIRST and level:
            self.exchange(self.tx[:HALF])
        elif self.state == SECOND and not level:
            self.exchange(self.tx[HALF:])
        elif self.state == ACK and level:
            self.exchange(bytes([ipc.ACK if ipc.valid(self.rx) else ipc.NACK]))
        elif self.state == END and not level:
            self.dd7(0)
            self.enter(IDLE)
            return True
        return False

    def on_reply(self, data):
        """Returns (gss frame, delivered) once the ACK byte is exchanged."""
        if self.state == FIRST:
            self.rx += data
            self.enter(SECOND)
        elif self.state == SECOND:
            self.rx += data
            self.enter(ACK)
        elif self.state == ACK:
            mine = ipc.ACK if ipc.valid(self.rx) else ipc.NACK
            self.enter(END)
            return self.rx, mine == ipc.ACK and data[0] == ipc.ACK
        return None, False

    def abort_if_stuck(self):
        if self.state != IDLE and time.monotonic() - self.since > self.timeout:
            self.log(f'link: stuck in {self.state} (CC6={int(self.cc6)}), dropping DD7')
            self.dd7(0)
            self.enter(IDLE)
            self.next_cycle = time.monotonic() + 0.5

    def messages(self):
        """Yield ('C', level) and ('R', data) from the chardev stream."""
        while True:
            if not self.buffer:
                return
            kind = self.buffer[:1]
            if kind == b'C' and len(self.buffer) >= 2:
                yield 'C', bool(self.buffer[1])
                self.buffer = self.buffer[2:]
            elif kind == b'R' and len(self.buffer) >= 2 and len(self.buffer) >= 2 + self.buffer[1]:
                n = self.buffer[1]
                yield 'R', self.buffer[2:2 + n]
                self.buffer = self.buffer[2 + n:]
            elif kind in (b'C', b'R'):
                return
            else:
                self.log(f'link: unexpected byte {self.buffer[0]:#04x}')
                self.buffer = self.buffer[1:]


class Kss:
    """GSS-Manager start-up and alive traffic on LUN 7."""

    # Stand-in versions screen data: the update's part number and software version.
    VERSIONS_INFO = ipc.vs_versions_info(part_number=b'8S0906961AK', hw_part_number=b'8S0906961AK',
                                         sw_version=b'0378', kss_sw_version=b'0378')
    # Gives gss_ipc's L4C receive task time to store the RTE data before Rte_Start.
    RUN_REQUEST_DELAY = 0.2
    # Terminal 15 (ignition) and S on, sent with every alive request as KSS
    # repeats CAN signals. gtf2 shows the cluster only with Clamp 15 on; gss_ipc
    # drops values that arrive before gtf2 connects, so they must repeat.
    CLAMPS = ((ipc.L4C_CLAMPS_CLAMP15, b'\x01'), (ipc.L4C_CLAMPS_CLAMPS, b'\x01'))

    def __init__(self, log, persistency=bytes(16)):
        self.log = log
        self.persistency = persistency
        self.outbox = []
        self.reassembler = ipc.Reassembler()
        self.last_alive = None
        self.alive_counter = 0
        self.status = None
        self.run_pending = False
        self.run_request_at = None

    def queue(self, lun, cid, data):
        for record in ipc.fragment(lun, cid, data):
            self.outbox.append(ipc.build_frame([record]))

    def next_frame(self):
        return self.outbox[0] if self.outbox else ipc.empty_frame()

    def delivered(self):
        if self.outbox:
            self.outbox.pop(0)
            if not self.outbox and self.run_pending:
                self.run_pending = False
                self.run_request_at = time.monotonic() + self.RUN_REQUEST_DELAY

    def receive(self, frame):
        try:
            messages = self.reassembler.feed(frame)
        except ValueError as error:
            self.log(f'rx: {error}')
            return
        for lun, cid, data in messages:
            self.handle(lun, cid, data)

    def handle(self, lun, cid, data):
        name = {ipc.CID_GSS_STATUS: 'GSS_STATUS', ipc.CID_GSS_RESET_REQUEST: 'GSS_RESET_REQUEST',
                ipc.CID_GSS_MODE_RESPONSE: 'GSS_MODE_RESPONSE',
                ipc.CID_GSS_ALIVE_RESPONSE: 'GSS_ALIVE_RESPONSE'}.get(cid) if lun == ipc.LUN_GSS_MANAGER else None
        if name == 'GSS_STATUS':
            # Sent repeatedly; only changes are logged.
            if data == self.status:
                return
            self.status = data
        if name != 'GSS_ALIVE_RESPONSE':
            self.log(f'rx lun {lun:#04x} cid {cid:#04x}{" " + name if name else ""}: {data.hex()}')
        if name == 'GSS_STATUS' and data == b'\x01':
            # 1 = "IPC COM ready": send the RTE data gss_ipc reads at Rte_Start
            # and the stored persistency (mode 1 submode 0; submode 2 ignores
            # it, and MOST's NOCOMM/SSO restore reports "no persistent data"
            # without it), then (in tick) request application run once per
            # link-up.
            self.log('tx RTE VS_HMI_VersionsInfo')
            self.queue(*ipc.rte_signal(ipc.L4C_VS_HMI_VERSIONS_INFO, self.VERSIONS_INFO))
            self.log('tx GSS_MODE_REQUEST mode 1 submode 0 (persistency)')
            self.queue(*ipc.gss_mode_request(1, 0, self.persistency))
            self.run_pending = True

    def request_run(self):
        lun, cid, payload = ipc.gss_mode_request(1, 2, self.persistency)
        self.log('tx GSS_MODE_REQUEST mode 1 submode 2 (application run)')
        self.queue(lun, cid, payload)
        self.last_alive = time.monotonic()

    def tick(self):
        if self.run_request_at is not None and time.monotonic() >= self.run_request_at:
            self.run_request_at = None
            self.request_run()
        if self.last_alive is not None and time.monotonic() - self.last_alive >= 1.0:
            self.last_alive = time.monotonic()
            self.alive_counter = (self.alive_counter + 1) & 0xff
            self.queue(ipc.LUN_GSS_MANAGER, ipc.CID_GSS_ALIVE_REQUEST, bytes([self.alive_counter]))
            for data_id, value in self.CLAMPS:
                self.queue(*ipc.rte_signal(data_id, value))


def connect(path, attempts=600):
    for _ in range(attempts):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(path)
            return sock
        except OSError:
            sock.close()
            time.sleep(0.1)
    raise SystemExit(f'kss_peer: cannot connect to {path}')


def run(path, period, emit=None):
    """Serve the link until QEMU disconnects; emit(line) gets each log line."""
    start = time.monotonic()
    emit = emit or (lambda line: print(line, flush=True))

    def log(text):
        emit(f'[kss {time.monotonic() - start:8.2f}] {text}')

    sock = connect(path)
    log(f'connected to {path}')
    link, kss = Link(sock, log, period), Kss(log)
    while True:
        wait = max(0.0, min(link.next_cycle - time.monotonic(), period)) if link.state == IDLE else period
        ready, _, _ = select.select([sock], [], [], wait)
        if ready:
            data = sock.recv(4096)
            if not data:
                log(f'disconnected after {link.cycles} cycles, {link.delivered} frames delivered')
                return
            link.buffer += data
            for kind, value in link.messages():
                if kind == 'C':
                    finished = link.on_cc6(value)
                    if finished:
                        link.next_cycle = time.monotonic() + period
                    elif link.state == IDLE and value:
                        # Tegra-initiated request while idle.
                        link.start_cycle(kss.next_frame())
                else:
                    frame, delivered = link.on_reply(value)
                    if frame is not None:
                        if delivered:
                            link.delivered += 1
                            kss.delivered()
                        if ipc.valid(frame):
                            kss.receive(frame)
        kss.tick()
        link.abort_if_stuck()
        if link.state == IDLE and time.monotonic() >= link.next_cycle:
            link.start_cycle(kss.next_frame())


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('socket', help='QEMU chardev socket of the kss slink (server side)')
    parser.add_argument('--period', type=float, default=0.01, help='seconds between idle cycles')
    args = parser.parse_args()
    try:
        run(args.socket, args.period)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == '__main__':
    main()
