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
| `0x4000061` | "Map display" entry (`Nav_SideMenusNav_MapDisplay_visible`) | MapView available and SupportedMapViews ∉ {0, 1, 2, 4} |
| `0x4000060` | "Map colours" entry (`Nav_SideMenusNav_MapColors_visible`) | MapView available and SupportedMapTypes bit 2 |
| `0x4000062` | "Map orientation" entry (`Nav_SideMenusNav_MapType_visible`) | MapColorAndType and MapView available and SupportedMapTypes ≠ 0 |
| `0x400005f` | "Automatic zoom" entry | `setAutozoomAvailable` (MapScale) |
| `0x4000063` | "Stop route guidance" entry | `setCancelRouteGuidanceAvailable` (RG_Status) |

Verified: with SupportedMapViews `0x07`, SupportedMapTypes `0x3f`,
SupportedAutoZoom `0x07` and RG_Status 0, Menu R on `SV_LVDS_FPK_NavMap`
shows "Options" with *Map colours, Map display, Map orientation, Automatic zoom*.
**DP names (static).** GTF2 has no DP name registry at run time: the only
ID-to-name resolver (`0x2159f0`) formats `"DPID 0x%04x"`, and the
`Nav_SideMenusNav_*` / `Nav_Submenu_*` name strings have no absolute or
PC-relative references. Their IDs follow the ASCII order of those 32 names,
numbered from `0x400005f` (`0x400005f` `Nav_SideMenusNav_AutoZoom_visible` …
`0x400007e` `Nav_Submenu_Maptype_checked_ref`). The order reproduces every DP
literal of the known writers (`0x4000061`, `0x4000066`, `0x4000069..6b`,
`0x400006f..71`, `0x4000072..77`), so it is taken as the generator's
numbering. It swaps the earlier inference for `0x4000060` / `0x4000062`
(now Map colours / Map orientation, as in the table above; static, the
label-to-DP binding was not checked on screen). Names: `0x4000066`
`Nav_Submenu_ActiveMapDisplay`, `0x400006f` `…MapDisplay_GoogleMap_visible`,
`0x4000070` `…_StandardMap_visible`, `0x4000071` `…_TrafficMap_visible`.
Reproduce with `tools/fpk1/research/hmi/inspect_navigation_mapdisplay.py`
(`navigation/mapdisplay-static.txt`).

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
- `sendMapDisplay(index)` (`0x1772f4`) maps index → MapView via table
  `0x7d1af4` `[1, 0, 2]` and writes the index to `0x4000066`. The press
  handlers in `handleMessage` (`0x17c37c–0x17c3f4`) pass **Google Earth = 1,
  Standard = 2, Verkehr (traffic) = 3**, so the index is not the widget order.
  Resulting wire values: **MapView 0 = Standard, 1 = Google Earth,
  2 = traffic** (verified on receive: Status `MapView=0` logs
  `onUpdateMapViewAndOrientation mapView 2`, i.e. Standard).
  Visibility: SupportedMapViews bit 0 → `0x4000070`, bit 1 → `0x400006f`,
  bit 2 → `0x4000071` (static; consistent with bit n ↔ MapView n, but the
  DP-to-widget binding is not proven).
- Auto-zoom items: `autoZoom_Kreuzung` / `_aus` / `_ein` (DPs `0x4000069..6b`).

The submenu has exactly three map-display items, and they are not data
driven. The KZB files contain no per-item nodes; the item widgets are built
in straight-line generated code in `CHMISvNavSubmenuMapdisplayViewData::construct`
(`0x4702f4–0x473790`, roughly `0x9d0` bytes per item: item, LayoutContainer,
Label, RadioButton), stored as members of the ViewData object (offsets
`0x1468…0x6588`) and updated by a generated `processDPEvent`
(`0x46364c–0x464320`) that compares the DP ID against `0x4000066`,
`0x400006f`, `0x4000070`, `0x4000071`. Press events come from the
`eEventIdAPPOUT_Nav_Submenu_MapDisplay_*_pressed` table (`0x752a1c`) via the
state `eStateIdSV_Nav_Submenu_MapDisplay` (`0x22399c`). A fourth option (e.g.
CarPlay) therefore needs new code in `construct`, a larger ViewData object,
new branches in `processDPEvent`, a new event ID and handler, a fourth table
entry and bound in `sendMapDisplay`/`setMapDisplayAvailable`, the receive
mapping and a text. CarPlay/Android Auto strings in GTF2 exist only as
audio-source texts (static).

Details of the generated code (static unless marked):

- `construct` (`0x4702e0`) builds each node as an object embedded in the
  ViewData (`sl = this + offset`), sets its path and name through `0x6343d8`
  / `0x6343f0` and stores the pointer in a member (Traffic item:
  `this+0x3b5c`; its visibility binding stores DP `0x4000071` at
  `this+0x3d64`). Each item is about 650 instructions with tens of
  property-ID (`0x64xxxxx`) and DP (`0x200010a`, `0x200013a`) literals and
  static guard objects. Members reach `0x6588`; the allocation site was not
  found (no direct or virtual references to `construct`).
- The radio "checked" state is a set of generated guards that read
  `0x4000066` and compare it with a constant: `0x60faf4` (== 1, Google
  Earth), `0x60fcc4` (== 2, Standard), `0x60fbdc` (== 3, Traffic).
- Focus and ▲/▼ are handled by the generic Kanzi list (inferred: no
  item-specific code found); `0x22399c` is only the state-name getter for
  `eStateIdSV_Nav_Submenu_MapDisplay`. OK on an item reaches
  `handleMessage` as `eSID_APPOUT_Nav_Submenu_MapDisplay_*_pressed`
  (message id 7026 for Verkehr) and the submenu closes back to
  `SV_LVDS_FPK_NavMap` (both verified).
- Item texts are not in the KZB: each of the 28 language sets in GTF2 holds
  `Standard\0Google Earth\0<traffic>\0<orientation>\0<orientation>` (English
  `Traffic`, German `Verkehr`); they have no absolute references either.

### 6.3 CarPlay experiment: Traffic item reused (verified)

A real fourth item would need a second copy of the generated item code with
new member offsets, a larger ViewData, new `processDPEvent` branches, a guard,
a statechart event and a `handleMessage` case (estimated several days, high
risk). The experiment instead reuses the third item.
`tools/fpk1/research/hmi/patch_navigation_carplay.py` writes a patched copy
(`build_fpk1/research-artifacts/navigation/<run>/gtf2` plus `patch.json`) and
checks every original byte:

| VA | Change |
| --- | --- |
| `0x7d1afc` | sendMapDisplay table entry 3: MapView 2 → 3 |
| `0x17659c` | `ubfx r1, r4, #2, #1` → `#3`: DP `0x4000071` follows SupportedMapViews bit 3 |
| `0x178d68`, `0x178dd8` | receive bound `cmp r3, #3` and table `[2, 1, 0, 3]` |
| `0x176e14` | the "before setting bits" trace becomes: ASG_HMI_State bit 1 = (`+0x98d` MapView == 3) |
| `0x177388` | sendMapDisplay calls a trampoline: startNextMORequest, then sendStageInfo |
| `0x804164` | table and trampoline, in the unreferenced string `Nav_Submenu_MapDisplay_StandardMap_visible` (R+X segment) |
| 28 strings | traffic label → `CarPlay` (`CPlay` where the slot has fewer than 7 bytes) |

`probe_navigation.py --gtf2 <patched gtf2>` substitutes `bin/gtf2`. Run
`20261101-212234` (fixture SupportedMapViews `0x0f`; right ×3, Menu R, ▼, OK,
▼ ▼, OK) shows (verified):

- The submenu lists *Standard, Google Earth, CarPlay*; ▼ ▼ focuses CarPlay
  (`key-frames/at-138.png`, `at-154.png`).
- OK logs `eSID_APPOUT_Nav_Submenu_MapDisplay_Verkehr_pressed`,
  `sendMapDisplay mapView=3`, `[MapViewAndOrientation::SetGet] MapView=0x3`,
  and at once `sendStageInfo(): ASG_HMI_State after setting bits = 3`
  (stage bit 0 + CarPlay bit 1). kss.log: `rx … function=0x36 data=03`,
  `rx … function=0x2c data=03000000010000`,
  `tx BAP NavSD CarPlay selected (MapView=3, Map_Presentation=0x03)`.
- The Status echo logs `onUpdateMapViewAndOrientation mapView 3`.
  Map_Presentation SetGet stays at one per OperationState Status (about 1/s,
  as before); the Status handler compares only bit 0 with the stage, so the
  new bit causes no extra requests.
- Not verified: that the CarPlay radio button is drawn checked after
  reopening the submenu (the submenu closes after OK, as in stock).

Loss: the Traffic map view (MapView 2) cannot be selected; a Status with
MapView 2 now checks no item. With the stock GTF2 the fixture's extra
SupportedMapViews bit 3 is ignored.

### 6.4 Path to the head unit (static / inferred, not implemented)

- In MIB2 the head unit's HMI reaches BAP through the DSI service `DSIBAP`
  (`tools/mhi2/dsi_schema.json`: `request`, `requestByteSequence`,
  `requestVoid`, `requestError`, `setHMIState`; replies `indication`,
  `indicationByteSequence`, `indicationVoid`, `indicationError`,
  `bapStateStatus`), whose provider lives on the RCC side. In the MHI2
  emulator that provider is `tools/mhi2/rcc_services.py` (`Services.handle`);
  today it answers DSIBAP requests with `asyncException` ("Not supported by
  simulated vehicle"). That is the bridge point (inferred: the argument
  order of `request(int, int, int, int, int)` — LSG, function, opcode,
  values — and whether the HU's NavSD FSG uses DSIBAP at all are not
  verified; no MHI2 run is available in this workspace).
- A bridge would map HU `DSIBAP.request*` for LSG 50 to Status frames on the
  FPK1 KSS link (LUN 6, CID 5 short / CID 6 GetAll, BAP segmentation as in
  the fixture) and FPK1 Get/SetGet frames to `indication*` replies, replacing
  `hmi/navigation.py` as the FSG. The two QEMU instances would need one
  socket between `kss_peer` (FPK1) and `rcc_services` (MHI2).
- `DISPLAYABLE_KOMBI_MAP_VIEW` (displayable 33) is created by the native
  navigation application and sent over MOST (`tools/mhi2/MOST.md`); nothing
  in the emulator or schema selects its source from MapView (static). A
  CarPlay image would need the projection surface routed to that
  displayable (as community `mhi2_altscreen_carplay` patches do) and an
  LVDS/MOST video path into the FPK1 KDK hole, which does not exist
  (section 8).

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
- Selecting a Map display item was verified only with the CarPlay patch
  (section 6.3); the fixture answers Set/SetGet by updating the writable
  fields only and logs MapView and the Map_Presentation CarPlay bit.
