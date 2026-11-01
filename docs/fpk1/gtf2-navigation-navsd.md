# GTF2 navigation: NavigationSD BAP availability, map options and Map_Presentation

> Status: static analysis plus guest runs, 2026-11-01. Local research only; not for upstream.

Sources: original ARM32 GTF2 ELF SHA256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`
and gss_ipc SHA256 `590e17373caa83f80f3d1965d6ccd9bee50a67b060a88bafeaa2761fa1a1d056`
(Q7 0378, `build_fpk1/research-artifacts/wheel/`). Cross-references were produced with
`tools/fpk1/research/hmi/inspect_navigation.py`; guest runs with
`tools/fpk1/research/hmi/probe_navigation.py` (outputs in
`build_fpk1/research-artifacts/navigation/`). The KSS-side fixture is
`tools/fpk1/hmi/navigation.py`, the Qt tab `tools/fpk1/ui/navigation.py`.

Confidence labels: **verified** = observed in a guest run (GTF2 trace and/or
scanout); **static** = read from code/tables, consistent but not exercised on
screen; **inferred** = interpretation of names/strings.

## 1. Why the cluster showed "Navigation is currently unavailable"

Two independent conditions, both missing with the default coding
`008500E07C98000801A369602000600000000000`:

1. **Coding / activation mask (static, verified effect).** `handleDriverassistMedia()`
   (`0x15779c`) reads the ConfigM `Driverassist_Media` record (l4c dataID `0x127`)
   as one byte per wire bit. Byte `0x0e` (wire bit 14, coding bit 87) sets bit
   `0x4` of the BAP activation mask at `this+0x2c` and logs
   `"BAP_NAVIGATION_ACTIVE configured"` (`0x157890`). Neighbours in the same
   function: Audio byte 5 → `0x2`, MFL byte `0x0d` → `0x100`, Telefon byte `0x0f`
   → `0x1`, VZA byte 9 → `0x80`. Coding bit 87 is 0 in the default coding. The
   BAPStrecke handler before it (`0x1573f4–0x157690`) follows the same pattern
   (RDK byte 5 → `0x8`, OnlineFunctions byte `0x0e` → `0x400000`).
2. **No NavigationSD FSG (verified).** Without a peer answering FSG `0x32`,
   `GSS_BAP_NavigationSD` logs `setAvailability() to 'not available'` and
   `showKDKFlap ... m_OP_State 16`. With wire bit 14 set, mask `0x4` sent on
   LUN 6 CID 17, and the fixture answering, the trace shows
   `handle_BAP_Config(BAP_Version=3.0, LSG_Class=50, ..., LSG_Version=4.4)`,
   `setConnectionState(is_connected=1)`, `setAvailability() to 'available'`,
   `ASG Navigation went online!` (`0x17b8fc`). The view switch then goes to
   `SV_LVDS_FPK_NavMap` instead of `SV_LVDS_Nav_NA`.

The message text itself is `"Navigation is currently unavailable."` at file
offset `0x80afaa` (one of the localised string sets).

## 2. gss_ipc descriptors for FSG 0x32 (static)

- FSG descriptor `0x1a8618`: FSG `0x32`, BAP_Config bytes at `0x1a824c` =
  `03 00 32 00 04 04` (BAP 3.0, LSG class 50, subclass 0, LSG version 4.4).
- Function table `0x19d61c`, 46 rows of 40 bytes: `+4` function, `+8` size
  (low 16 bits), `+12` type (`0xf` = byte sequence), `+32` CAN CID.
- CIDs: GetAll (1) and large/list functions use CID 6; BAP_Config, FunctionList,
  Heartbeat, FSG_OperationState and the map properties use CID 5. LUN is 6.
- Type `0xf` properties carry a little-endian uint16 length inside GetAll
  (same rule as OnlineFunctions Info); FunctionList keeps its legacy fixed
  8 bytes. Among the properties used here only MapViewAndOrientation (`0x2c`)
  is type `0xf`.

## 3. NavigationSD function IDs (static)

The NavSD `notifyListeners` dispatcher at `0x78b250` switches on
`function - 1` (`cmp r3, #0x37; ldrls pc, [pc, r3, lsl #2]`). Each case logs the
property name, giving this map (sizes from the gss_ipc table):

| ID | Name | Size | ID | Name | Size |
| --- | --- | --- | --- | --- | --- |
| 0x01 | GetAll | var | 0x24 | VoiceGuidance | 1 |
| 0x02 | BAP_Config | 6 | 0x25 | FunctionSynchronisation | var |
| 0x03 | FunctionList | 8 | 0x26 | InfoStates | 1 |
| 0x0f | FSG_OperationState | 1 | 0x27 | ActiveRgType | 1 |
| 0x10 | CompassInfo | 3 | 0x2a | (gss row only) | 5 |
| 0x11 | RG_Status | 1 | 0x2b | MapColorAndType | 4 |
| 0x12 | DistanceToNextManeuver | 8 | 0x2c | MapViewAndOrientation | 7 |
| 0x13 | CurrentPositionInfo | var | 0x2d | MapScale | 6 |
| 0x14 | TurnToInfo | var | 0x2e | DestinationInfo | var |
| 0x15 | DistanceToDestination | 6 | 0x2f | Altitude | 3 |
| 0x16 | TimeToDestination | 7 | 0x30 | OnlineNavigationState | 3 |
| 0x1d | LastDest_List | var | 0x32 | SemidynamicRouteGuidance | var |
| 0x1e | FavoriteDest_List | var | 0x36 | Map_Presentation | 1 |
| 0x20 | NavBook | var | 0x38 | ETC_Status | 2 |
| 0x22 | RG_ActDeact | 1 | | | |

`indicationError(fctId=0x36, ...)` in the first run (Map_Presentation not in
the FunctionList) confirms the `id - 1` offset (verified).

## 4. FunctionList → availability flags (static, verified effect)

`[FunctionList.Status]` handling at `0x179608–0x1796d4` copies per-function
availability bytes from the BAP proxy objects into the AsgNavigation object:

| Flag | Source function |
| --- | --- |
| `+0x89d` | MapViewAndOrientation available |
| `+0x8a3` | MapColorAndType available |
| `+0x8a8` | MapScale available |

then calls, among others, `setMapColorAndTypeAvailable` (`0x1765c8`) and
`setMapDisplayAvailable` (`0x1764f4`). Without these three functions in the
FunctionList the Menu R options menu has no entries and does not open
(verified: first runs had no menu; after advertising them the menu opened).

## 5. Status layouts (static; field names from GTF2 log format strings)

- **MapColorAndType (0x2b)** Status: `Colour, ActiveMapType, MainMapSetup,
  SupportedMapTypes`; SetGet: `Colour, ActiveMapType, MainMapSetup, Reserve`.
  Handler `0x178dec` stores bytes into `+0x8a4..+0x8a7`.
- **MapViewAndOrientation (0x2c)** Status: `MapView, SupplementaryMapView,
  SupportedMapViews, SupportedSupplementaryMapViews, MapVisibility,
  MapOrientation, Modification`; SetGet: `MapView, SupplementaryMapView,
  Reserve1, Reserve2, MapVisibility, MapOrientation, Reserve3`. Stored into
  `+0x89e` (MapView), `+0x89f`, `+0x8a0` (SupportedMapViews), `+0x8a1`,
  `+0x8a2` (MapOrientation). `MapVisibility` bit 1 opens the KDK hole for the
  LVDS map (`"mapVisibility BIT1 set to true, KDK hole will be opened"`).
- **MapScale (0x2d)** Status: `Reserve1, AutoZoom, AutoZoomState, Scale, Unit,
  SupportedAutoZoom`; SetGet: `Steps, AutoZoom, AutoZoomState, Reserve2..4`.
- **Map_Presentation (0x36)**: one byte `ASG_HMI_State` (Status log also has a
  `PresentationCapabilities` variant string).
- **RG_Status (0x11)**, **VoiceGuidance (0x24)**: one byte each.

The SetGet layouts matter: the FSG must not copy Reserve bytes over the
`Supported*` fields. When the map view is entered GTF2 sends
`MapViewAndOrientation` SetGet `00 00 00 00 01 00 00` as a **BAP-segmented**
request (`80 07 2c ac 00 00 00 00`, `c0 01 00 00`). If it is not answered,
`indicationError(fctId=0x2C, errorCode=0x22) 'retry time-out'` follows after
~6 s and the view switches to `SV_NavFPK_NA` (verified).

## 6. Menu R options menu (static logic, verified display)

DP writes in `setMapDisplayAvailable` / `setMapColorAndTypeAvailable`
(writer `0x69e968`); item names from the `RV_SideMenusNav` / `SV_Nav_Submenu_*`
widget bindings and the `set*Available` function names:

| DP | Meaning | Condition |
| --- | --- | --- |
| `0x4000061` | "Map display" entry | MapView available and SupportedMapViews ∉ {0, 1, 2, 4} |
| `0x4000060` | "Map orientation" entry (`MapType` item) | MapView available and SupportedMapTypes bit 2 |
| `0x4000062` | "Map colours" entry | MapColorAndType and MapView available and SupportedMapTypes ≠ 0 |
| `0x400005f` | "Automatic zoom" entry | `setAutozoomAvailable` (MapScale) |
| `0x4000063` | "Stop route guidance" entry | `setCancelRouteGuidanceAvailable` (RG_Status) |

Verified: with SupportedMapViews `0x07`, SupportedMapTypes `0x3f`,
SupportedAutoZoom `0x07` and RG_Status 0, Menu R on `SV_LVDS_FPK_NavMap`
shows "Options" with *Map colours, Map display, Map orientation, Automatic zoom*.
Which of `0x4000060` / `0x4000062` is which label is inferred from the
conditions, not from a binding record.

Active-selection DPs: `0x4000065` map colour, `0x4000066` map display,
`0x4000067` map type, `0x4000068` voice, `0x4000064` auto zoom.

### 6.1 Map types (static; not exercised on screen)

`sendMapType(index)` (`0x1771e4`) and `updateActiveMapType` (`0x1766b4`) are
mutually consistent:

| Submenu item | Index (`0x4000067`) | ActiveMapType | MapOrientation | SupportedMapTypes bit |
| --- | --- | --- | --- | --- |
| `mapType_2dPos` (heading up) | 1 | 1 | 2 | 2 (DP `0x4000073`) |
| `mapType_2dNorth` | 2 | 1 | 1 (any ≠ 2 on receive) | 2 (DP `0x4000072`) |
| `mapType_3dMap` | 3 | 2 | 2 | 3 (DP `0x4000074`) |
| `mapType_Overview` | 4 | 3 | unchanged | 4 (DP `0x4000076`) |
| `mapType_Destination` | 5 | 0 | unchanged | 1 (DP `0x4000075`) |
| `mapType_RangeMap` | 6 | 4 | unchanged | 5 (DP `0x4000077`) |

So bit `n + 1` of SupportedMapTypes enables ActiveMapType `n`; bit 0 is unused.
Widget → visibility-DP pairs come from the binding records
(`SV_Nav_Submenu_MapType.GlassPlate.Menu.*`); the record layout puts the DP at
varying offsets, so the pairing is static evidence only.

### 6.2 Map colours and map display (static)

- `sendMapColor(index)` (`0x176c8c`): index 1/2/3 (`mapColor_day`, `_night`,
  `_auto`) → Colour 0/1/2. Receive maps Colour 0..2 through table `0x7d1b1c`
  `[1, 2, 3]` to the index; other values → 0.
- `sendMapDisplay(index)` (`0x1772f4`): index 1/2/3 (`mapDisplay_Standard`,
  `_GoogleEarth`, `_Verkehr`) → MapView via table `0x7d1af4` `[1, 0, 2]`.
  Visibility: SupportedMapViews bit 0 Standard (`0x4000070`), bit 1 Google
  Earth (`0x400006f`), bit 2 traffic (`0x4000071`).
- Auto-zoom items: `autoZoom_Kreuzung` / `_aus` / `_ein` (DPs `0x4000069..6b`).

The submenu has exactly three map-display items. Index bounds (`cmp r3, #2`),
the three-entry tables and the three visibility bits are compiled in, so a
fourth option (e.g. CarPlay) would require patching the widget tree, a new
visibility DP, texts and both tables. CarPlay/Android Auto strings in GTF2
exist only as audio-source texts (static).

## 7. Map_Presentation: ASG → FSG HMI state (static, verified traffic)

Map_Presentation is the cluster reporting its own state to the navigation
FSG, not data from the FSG:

- `sendStageInfo()` (`0x176de0`) takes the last reported value (`+0x8b0`),
  sets bit 0 when the current stage (`+0x95c`) is 1 and clears it when the
  stage is 0; any other stage logs `"unknown current stage"` and sends
  nothing. Stage is initialised to 2 (`0x179d30`) and updated from the
  `eSIDAppStageChange` message (`0x17bd50`). It then issues SetGet through
  `startNextMPRequest` (`0x176d4c`), which is suppressed while OP_State ≠ 0.
- The Status handler (`0x178280`) stores the FSG's byte at `+0x8b0`; if
  `(status & 1) != stage`, it calls `sendStageInfo()` again.
- What stage 0/1 means is inferred (probably classic vs. large-map cluster
  layout, toggled by VIEW); not verified.
- Every FSG_OperationState Status also triggers `sendStageInfo()` via
  `0x179400–0x17942c`. A fixture that repeats OperationState every second
  therefore causes a Map_Presentation SetGet every second (verified).

## 8. What remains unemulated

- The map image: GTF2 only opens a hole (`KDK`) for the LVDS video from the
  head unit. No LVDS video path exists in the emulator, so the map area stays
  black in every mode. Any real map/CarPlay content needs that path first.
- Route guidance (RG_Status, maneuvers, distances, lists) is not implemented
  by the fixture; "Stop route guidance" stays hidden.
- Selecting submenu items was not checked on screen; the fixture answers
  Set/SetGet by updating the writable fields only.
