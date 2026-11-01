# GTF2 behavioral compatibility boundary for a future IAA frontend

Status: implementation-oriented synthesis of **existing static findings**, not a claim of runtime equivalence. Source: `docs/fpk1/gtf2-stock-routing-lifecycle.md` and reproducible verifiers in `tools/fpk1/research/gtf2/`.

## Separation of concerns

The replaceable boundary is after stock HMI event handling has selected a logical destination and before any Kanzi-specific scene/property mutation. Do **not** implement a global `IPC -> scene property` lookup as if it existed in the stock binary. Instead:

```text
IHmiKss transport (registration still unresolved)
  -> typed callback payload (byte offsets and widths known for 176 writes)
  -> DP update/event (ID + value; conversion rules not fully recovered)
  -> HMI dispatcher / state machine / guard logic
  -> logical UI state and semantic effects
  -> IAA adapter (future)
```

Parallel paths:
- startup configures `DisplaySupervisor.kzb`, optionally adds DP-dependent configuration, then queues image/texture batch work;
- graphics batch queue and KZB resources are **not** the IPC callback queue;
- Stage3 process launch and AliveManager activation are lifecycle concerns, not scene-property routing.

## Proven contract and evidence

| Contract element | Observed stock evidence | IAA-port implication | Confidence |
| --- | --- | --- | --- |
| HMI owner lifetime | guarded getter `0x2bae28`, constructor `0x25ef60`; startup call `0x1146b8 -> 0x222070 -> 0x2bae28` | central persistent HMI state, created before primary loop | verified normal path |
| IPC descriptor | `IHmiKss`/`IHmiKssReply` descriptor `0xa7e838` stored during owner construction | keep transport adapter separate from HMI state | descriptor verified, subscribe unknown |
| Input-to-DP | `gtf2-ipc-to-dp.csv`: 176 distinct source DP IDs, callback names, offsets, u8/u16 widths | decode by callback schema and byte offset; do not invent member names | binary-backed inventory |
| DP routing | dispatcher `0x570000-0x577000`, including computed-ID branches | explicit handler registry and ordered dispatch | partial |
| Event fanout | DP `0x02000225` handler `0x584710` uses two receiver slots `0x4b02c`, `0x51310`; DP `0x020001e6` handler `0x5812a8` uses slots `0x1f5d0`, `0x1fb00` | one DP may trigger multiple effects; never assume one-to-one | verified calls, effect semantics unknown |
| Scene metadata | ESP wrapper path and property literals, owner offset `0x453b8` | map logical outputs to IAA widget/state names independently | verified ESP chain |
| Receiver lifetime | owner constructor binds embedded receiver via virtual slot `+0x30`; wrapper getter reads `+0xb8` on event | no requirement for lazy scene lookup on every event | verified ESP chain |
| Graphics batch | startup `0x114a98` enqueues 52-byte work item; `0x14199c` drains, with `handleWaitingBatch` image/texture diagnostics | implement resource-loading separately from IPC | verified |
| Startup DP configuration | `0x114a18` reads `0x064004d3`; status `==1` gates `0x142cec`; both branches reach graphics queue | treat status separately from DP value; preserve optional config behavior | verified branch, value meaning unknown |

## Minimal testable behavioral interfaces (proposed, NOT recovered C++ ABI)

```text
TransportAdapter:
  on_message(callback_name, raw_payload)
  connect(), disconnect()  // timing and protocol TBD

InputDecoder:
  decode(callback_name, raw_payload) -> [DpWrite(dp_id, typed_value)]
  // Validate offsets, widths and bounds. Preserve ordering.

HmiCore:
  initialize(config)
  apply_dp(dp_id, value) -> [SemanticEffect]
  // Owns persistent state, event guards, fanout and transitions.

PresentationPort:
  apply([SemanticEffect])
  // IAA-specific: scene/widget/state binding, no stock Kanzi dependency.

ResourceLoader:
  configure(resource_name, optional_dp_config)
  enqueue_batch(), process_batch(), on_batch_complete()
```

This is a **target design**, not proof of stock internal API shapes, threading, callback ordering, value normalization or exact rendering behavior. The existing CSV is a source-write inventory, not a complete handler implementation.

## Priority reverse-engineering backlog

1. Trace `IHmiKss` descriptor field consumers to the real connect/subscribe path, including thread ownership and reconnect semantics.
2. For every DP handler, recover predicates, value transforms, state writes, fanout, and non-UI side effects; distinguish DP *write* from DP *notification*.
3. Recover complete dispatch coverage, including arithmetic and indirect routes; label each edge with exact VA and proof strength.
4. Extract semantic transitions for speed/gear/ACC/telltales/menus and identify initialization defaults, stale-event behavior and precedence.
5. Trace resource-loader completion separately from HMI readiness, scene switching and Stage3 startup.
6. Build differential replay fixtures: callback name + raw bytes + initial state -> ordered DP writes -> ordered semantic effects; compare against stock runtime traces before claiming parity.

## Acceptance criteria for replacing Kanzi

- All known callback payload offsets/widths decode without out-of-bounds reads.
- For every recovered event, same DP writes and **ordered** semantic effects as stock, including multiple consumers and guards.
- Repeated events, missing messages, initialization, and mode/scene transitions have explicit regression tests.
- IPC connection lifecycle and resource/graphics readiness are independent state machines.
- No direct Kanzi dependency in `HmiCore`; IAA consumes semantic state/effects.
- Every claimed parity case links to static evidence plus runtime replay/trace. Until runtime evidence exists, label it `static-only`.

## Known gaps

Exact IPC field identifiers, subscription registration, event ordering across threads, complete DP consumer coverage, dynamic value transforms, and scene switch lifecycle are **not yet proven**. The 33 candidate DP-to-scene joins are not 33 guaranteed equivalent IAA behaviors. See the original lifecycle report for verified/candidate distinctions.
