#!/usr/bin/env python3
"""Frame format of the FPK1 GSS<->KSS SPI link, as implemented by gss_ipc.

Recovered from gss_ipc (Transfer/RxBuffers/TxBuffers classes, Q7 0378):

* Each SPI transfer moves one 128-byte frame in each direction. Byte 0 is the
  number of used payload bytes, bytes 1..126 hold records, unused bytes are
  0xff and byte 127 is ``~sum(bytes[0:127]) & 0xff``.
* A record is ``[fragment length][LUN][CID | 0x80 on the last fragment]``
  followed by the fragment; byte 0 counts the 3-byte headers too. Messages
  longer than the free space continue in later frames with the same LUN/CID.
* After each frame both sides exchange one byte: 0xd0 (ACK, checksum valid)
  or 0xe1 (NACK). A frame counts as delivered only if both bytes are 0xd0;
  otherwise the sender keeps it for the next transfer.

GSS-Manager uses LUN 7. KSS -> GSS CIDs: 3 GSS_MODE_REQUEST (mode, submode,
up to 16 persistency bytes), 6 GSS_FLASH_RESPONSE (2), 8 GSS_KSS_STATUS (1),
9 SYS_MODE_REQUEST (3), 11 GSS_ALIVE_REQUEST (1). GSS -> KSS CIDs: 1
GSS_STATUS (1), 2 GSS_RESET_REQUEST, 4 GSS_MODE_RESPONSE (mode, submode,
16 persistency bytes), 12 GSS_ALIVE_RESPONSE (1). In the GSS manager, mode 1
with submode 2 enters GSS_SM_APP_RUN (application run); mode 1 submode 0
stores the persistency bytes.
"""
FRAME_SIZE = 128
PAYLOAD_END = FRAME_SIZE - 1
ACK, NACK = 0xd0, 0xe1
LAST_FRAGMENT = 0x80

LUN_GSS_MANAGER = 7
CID_GSS_STATUS = 1
CID_GSS_RESET_REQUEST = 2
CID_GSS_MODE_REQUEST = 3
CID_GSS_MODE_RESPONSE = 4
CID_GSS_FLASH_RESPONSE = 6
CID_GSS_KSS_STATUS = 8
CID_SYS_MODE_REQUEST = 9
CID_GSS_ALIVE_REQUEST = 11
CID_GSS_ALIVE_RESPONSE = 12


def checksum(frame):
    return ~sum(frame[:PAYLOAD_END]) & 0xff


def valid(frame):
    return len(frame) == FRAME_SIZE and frame[PAYLOAD_END] == checksum(frame)


def empty_frame():
    frame = bytearray(b'\xff' * FRAME_SIZE)
    frame[0] = 0
    frame[PAYLOAD_END] = checksum(frame)
    return bytes(frame)


def build_frame(records):
    """records: iterable of (lun, cid, data, last). Returns one frame."""
    frame = bytearray(b'\xff' * FRAME_SIZE)
    used = 0
    for lun, cid, data, last in records:
        if not 0 <= cid < LAST_FRAGMENT or not 0 <= lun <= 0xff or len(data) > 0xff:
            raise ValueError('Invalid record')
        if 1 + used + 3 + len(data) > PAYLOAD_END:
            raise ValueError('Records exceed the frame')
        at = 1 + used
        frame[at:at + 3] = bytes([len(data), lun, cid | (LAST_FRAGMENT if last else 0)])
        frame[at + 3:at + 3 + len(data)] = data
        used += 3 + len(data)
    frame[0] = used
    frame[PAYLOAD_END] = checksum(frame)
    return bytes(frame)


def parse_frame(frame):
    """Return [(lun, cid, fragment, last)]; raises on a bad checksum or layout."""
    if not valid(frame):
        raise ValueError('Bad frame checksum')
    used, at, records = frame[0], 1, []
    if used > PAYLOAD_END - 1:
        raise ValueError('Bad payload length')
    while used > 0:
        if used < 3:
            raise ValueError('Truncated record header')
        size, lun, cid = frame[at:at + 3]
        if 3 + size > used:
            raise ValueError('Record exceeds payload')
        records.append((lun, cid & 0x7f, bytes(frame[at + 3:at + 3 + size]), bool(cid & LAST_FRAGMENT)))
        at += 3 + size
        used -= 3 + size
    return records


class Reassembler:
    """Collect fragments per (LUN, CID) and return completed messages."""

    def __init__(self):
        self.partial = {}

    def feed(self, frame):
        done = []
        for lun, cid, data, last in parse_frame(frame):
            buffer = self.partial.setdefault((lun, cid), bytearray())
            buffer += data
            if last:
                done.append((lun, cid, bytes(self.partial.pop((lun, cid)))))
        return done


def fragment(lun, cid, message):
    """Split one message into frame-sized records (one record per frame)."""
    limit = PAYLOAD_END - 1 - 3
    pieces = [message[i:i + limit] for i in range(0, len(message), limit)] or [b'']
    return [(lun, cid, piece, i == len(pieces) - 1) for i, piece in enumerate(pieces)]


def gss_mode_request(mode, submode, persistency=b'\x00' * 16):
    if len(persistency) > 16:
        raise ValueError('At most 16 persistency bytes')
    return LUN_GSS_MANAGER, CID_GSS_MODE_REQUEST, bytes([mode, submode]) + persistency
