import unittest

import gss_ipc_frames as ipc
import kss_peer
from hmi.closures import updates as closure_updates


class FakeSocket:
    def __init__(self):
        self.sent = []

    def sendall(self, data):
        self.sent.append(bytes(data))


class LinkTests(unittest.TestCase):
    def test_master_cycle_follows_the_slave_handshake(self):
        sock = FakeSocket()
        link = kss_peer.Link(sock, lambda text: None)
        mine = ipc.build_frame([(7, 11, b'\x01', True)])
        gss = ipc.build_frame([(7, 1, b'\x01', True)])
        link.start_cycle(mine)
        self.assertEqual(sock.sent, [b'D\x01'])
        link.on_cc6(True)
        self.assertEqual(sock.sent[-1], b'X\x40' + mine[:64])
        self.assertEqual(link.on_reply(gss[:64]), (None, False))
        link.on_cc6(False)
        self.assertEqual(sock.sent[-1], b'X\x40' + mine[64:])
        link.on_reply(gss[64:])
        link.on_cc6(True)
        self.assertEqual(sock.sent[-1], b'X\x01\xd0')
        self.assertEqual(link.on_reply(b'\xd0'), (gss, True))
        self.assertTrue(link.on_cc6(False))
        self.assertEqual((sock.sent[-1], link.state), (b'D\x00', kss_peer.IDLE))

    def test_bad_frame_is_nacked_and_not_delivered(self):
        sock = FakeSocket()
        link = kss_peer.Link(sock, lambda text: None)
        link.start_cycle(ipc.empty_frame())
        link.on_cc6(True)
        link.on_reply(bytes(64))
        link.on_cc6(False)
        link.on_reply(bytes(64))
        link.on_cc6(True)
        self.assertEqual(sock.sent[-1], b'X\x01\xe1')
        self.assertFalse(link.on_reply(b'\xd0')[1])

    def test_requested_cycle_starts_clocking_at_once(self):
        sock = FakeSocket()
        link = kss_peer.Link(sock, lambda text: None)
        link.on_cc6(True)
        link.start_cycle(ipc.empty_frame())
        self.assertEqual(sock.sent[0], b'D\x01')
        self.assertEqual(sock.sent[1][:2], b'X\x40')

    def test_parses_chardev_messages(self):
        link = kss_peer.Link(FakeSocket(), lambda text: None)
        link.buffer = b'C\x01R\x02ab' + b'R\x03x'
        self.assertEqual(list(link.messages()), [('C', True), ('R', b'ab')])
        self.assertEqual(link.buffer, b'R\x03x')


class KssTests(unittest.TestCase):
    def test_sends_versions_info_and_persistency_then_requests_application_run(self):
        kss = kss_peer.Kss(lambda text: None, persistency=bytes(range(16)))
        kss.RUN_REQUEST_DELAY = 0
        status = ipc.build_frame([(7, ipc.CID_GSS_STATUS, b'\x01', True)])
        kss.receive(status)
        kss.receive(status)
        self.assertEqual(len(kss.outbox), 3)
        lun, cid, data, last = ipc.parse_frame(kss.next_frame())[0]
        self.assertEqual((lun, cid, last), (ipc.LUN_RTE, 0, True))
        self.assertEqual(data, ipc.l4c_message(ipc.L4C_VS_HMI_VERSIONS_INFO, kss.VERSIONS_INFO + b'\x00'))
        kss.delivered(kss.next_frame())
        lun, cid, data, last = ipc.parse_frame(kss.next_frame())[0]
        self.assertEqual((lun, cid, data, last),
                         (7, ipc.CID_GSS_MODE_REQUEST, b'\x01\x00' + bytes(range(16)), True))
        kss.tick()
        self.assertEqual(len(kss.outbox), 2, 'run request waits for startup data')
        kss.delivered(kss.next_frame())
        self.assertEqual(ipc.parse_frame(kss.next_frame())[0][2],
                         closure_updates(0))
        kss.delivered(kss.next_frame())
        kss.tick()
        lun, cid, data, last = ipc.parse_frame(kss.next_frame())[0]
        self.assertEqual((lun, cid, data[:2], last), (7, ipc.CID_GSS_MODE_REQUEST, b'\x01\x02', True))
        kss.delivered(kss.next_frame())
        kss.tick()
        self.assertEqual(kss.next_frame(), ipc.empty_frame())

    def test_alive_request_carries_the_clamps(self):
        kss = kss_peer.Kss(lambda text: None)
        kss.last_alive = 0.0
        kss.tick()
        messages = [ipc.parse_frame(frame)[0] for frame in kss.outbox]
        self.assertEqual(messages[0][:2], (7, ipc.CID_GSS_ALIVE_REQUEST))
        self.assertEqual([m[2] for m in messages[1:]],
                         [ipc.l4c_message(0x79, b'\x01\x00'), ipc.l4c_message(0x7a, b'\x01\x00'),
                          closure_updates(0)])

    def test_empty_frame_ack_does_not_drop_unsent_run_request(self):
        kss = kss_peer.Kss(lambda text: None)
        in_flight = kss.next_frame()
        self.assertEqual(in_flight, ipc.empty_frame())
        # RUN_REQUEST_DELAY expires while this empty SPI transfer is in flight.
        kss.request_run()
        pending = kss.next_frame()
        kss.delivered(in_flight)
        self.assertEqual(kss.next_frame(), pending)
        kss.delivered(pending)
        self.assertEqual(kss.next_frame(), ipc.empty_frame())

    def test_empty_frame_ack_does_not_drain_configuration(self):
        kss = kss_peer.Kss(lambda text: None)
        in_flight = kss.next_frame()
        kss.handle(7, ipc.CID_GSS_STATUS, b'\x01')
        pending = list(kss.outbox)
        kss.delivered(in_flight)
        self.assertEqual(kss.outbox, pending)
        self.assertTrue(kss.run_pending)

if __name__ == '__main__':
    unittest.main()
