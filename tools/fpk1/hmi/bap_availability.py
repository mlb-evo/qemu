"""Shared local BAP coding/mask ownership for independent display fixtures."""
import gss_ipc_frames as ipc

# ConfigM messages a fixture may extend: l4c dataID -> (name, wire bytes).
CONFIG = {0x127: ('Driverassist_Media', 3), 0x12c: ('BAPStrecke', 2)}


class Availability:
    def __init__(self, peer):
        self.peer = peer
        self.owners = {}
        self.original = None

    @property
    def mask(self):
        result = 0
        for _, mask, _ in self.owners.values():
            result |= mask
        return result

    def select(self, owner, bit, mask, enabled, key=0x12c):
        """Own `bit` of ConfigM message `key` (BAPStrecke by default) and `mask`."""
        before = dict(self.owners)
        if enabled:
            self.owners[owner] = (bit, mask, key)
        else:
            self.owners.pop(owner, None)
        if before == self.owners:
            return
        if self.original is None:
            self.original = list(self.peer.config_signals)
        updated = list(self.original)
        for data_id in sorted({value[2] for value in before.values()} | {value[2] for value in self.owners.values()}):
            name, size = CONFIG[data_id]
            bits = sum(1 << value[0] for value in self.owners.values() if value[2] == data_id)
            found = False
            for i, (signal, current, payload) in enumerate(updated):
                if current == data_id:
                    found = True
                    updated[i] = (signal, current, (int.from_bytes(payload, 'little') | bits).to_bytes(size, 'little'))
            if not found and bits:
                updated.append((name, data_id, bits.to_bytes(size, 'little')))
            if not found and not bits:
                self.peer.queue(*ipc.rte_signal(data_id, bytes(size)))
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
