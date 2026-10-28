# Binary-backed triage of the 12 unresolved IHmiKss source rows

**Source:** `AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip` from the supplied Drive file; extracted `STAGE2.1/bin/gtf2`, 10,180,269 bytes, SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`.

## New ELF run

The archive was decoded using the existing repository's documented CIFS/IFSPTTBL + Adler-32-checked LZO Stage2 reconstruction profile (the extracted ELF hash matches prior research). The 12 DP write addresses previously labeled `unknown` in `gtf2-ipc-to-dp.csv` were individually located in the **actual ELF**, and assigned candidate function starts by nearest preceding ARM `STMDB sp!,{...,lr}` prologue, with the next such prologue used as an upper bound.

**Result:** 12 DP writes have **12 distinct candidate function starts**. Therefore the 12 rows are **not one verified callback structure**. This is a candidate function-level split, not yet proof of 12 independent registered IPC methods; thunks and inlining require further examination.

New evidence from PC-relative literal references within the candidate function ranges:

- DP `0x0200016a`, write `0x694308`, candidate start `0x6942f0`: diagnostic `AAG_Blinker_H_aktiv (s_AB): %d` referenced at `0x694324` (string VA `0x88eef6`).
- DP `0x02000222`, write `0x694460`, candidate start `0x694448`: diagnostic `rightHandDrive: %d` referenced at `0x69447c` (string VA `0x88ef15`).
- No other printable diagnostic strings were found by this literal-pointer scan inside the ten remaining candidate function ranges. **Absence of such a string does not mean the callback has no symbolic identity.**

The complete 12-row ledger is `docs/fpk1/gtf2-unresolved-callback-functions.csv`. These diagnostic phrases are **behavioral clues**, not confirmed IPC method names or field names.

## Non-duplication check

Earlier `group_rte_dp_callbacks.py` and `name_rte_dp_callbacks.py` already grouped direct DP writes and searched `batchLock()` diagnostic names. The incremental result here is a **fresh execution against the user-supplied original ELF**, the exact 12 unresolved DP site split, and the two diagnostic-string xrefs. The canonical 176-row table is unchanged pending proof of actual callback identity.

## Next evidence needed

Resolve the 12 candidate callback entrypoints to their **registered virtual interface/vtable slots** or IPC interface descriptors; independently verify that the DP write is reached from that entrypoint. Search for call-site-to-method correspondence, not merely nearby printable strings. Then trace subscription and dispatch to distinguish an IPC callback from a helper or forwarding thunk.
