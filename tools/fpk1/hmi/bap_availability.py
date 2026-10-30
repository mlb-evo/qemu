"""Shared local BAP coding/mask ownership for independent display fixtures."""
import gss_ipc_frames as ipc


class Availability:
    def __init__(self, peer):
        self.peer = peer
        self.owners = {}
        self.original = None

    @property
    def mask(self):
        result = 0
        for _, mask in self.owners.values():
            result |= mask
        return result

    def select(self, owner, bit, mask, enabled):
        before = dict(self.owners)
        if enabled:
            self.owners[owner] = (bit, mask)
        else:
            self.owners.pop(owner, None)
        if before == self.owners:
            return
        if self.original is None:
            self.original = list(self.peer.config_signals)
        updated = list(self.original)
        bits = sum(1 << value[0] for value in self.owners.values())
        found = False
        for i, (name, key, payload) in enumerate(updated):
            if key == 0x12c:
                found = True
                updated[i] = (name, key, (int.from_bytes(payload, 'little') | bits).to_bytes(2, 'little'))
        if not found and bits:
            updated.append(('BAPStrecke', 0x12c, bits.to_bytes(2, 'little')))
        if not found and not bits:
            self.peer.queue(*ipc.rte_signal(0x12c, bytes(2)))
        self.peer.config_signals = updated
        self.peer.queue_config(log=True)
        self.send()
        if not self.owners:
            self.original = None

    def send(self):
        self.peer.queue(6, 17, self.mask.to_bytes(4, 'little'))


def availability(peer):
    if not hasattr(peer, '_fixture_availability'):
        peer._fixture_availability = Availability(peer)
    return peer._fixture_availability
