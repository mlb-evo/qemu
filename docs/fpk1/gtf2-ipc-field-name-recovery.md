# Recovering original IHmiKss IPC field names

## Status: original field identifiers are not established

The stock GTF2 ARM ELF permits reconstruction of the following for each of **176** IPC-to-DP writes:

- IPC callback name (33 named callback types, plus an unresolved callback grouping);
- payload byte offset and load width (`u8`/`u16`);
- 32-bit DP ID and write call site.

See `docs/fpk1/gtf2-ipc-to-dp.csv` for the full evidence table. The `field_name` column is **intentionally unknown**: a load such as `ldrb r2,[rN,#4]` proves the field's position, not its C++/IDL identifier.

### Names we *can* identify, but must not confuse with IPC field names

| IPC callback | Payload offset | DP ID | Scene property | Confidence |
| --- | --- | --- | --- | --- |
| `TelltaleHMI_Display` | `+0x04` | `0x020002CD` | `ESP` | Verified handler/constructor/receiver chain |
| `TelltaleAALA_Display` | `+0x01` | `0x02000217` | `Limiter`, `Limiter_shadow`, `Cruise_shadow` | Candidate static join; not original IPC names |
| `TelltaleAALA_Display` | `+0x07` | `0x02000220` | `praediktivesACC`, `PEA_Foot`, `ACC_STA` | Candidate static join; not original IPC names |
| `ActTest_SoftLEDs` | `+0x04` | `0x0200016B` | `Limiter`, `Limiter_shadow`, `Cruise_shadow` | Candidate static join; not original IPC names |

The 176-entry source-write inventory and the scene join are different layers: one IPC field may affect multiple scene properties, and some DP IDs have no proven scene sink. Never rename an IPC field to a scene property without an IDL/schema or equivalent binary metadata tying that exact identifier to the payload offset.

### Binary/firmware evidence checked

- Stock GTF2 contains callback strings and numerous unrelated `DP_ID_...` logging strings, but no confirmed mapping from the above IPC field offsets to their original source identifiers.
- The provided `AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip` includes `KSSApplication.bin` (599,924 bytes); literal searches of that file for `IHmiKss`, `TelltaleHMI_Display`, and `ESP` returned no hits. This is **not** proof the KSS firmware lacks an encoded schema.
- The provided firmware archive does not list obvious `.h` or `.idl` source files.

### Evidence required for exact names

Locate the generated `asi.gss.ipc.rte.hmi.IHmiKss` C++ headers, the IPC/RTE IDL schema, or KSS signal specification for this firmware revision. For each callback, map schema member order/offset and width to the stock ELF load instructions. Only then replace `unknown` in the canonical CSV, with a citation to the schema. Until that source is found, **the actual IPC member names remain unresolved**.

The current table does establish the exact numeric interface (callback, byte offset, type, DP ID), so replay or tracing can proceed without guessing symbolic member names.
