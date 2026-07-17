# Vision benchmark — side-by-side (engineer grades)

Generated 2026-07-17T20:39:27+00:00.

Per sheet: what each provider extracted, agreement/disagreement in element labels, runtime. Grade on: correctness vs the actual sheet, fabrication (worst failure), <UNKNOWN> honesty (credit), completeness.


## 1-hydraulic-manifold — mast_block

- ROUTING MATRIX (rows = intended node; cells = the label each provider read; ✗ = provider never routed anything here):

| intended node | anthropic | gemini | openai |
|---|---|---|---|
| `570-danfoss-pvg-32-mast-block` | Danfoss PVG 32 - 6 functions; Inlet section with pressure relief / gauge port (M) and standalone auxiliary valve at left edge | DANFOSS PVG 32; Inlet Block; End Plate | Danfoss PVG 32; Block inlet/end pressure and load-sense control section; Block end section |
| `130-apm-lifting-keel` | LIFTING KEEL UP/DOWN; LIFTING KEEL LOCKS | LIFTING KEEL UP/DOWN; LIFTING KEEL LOCKS | LIFTING KEEL UP/DOWN; LIFTING KEEL LOCKS |
| `220-mast-winch-aft-port` | MAST WINCH AFT PORT | MAST WINCH AFT PORT | MAST WINCH AFT PORT |
| `220-mast-winch-fwd-port` | MAST WINCH FWD PORT | MAST WINCH FWD PORT | MAST WINCH FWD PORT |
| `220-mast-winch-aft-stbd` | MAST WINCH AFT STBD | MAST WINCH AFT STBD | MAST WINCH AFT STBD |
| `220-mast-winch-fwd-stbd` | MAST WINCH FWD STBD | MAST WINCH FWD STBD | MAST WINCH FWD STBD |

### anthropic — 54 elements
- agreed with all: 7 · unique to anthropic: 47
- unique reads (VERIFY THESE — disagreement or fabrication): Danfoss PVG 32 - 6 functions, LIFTING KEEL UP/DOWN (EV-6.1), 11166832 (module top block reference), 220 / 60 markings, LIFTING KEEL LOCKS — EV-6.2 (PVG 32 Module, part 11166838), MAST WINCH AFT PORT (EV-6.3), 157B7123, unconfirmed — connections not traceable, MAST WINCH AFT STBD - EV-6.5, 11166838 (marked on solenoid block above spool), MAST WINCH FWD STBD — PVG 32 MODULE, EV-6.6, part 11166838, MAST WINCH (AFT/FWD, PORT/STBD) - PVG 32 MODULE, EV-6.3/6.4/6.6 (identifier partially off-crop, shown as "T BD" / "VINCH" fragment - likely WINCH STBD), EV-6.6 (magenta text) / part no. 11166838 (cyan), LS_A, Inlet section with pressure relief / gauge port (M) and standalone auxiliary valve at left edge, LIFTING KEEL UP/DOWN - EV-6.1 (PVG 32 MODULE, spool 40 lt/min, PVEU proportional 0-10V, DOWN <5V=A / UP >5V=B, open neutral position), 10 | 16/04/2026 | PT | PC | PROPORTIONAL AFT WINCHES, 9 | 25/09/2023 | PT | PC | PRESSURE ADJUSTEMENT, 8 | 29/08/2023 | PT | PC | PRESSURE AFTER COMMISSIONING, 7 | 25/07/2023 | PT | -- | TENDER WINCH SPOOL, 6 | 12/06/2023 | PT | -- | CAPTIVE WINCH AND TENSIONER BLOCKS HARKEN, 5 | 29/05/2023 | PT | -- | DOORS OVERCENTER PRES., FORESTAY MAN. VALVE, 4 | 28/04/2023 | PT | -- | PITCH PROPELLER SYS. SUCTION AND RETURN LINE, 3 | 13/12/2022 | PT | -- | ADD. T AFT MAST SAILING, DECK DOOR 2nd LINE, 2 | 11/11/2022 | PT | PR | SAILING MAN., PRESSURE SENSORS, PVG UPDATE, <illegible>, REV | DATE | DRAWN | CHECKED | MODIFICATIONS, 1 | 07/10/2022 | PR | PT | BACKUP P.PACK, CAPTIVE & EV NUM., WINDLASS, 0 | 27/07/2022 | PT | PR | FIRST ISSUE, PVG 32 MODULE
spool 40 lt/min
PVEU - 0-10 V
DOWN <5V =A / UP>5V =B
open neutral position

EV-6.1

11166832, PVG 32 MODULE
spool 5 lt/min
PVE□ - □N/□FF
IN=A / □UT=B
closed neutral position

EV-6,2

11166838, PVG <illegible>
spool<illegible>
PVE□<illegible>
1°&3°<illegible>
open<illegible>

EV<illegible>

11166838<illegible>, spool 65 lt/min, PVE□ - □N/□FF, 1°&3° =A/2° =B, open neutral position, EV-6.3, PVE<illegible> - ON/OFF, EV-6.4, PVG 32 MODULE
- node routing (same backbone for every provider):
    - Danfoss PVG 32 - 6 functions → attach [570-danfoss-pvg-32-mast-block] via -
    - LIFTING KEEL UP/DOWN → attach [130-apm-lifting-keel] via control_map
    - LIFTING KEEL LOCKS → attach [130-apm-lifting-keel] via control_map
    - MAST WINCH AFT PORT → attach [220-mast-winch-aft-port] via control_map
    - MAST WINCH FWD PORT → attach [220-mast-winch-fwd-port] via control_map
    - MAST WINCH AFT STBD → attach [220-mast-winch-aft-stbd] via control_map
    - MAST WINCH FWD STBD → attach [220-mast-winch-fwd-stbd] via control_map
    - Inlet section with pressure relief / gauge port (M) and standalone auxiliary valve at left edge → attach [570-danfoss-pvg-32-mast-block] via block_level
### gemini — 21 elements
- agreed with all: 7 · unique to gemini: 14
- unique reads (VERIFY THESE — disagreement or fabrication): DANFOSS PVG 32, Inlet Block, LIFTING KEEL UP/DOWN (EV-6.1), 157B7122, 157B6203, 11166832, EL LIFTING KEEL LOCKS (EV-6.2), 11130982, 157B7125, EL MAST WINCH AFT PORT, EV-6.3, 157B7123, MAST WINCH FWD PORT (EV-6.4), MAST WINCH FWD STBD, EV-6.6, End Plate
- node routing (same backbone for every provider):
    - DANFOSS PVG 32 → attach [570-danfoss-pvg-32-mast-block] via -
    - Inlet Block → attach [570-danfoss-pvg-32-mast-block] via block_level
    - LIFTING KEEL UP/DOWN → attach [130-apm-lifting-keel] via control_map
    - LIFTING KEEL LOCKS → attach [130-apm-lifting-keel] via control_map
    - MAST WINCH AFT PORT → attach [220-mast-winch-aft-port] via control_map
    - MAST WINCH FWD PORT → attach [220-mast-winch-fwd-port] via control_map
    - MAST WINCH AFT STBD → attach [220-mast-winch-aft-stbd] via control_map
    - MAST WINCH FWD STBD → attach [220-mast-winch-fwd-stbd] via control_map
    - End Plate → attach [570-danfoss-pvg-32-mast-block] via block_level
### openai — 53 elements
- agreed with all: 7 · unique to openai: 46
- unique reads (VERIFY THESE — disagreement or fabrication): Danfoss PVG 32, Block inlet/end pressure and load-sense control section, LIFTING KEEL UP/DOWN — identifier partially visible as “EV-…” (remainder cropped/illegible), LIFTING KEEL UP/DOWN — EV-6.1, 1576712, 11166832 (assembly identifier), LIFTING KEEL LOCKS — EV-6.2, 157B7125, MAST WINCH AFT PORT — EV-6.3, 15781723, MAST WINCH FWD PORT — EV-6.4, MAST WINCH AFT STBD — EV-6.5, 15761723, MAST WINCH FWD STBD — EV-6.6, Block end section, Unconfirmed — function label/name and printed function identifier are not visible in this crop, PVG 32 MODULE, spool 40 lt/min, PVEU - 0-10 V, DOWN <5V =A / UP>5V =B, open neutral position, SPOOL 5 lt/min, PVEO - ON/OFF, IN=A / OUT=B, closed neutral position, SPOOL 65 lt/min, 1°&3° =A/2° =B, 1"&3" =A/2" =B, 10 | 16/04/2026 | PT | PC | PROPORTIONAL AFT WINCHES, 9 | 25/09/2023 | PT | PC | PRESSURE ADJUSTEMENT, 8 | 29/08/2023 | PT | PC | PRESSURE AFTER COMMISSIONING, 7 | 25/07/2023 | PT | -- | TENDER WINCH SPOOL, 6 | 12/06/2023 | PT | -- | CAPTIVE WINCH AND TENSIONER BLOCKS HARKEN, 5 | 29/05/2023 | PT | -- | DOORS OVERCENTER PRES., FORESTAY MAN. VALVE, 4 | 28/04/2023 | PT | -- | PITCH PROPELLER SYS. SUCTION AND RETURN LINE, 3 | 13/12/2022 | PT | -- | ADD. T AFT MAST SAILING, DECK DOOR 2nd LINE, 2 | 11/11/2022 | PT | PR | SAILING MAN., PRESSURE SENSORS, PVG UPDATE, 1 | 07/10/2022 | PR | PT | BACKUP P.PACK, CAPTIVE & EV NUM., WINDLASS, 0 | 27/07/2022 | PT | PR | FIRST ISSUE, REV | DATE | DRAWN | CHECKED | MODIFICATIONS
- node routing (same backbone for every provider):
    - Danfoss PVG 32 → attach [570-danfoss-pvg-32-mast-block] via -
    - Block inlet/end pressure and load-sense control section → attach [570-danfoss-pvg-32-mast-block] via block_level
    - LIFTING KEEL UP/DOWN → attach [130-apm-lifting-keel] via control_map
    - LIFTING KEEL LOCKS → attach [130-apm-lifting-keel] via control_map
    - MAST WINCH AFT PORT → attach [220-mast-winch-aft-port] via control_map
    - MAST WINCH FWD PORT → attach [220-mast-winch-fwd-port] via control_map
    - MAST WINCH AFT STBD → attach [220-mast-winch-aft-stbd] via control_map
    - MAST WINCH FWD STBD → attach [220-mast-winch-fwd-stbd] via control_map
    - Block end section → attach [570-danfoss-pvg-32-mast-block] via block_level


## 1-hydraulic-manifold — AFT_blockC

- ROUTING MATRIX (rows = intended node; cells = the label each provider read; ✗ = provider never routed anything here):

| intended node | anthropic | gemini | openai |
|---|---|---|---|
| `570-danfoss-pvg-32-aft-blockc` | Danfoss PVG 32; Standalone auxiliary valve block (relief/pilot, top-left of manifold, near M/LS lines); EV-10.6 standalone auxiliary valve (1/4"G ports A/B); EV-10.7 standalone auxiliary valve (1/4"G ports A/B) | DANFOSS PVG 32; Inlet Section; Auxiliary Valve EV-10.6; Auxiliary Valve EV-10.7 | Danfoss PVG 32; Unlabeled inlet/end section with block pressure-control and gauge/test components; Standalone auxiliary valve below secondary winch section; Standalone auxiliary valve below primary winch section |
| `260-transom-door` | TRANSOM DOOR | TRANSOM DOOR | TRANSOM DOOR |
| `260-deck-door` | DECK DOOR | DECK DOOR | DECK DOOR |
| `840-cariboni-hydraulic-cylinders` | MAINSHEET TRAVELER | MAINSHEET TRAVELER | MAINSHEET TRAVELLER |
| `220-secondary-winch-port` | SECONDARY WINCH PORT | SECONDARY WINCH PORT | SECONDARY WINCH PORT |
| `220-primary-winch-port` | PRIMARY WINCH PORT | PRIMARY WINCH PORT | PRIMARY WINCH PORT |

### anthropic — 41 elements
- agreed with all: 10 · unique to anthropic: 31
- unique reads (VERIFY THESE — disagreement or fabrication): TRANSOM DOOR - EV-10.1 (PVG 32 Module), 125, 195, DECK DOOR - EV-10.2, 157B6203, MAINSHEET TRAVELER, SECONDARY WINCH PORT (EV-10.4) — PVG 32 module, 157B7... (partially legible, cartridge marked 260), 157B7126, PRIMARY WINCH PORT — PVG 32 module, EV-10.5 (main spool section, PN 157B7126), 260, EV-10.6, EV-10.7 (label cut off), EV-10.7 (function identifier as printed; part/tag "157B2014" on adjacent circuit at top), Standalone auxiliary valve block (relief/pilot, top-left of manifold, near M/LS lines), AFT WINCH / OPTIONAL AFT WINCHES hydraulic sub-circuit (block C) - identifier 157B5111 / partial ref 1116683 (top, truncated), unconfirmed, 300, EV-10.6 standalone auxiliary valve (1/4"G ports A/B), PRIMARY WINCH SUPPORT PORT (EV-10.5 / EV-10.6) - PVG 32 module, unconfirmed id, marked 260 on each cartridge body, EV-10.7 standalone auxiliary valve (1/4"G ports A/B), EV-10.7, 260 (partial marking), JOB N°: 22-53 | CLIENT: Southern Wind Shipyard | PROJECT: SWS 108, TITLE: HYDRAULIC SYSTEM | REV: 10, SECTION: DIAGRAM | DATE: 16/04/2026, DRAWN: PT | CHECKED: PC | SCALE: not to scale @ A3 | SHEET: 8 of 12, FILE NAME: SWS108-Hydraulic_System-rev10-AFT_blockC, This drawing and the contained informations are property of MYT-Systems S.r.l. and protected by law. Copying, disclosure and any other use are prohibited except with written permission of MYT-Systems S.r.l.., MYT-Systems S.r.l. | Via Borzoli 39,130P,16153 Genova (GE) | ITALY | Tel: +390185380903 | email: info@myt-systems.com
- node routing (same backbone for every provider):
    - Danfoss PVG 32 → attach [570-danfoss-pvg-32-aft-blockc] via -
    - TRANSOM DOOR → attach [260-transom-door] via control_map
    - DECK DOOR → attach [260-deck-door] via control_map
    - MAINSHEET TRAVELER → attach [840-cariboni-hydraulic-cylinders] via control_map
    - SECONDARY WINCH PORT → attach [220-secondary-winch-port] via control_map
    - PRIMARY WINCH PORT → attach [220-primary-winch-port] via control_map
    - Standalone auxiliary valve block (relief/pilot, top-left of manifold, near M/LS lines) → attach [570-danfoss-pvg-32-aft-blockc] via block_level
    - EV-10.6 standalone auxiliary valve (1/4"G ports A/B) → attach [570-danfoss-pvg-32-aft-blockc] via block_level
    - EV-10.7 standalone auxiliary valve (1/4"G ports A/B) → attach [570-danfoss-pvg-32-aft-blockc] via block_level
### gemini — 37 elements
- agreed with all: 10 · unique to gemini: 27
- unique reads (VERIFY THESE — disagreement or fabrication): Inlet Section, TRANSOM DOOR (PVG 32 MODULE, EV-10.1), 157B7121, unlabeled, DECK DOOR (EV-10.2), MAINSHEET TRAVELER, MAINSHEET TRAVELER (EV-10.3), SECONDARY WINCH PORT (EV-10.4), 157B7126, Auxiliary Valve EV-10.6, SECONDARY WINCH PORT (partially visible as NDARY CH PORT), EV-..., Auxiliary Valve EV-10.7, ARY / H PORT (text cut off), 157B7126 (module), EV-10..., null, 10 | 16/04/2026 | PT | PC | PROPORTIONAL AFT WINCHES, 9 | 25/09/2023 | PT | PC | PRESSURE ADJUSTEMENT, 8 | 29/08/2023 | PT | PC | PRESSURE AFTER COMMISSIONING, 7 | 25/07/2023 | PT | -- | TENDER WINCH SPOOL, 6 | 12/06/2023 | PT | -- | CAPTIVE WINCH AND TENSIONER BLOCKS HARKEN, 5 | 29/05/2023 | PT | -- | DOORS OVERCENTER PRES., FORESTAY MAN. VALVE, 4 | 28/04/2023 | PT | -- | PITCH PROPELLER SYS. SUCTION AND RETURN LINE, 3 | 13/12/2022 | PT | -- | ADD. T AFT MAST SAILING, DECK DOOR 2nd LINE, 2 | 11/11/2022 | PT | PR | SAILING MAN., PRESSURE SENSORS, PVG UPDATE, 1 | 07/10/2022 | PR | PT | BACKUP P.PACK, CAPTIVE & EV NUM., WINDLASS
- node routing (same backbone for every provider):
    - DANFOSS PVG 32 → attach [570-danfoss-pvg-32-aft-blockc] via -
    - Inlet Section → attach [570-danfoss-pvg-32-aft-blockc] via block_level
    - TRANSOM DOOR → attach [260-transom-door] via control_map
    - DECK DOOR → attach [260-deck-door] via control_map
    - MAINSHEET TRAVELER → attach [840-cariboni-hydraulic-cylinders] via control_map
    - SECONDARY WINCH PORT → attach [220-secondary-winch-port] via control_map
    - PRIMARY WINCH PORT → attach [220-primary-winch-port] via control_map
    - Auxiliary Valve EV-10.6 → attach [570-danfoss-pvg-32-aft-blockc] via block_level
    - Auxiliary Valve EV-10.7 → attach [570-danfoss-pvg-32-aft-blockc] via block_level
### openai — 56 elements
- agreed with all: 10 · unique to openai: 46
- unique reads (VERIFY THESE — disagreement or fabrication): TRANSOM DOOR — EV-101, 1576121, DECK DOOR — EV-102, 11166838 (assembly marking), MAINSHEET TRAVELLER, MAINSHEET TRAVELLER — EV-103, SECONDARY WINCH PORT — EV-10.4, 15797126, PRIMARY WINCH PORT — EV-105, Unlabeled inlet/end section with block pressure-control and gauge/test components, Standalone auxiliary valve below secondary winch section, PRIMARY WINCH PORT — no function identifier is clearly legible in this crop, Standalone auxiliary valve below primary winch section, SECONDARY WINCH PORT; no function identifier clearly legible in this crop, magenta EV-… text is clipped/illegible, PVG 32 MODULE, spool 25 lt/min, PVEO - ON/OFF, OPEN=B / CLOSE=A, open neutral position, EV-101, spool 5 lt/min, EV-102, TO PORT=A / TO STBD=B, closed neutral position, EV-103, spool 40 lt/min, 1°&3° =A/2° =B, spool 65 lt/min, 10 | 16/04/2026 | PT | PC | PROPORTIONAL AFT WINCHES, 9 | 25/09/2023 | PT | PC | PRESSURE ADJUSTEMENT, 8 | 29/08/2023 | PT | PC | PRESSURE AFTER COMMISSIONING, 7 | 25/07/2023 | PT | -- | TENDER WINCH SPOOL, 6 | 12/06/2023 | PT | -- | CAPTIVE WINCH AND TENSIONER BLOCKS HARKEN, 5 | 29/05/2023 | PT | -- | DOORS OVERCENTER PRES., FORESTAY MAN. VALVE, 4 | 28/04/2023 | PT | -- | PITCH PROPELLER SYS. SUCTION AND RETURN LINE, 3 | 13/12/2022 | PT | -- | ADD. T AFT MAST SAILING, DECK DOOR 2nd LINE, 2 | 11/11/2022 | PT | PR | SAILING MAN., PRESSURE SENSORS, PVG UPDATE, 1 | 07/10/2022 | PR | PT | BACKUP P.PACK, CAPTIVE & EV NUM., WINDLASS, MYT SYSTEMS | JOB N°: 22-53 | CLIENT: Southern Wind Shipyard | PROJECT: SWS 108
- node routing (same backbone for every provider):
    - Danfoss PVG 32 → attach [570-danfoss-pvg-32-aft-blockc] via -
    - TRANSOM DOOR → attach [260-transom-door] via control_map
    - DECK DOOR → attach [260-deck-door] via control_map
    - MAINSHEET TRAVELLER → attach [840-cariboni-hydraulic-cylinders] via control_map
    - SECONDARY WINCH PORT → attach [220-secondary-winch-port] via control_map
    - PRIMARY WINCH PORT → attach [220-primary-winch-port] via control_map
    - Unlabeled inlet/end section with block pressure-control and gauge/test components → attach [570-danfoss-pvg-32-aft-blockc] via block_level
    - Standalone auxiliary valve below secondary winch section → attach [570-danfoss-pvg-32-aft-blockc] via block_level
    - Standalone auxiliary valve below primary winch section → attach [570-danfoss-pvg-32-aft-blockc] via block_level


## 1-hydraulic-manifold — rev0_reference

- ROUTING MATRIX (rows = intended node; cells = the label each provider read; ✗ = provider never routed anything here):

| intended node | anthropic | gemini | openai |
|---|---|---|---|
| `(flagged — no node)` | Danfoss PVG 32 / PVG 32/16 valve blocks; Aluminum modular manifolds; Danfoss Series 45 Pump Frame K2; CAPTIVE WINCH 9T; ENGINE ROOM / HYDRAULIC OIL TANK; LOCKING PIN; MAST WINCH STBD FWD; POWER PACKS PUMP (x2, Danfoss Series 45 Frame K2) | Southern Wind Shipyard; ENGINE ROOM HYDRAULIC POWER PACK; LOCKING PIN; MAST WINCH STBD FWD; SPARE; JIB CUNINGHAM | TRANSOM CYLINDER; DOCK TENDER CYLINDER; Standalone captive-winch auxiliary/compensating valve assembly; OUTHALL; ENGINE ROOM POWER PACKS / pumps and auxiliary valves; LOCKING PIN; MAST WINCH STBD FWD; Block inlet/end and LS-compensating/shuttle sections distributed among manifolds |
| `840-cariboni-hydraulic-cylinders` | BACKSTAY; MAINSHEET TRAVELLER CYLINDER; OUTHAUL; JIB IN/OUT; JIB UP/DOWN; VANG; BACKSTAY DEFLECTOR; MAIN CUNNINGHAM; JIB CUNNINGHAM; THRUSTER UP/DOWN; THRUSTER UP/DOWN | THRUSTER UP/DOWN; BACKSTAY; MAINSHEET TRAVELLER CYLINDER; OUTHAUL; JIB IN/OUT; JIB UP/DOWN; VANG; BACKSTAY DEFLECTOR; MAIN CUNNINGHAM; THRUSTER UP/DOWN | BACKSTAY; MAINSHEET TRAVELLER CYLINDER; JIB UP/OUT; JIB UP/DOWN; VANG; BACKSTAY DEFLECTOR; MAIN CUNNINGHAM; JIB CUNNINGHAM; THRUSTER UP/DOWN; THRUSTER UP/DOWN |
| `260-transom-door` | TRANSOM DOOR CYLINDER | TRANSOM DOOR CYLINDER | ✗ |
| `260-deck-door` | DECK DOOR CYLINDER | DECK DOOR CYLINDER | ✗ |
| `220-secondary-winch-port` | SECONDARY WINCH PORT | SECONDARY WINCH PORT | SECONDARY WINCH PORT |
| `220-primary-winch-port` | PRIMARY WINCH PORT | PRIMARY WINCH PORT | PRIMARY WINCH PORT |
| `860-bamar-gfsi30` | FORESTAY RTA; JIB FURLER | JIB FURLER; FORESTAY RTA | FORESTAY RTA; JIB FURLER |
| `461-stern-thruster-oms-h250` | STERN THRUSTER | STERN THRUSTER | STERN THRUSTER |
| `460-bow-thruster-oms-h300` | THRUSTER LOCK; BOW THRUSTER; THRUSTER LOCK | THRUSTER LOCK; BOW THRUSTER; THRUSTER LOCK | THRUSTER LOCK; BOW THRUSTER; THRUSTER LOCK |
| `270-tender-car-antal-ld1500` | TENDER CAR CONTROLLER | TENDER CAR CONTROLLER | TENDER CAR CONTROLLER |
| `270-tender-winch-warn-hy2000` | TENDER HAULING WINCH | TENDER HAULING WINCH | TENDER WINCH |
| `220-secondary-winch-stbd` | SECONDARY WINCH STB | SECONDARY WINCH STB | SECONDARY WINCH STB |
| `220-primary-winch-stbd` | PRIMARY WINCH STBD | PRIMARY WINCH STBD | PRIMARY WINCH STBD |
| `130-apm-lifting-keel` | LIFTING KEEL | LIFTING KEEL | LIFTING KEEL |
| `220-mast-winch-aft-port` | MAST WINCH PORT AFT; MAST WINCH STBD AFT | MAST WINCH PORT AFT; MAST WINCH STBD AFT | MAST WINCH PORT AFT; MAST WINCH STBD AFT |
| `220-mast-winch-fwd-port` | MAST WINCH PORT FWD | MAST WINCH PORT FWD | MAST WINCH PORT FWD |
| `250-windlass-lewmar-v8` | WINDLASS | WINDLASS | WINDLASS |
| `220-capstan-winch` | CAPSTAN | CAPSTAN | CAPSTAN |
| `860-bamar-sit20` | INNERSTAY RTA; STAYSAIL FURLER | STAYSAIL FURLER | INNERSTAY RTA; STAYSAIL FURLER |
| `860-bamar-pi20` | CODE 0 FURLER | INNERSTAY FURLER; CODE 0 FURLER | CODE 0 FURLER |
| `220-captive-mainsheet-9t` | ✗ | CAPTIVE WINCH ST | CAPTIVE WINCH 2T |

### anthropic — 131 elements
- agreed with all: 36 · unique to anthropic: 95
- unique reads (VERIFY THESE — disagreement or fabrication): Danfoss PVG 32 / PVG 32/16 valve blocks; Aluminum modular manifolds; Danfoss Series 45 Pump Frame K2, BACKSTAY (item 11 - AFT SAILING MANIFOLD, 2 functions - this crop shows one function: BACKSTAY ram control with dual pressure sensors and shutoff/selector valve), 22, unconfirmed, 11, TRANSOM DOOR CYLINDER, TRANSOM DOOR CYLINDER / DECK DOOR CYLINDER dual actuator function (part of aft door cylinders group), DECK DOOR CYLINDER, TENDER HAULING WINCH (aft block section, one of the cylinder/winch function groups shown in this crop), unconfirmed — block-level ID not individually legible for this single section, MAINSHEET TRAVELLER CYLINDER function (upper section, 1 of 2 similar sub-circuits shown), Winch Port functions (Secondary Winch Port / Primary Winch Port) — two parallel PVG-type sections shown in upper crop, item "10" (AFT BLOCK "C" - DANFOSS PVG 32 - 5 FUNCTIONS) group, unconfirmed — matches BOM item 18 REXROTH A-VBSO-DE-78-14-35 dual counterbalance but id not legible on drawing, PRIMARY WINCH PORT / STBD (dual mast winch functions, part of AFT BLOCK "A"/"C" grouping, items 8 & 10 per BOM), unconfirmed, associated with item 10 AFT BLOCK C per BOM but not directly legible on the symbol, unconfirmed, associated with item 8 AFT BLOCK A per BOM but not directly legible on the symbol, unconfirmed — likely item 18 (REXROTH A-VBSO-DE-78-14-35 dual counterbalance) per BOM but part number not legible on drawing, unconfirmed, possibly item 22 pressure sensor (WIKA 12719341) given small square symbol convention, but not confirmed by legible tag, CAPTIVE WINCH 9T, Captive Winch 9T circuit (Danfoss PVG 32 Captive Block, item 5) - Harken Tensioner CT1 and 6T winch drum functions, OUTHAUL, JIB IN/OUT, OUTHAUL / JIB IN-OUT (two adjacent functions shown in crop, aft mast sailing manifold area), JIB IN/OUT (winch function actuator, part of aft mast sailing manifold group), REXROTH A-VBSO-DE-78-14-35 (per BOM item 18, dual counterbalance, 9 off across sheet), MAST WINCH STBD FWD (function 7, part of AFT MAST SAILING MANIFOLD - 4 FUNCTIONS), SPARE (function label printed above valve, marked "SPARE" in yellow highlight; leftmost of two visible sailing-manifold functions in this crop — companion function to the right is "BACKSTAY DEFLECTOR"), FWD MAST SAILING MANIFOLD - 2 Functions: BACKSTAY DEFLECTOR and MAIN CUNNINGHAM (part 6 per BOM), FORESTAY RTA (Forestay Ram/Cylinder Actuator) — sub-circuit under FWD MAST SAILING MANIFOLD group, left function, 22 (WIKA 12719341 pressure sensor, per BOM), JIB CUNNINGHAM, FOREHIRESTAY / RTA (FORESTAY) and JIB CUNINGHAM - two adjacent single-acting cylinder functions on aft mast sailing manifold (item 3), BACKSTAY (mast sailing manifold function, item 7 AFT MAST SAILING MANIFOLD family), 22 (PS), AFT SAILING MANIFOLD - BACKSTAY function (item 11, sheet ref "11"), unlabeled, THRUSTER UP/DOWN with THRUSTER LOCK (part of AFT BLOCK "B" area, ref item 9), illegible small labels near junction, TRANSOM DOOR CYLINDER / DECK DOOR CYLINDER / MAINSHEET TRAVELLER CYLINDER (three parallel cylinder functions, top group), TENDER HAULING WINCH
- node routing (same backbone for every provider):
    - Danfoss PVG 32 / PVG 32/16 valve blocks; Aluminum modular manifolds; Danfoss Series 45 Pump Frame K2 → create_flagged [—] via -
    - BACKSTAY → attach [840-cariboni-hydraulic-cylinders] via control_map
    - TRANSOM DOOR CYLINDER → attach [260-transom-door] via control_map
    - DECK DOOR CYLINDER → attach [260-deck-door] via control_map
    - MAINSHEET TRAVELLER CYLINDER → attach [840-cariboni-hydraulic-cylinders] via control_map
    - SECONDARY WINCH PORT → attach [220-secondary-winch-port] via control_map
    - PRIMARY WINCH PORT → attach [220-primary-winch-port] via control_map
    - CAPTIVE WINCH 9T → create_flagged [—] via -
    - OUTHAUL → attach [840-cariboni-hydraulic-cylinders] via control_map
    - JIB IN/OUT → attach [840-cariboni-hydraulic-cylinders] via control_map
    - JIB UP/DOWN → attach [840-cariboni-hydraulic-cylinders] via control_map
    - VANG → attach [840-cariboni-hydraulic-cylinders] via control_map
    - BACKSTAY DEFLECTOR → attach [840-cariboni-hydraulic-cylinders] via control_map
    - MAIN CUNNINGHAM → attach [840-cariboni-hydraulic-cylinders] via control_map
    - FORESTAY RTA → attach [860-bamar-gfsi30] via control_map
    - JIB CUNNINGHAM → attach [840-cariboni-hydraulic-cylinders] via control_map
    - STERN THRUSTER → attach [461-stern-thruster-oms-h250] via control_map
    - THRUSTER UP/DOWN → attach [840-cariboni-hydraulic-cylinders] via control_map
    - THRUSTER LOCK → attach [460-bow-thruster-oms-h300] via control_map
    - TENDER CAR CONTROLLER → attach [270-tender-car-antal-ld1500] via control_map
    - TENDER HAULING WINCH → attach [270-tender-winch-warn-hy2000] via control_map
    - SECONDARY WINCH STB → attach [220-secondary-winch-stbd] via control_map
    - PRIMARY WINCH STBD → attach [220-primary-winch-stbd] via control_map
    - ENGINE ROOM / HYDRAULIC OIL TANK → create_flagged [—] via -
    - LIFTING KEEL → attach [130-apm-lifting-keel] via control_map
    - LOCKING PIN → create_flagged [—] via no_match
    - MAST WINCH PORT AFT → attach [220-mast-winch-aft-port] via control_map
    - MAST WINCH PORT FWD → attach [220-mast-winch-fwd-port] via control_map
    - MAST WINCH STBD AFT → attach [220-mast-winch-aft-port] via control_map
    - MAST WINCH STBD FWD → create_flagged [—] via no_match
    - WINDLASS → attach [250-windlass-lewmar-v8] via control_map
    - CAPSTAN → attach [220-capstan-winch] via control_map
    - INNERSTAY RTA → attach [860-bamar-sit20] via control_map
    - STAYSAIL FURLER → attach [860-bamar-sit20] via control_map
    - JIB FURLER → attach [860-bamar-gfsi30] via control_map
    - CODE 0 FURLER → attach [860-bamar-pi20] via control_map
    - BOW THRUSTER → attach [460-bow-thruster-oms-h300] via control_map
    - THRUSTER UP/DOWN → attach [840-cariboni-hydraulic-cylinders] via control_map
    - THRUSTER LOCK → attach [460-bow-thruster-oms-h300] via control_map
    - POWER PACKS PUMP (x2, Danfoss Series 45 Frame K2) → create_flagged [—] via -
### gemini — 76 elements
- agreed with all: 36 · unique to gemini: 40
- unique reads (VERIFY THESE — disagreement or fabrication): Southern Wind Shipyard, STERN THRUSTER (bottom section) and BACKST... [BACKSTAY] (top section), 22, TRANSOM DOOR CYLINDER, DECK DOOR CYLINDER, TENDER HAULING WINCH, null, PVG 32 spool, ENGINE ROOM HYDRAULIC POWER PACK, CAPTIVE BLOCK 5 (CAPTIVE WINCH 9T & Tensioner Harken CT1) and POWER PACKS, unlabeled, 12, 13, 14, 21, CAPTIVE WINCH ST, unclear from crop, LIFTING KEEL / LOCKING PIN, PVG 32 slice, 15 (PVFC), unconfirmed, OUTHAUL, JIB IN/OUT, BACKSTAY DEFLECTOR / SPARE, INNERSTAY FURLER, SPARE, WINDLASS / CAPSTAN (with inlet block), none, JIB CUNINGHAM, # | NAME | QTY | MODEL | # | QTY, 1 | FWD BLOCK "A" | 1 | DANFOSS PVG 32 - 6 FUNCTIONS | 13 | POWERPACKS NON RETURN VALVE | 2 | REXROTH CA25, 2 | FWD BLOCK "B" | 1 | DANFOSS PVG 32/16 - 3 FUNCTIONS | 14 | POWERPACKS LS VALVE | 2 | REXROTH VEI-16-08A-NC, 3 | FWD SAILING MANIFOLD | 1 | ALLUMINUM MODULAR MANIFOLD - 2 FUNCTIONS | 15 | LS COMPENSATING VALVE | 5 | DANFOSS PVFC, 4 | MAST BLOCK | 1 | DANFOSS PVG 32 - 6 FUNCTIONS | 16 | SHUTTLE VALVE | 8 | FLUID-PRESS FPT1/4, 5 | CAPTIVE BLOCK | 1 | DANFOSS PVG 32 - 2 FUNCTIONS | 17 | DUAL COUNTERBALANCE VALVE | 1 | REXROTH A-VBSO-DE30-CSL-PI-38-35, 6 | FWD MAST SAILING MANIFOLD | 1 | ALLUMINUM MODULAR MANIFOLD - 2 FUNCTIONS | 18 | DUAL COUNTERBALANCE VALVE | 9 | REXROTH A-VBSO-DE-78-14-35, 7 | AFT MAST SAILING MANIFOLD | 1 | ALLUMINUM MODULAR MANIFOLD - 4 FUNCTIONS | 19 | FLOW CONTROL VALVE | 1 | TOGNELLA 251/5/S-01-14, 8 | AFT BLOCK "A" | 1 | DANFOSS PVG 32 - 4 FUNCTIONS | 20 | FLOW DIVIDER-COMBINER VALVE | 2 | REXROTH A-DRF16-1238-16-C, 9 | AFT BLOCK "B" | 1 | DANFOSS PVG 32/16 - 3 FUNCTIONS | 21 | FLOW METER | 1 | HYDROTECHNIK 31JH-71-35.030, 10 | AFT BLOCK "C" | 1 | DANFOSS PVG 32 - 5 FUNCTIONS | 22 | PRESSURE SENSOR | 5 | WIKA 12719341
- node routing (same backbone for every provider):
    - Southern Wind Shipyard → create_flagged [—] via -
    - STERN THRUSTER → attach [461-stern-thruster-oms-h250] via control_map
    - THRUSTER UP/DOWN → attach [840-cariboni-hydraulic-cylinders] via control_map
    - THRUSTER LOCK → attach [460-bow-thruster-oms-h300] via control_map
    - BACKSTAY → attach [840-cariboni-hydraulic-cylinders] via control_map
    - TRANSOM DOOR CYLINDER → attach [260-transom-door] via control_map
    - DECK DOOR CYLINDER → attach [260-deck-door] via control_map
    - MAINSHEET TRAVELLER CYLINDER → attach [840-cariboni-hydraulic-cylinders] via control_map
    - SECONDARY WINCH PORT → attach [220-secondary-winch-port] via control_map
    - PRIMARY WINCH PORT → attach [220-primary-winch-port] via control_map
    - TENDER CAR CONTROLLER → attach [270-tender-car-antal-ld1500] via control_map
    - TENDER HAULING WINCH → attach [270-tender-winch-warn-hy2000] via control_map
    - SECONDARY WINCH STB → attach [220-secondary-winch-stbd] via control_map
    - PRIMARY WINCH STBD → attach [220-primary-winch-stbd] via control_map
    - ENGINE ROOM HYDRAULIC POWER PACK → create_flagged [—] via -
    - CAPTIVE WINCH ST → attach [220-captive-mainsheet-9t] via control_map
    - LIFTING KEEL → attach [130-apm-lifting-keel] via control_map
    - LOCKING PIN → create_flagged [—] via no_match
    - MAST WINCH PORT AFT → attach [220-mast-winch-aft-port] via control_map
    - MAST WINCH PORT FWD → attach [220-mast-winch-fwd-port] via control_map
    - MAST WINCH STBD AFT → attach [220-mast-winch-aft-port] via control_map
    - MAST WINCH STBD FWD → create_flagged [—] via no_match
    - OUTHAUL → attach [840-cariboni-hydraulic-cylinders] via control_map
    - JIB IN/OUT → attach [840-cariboni-hydraulic-cylinders] via control_map
    - JIB UP/DOWN → attach [840-cariboni-hydraulic-cylinders] via control_map
    - VANG → attach [840-cariboni-hydraulic-cylinders] via control_map
    - WINDLASS → attach [250-windlass-lewmar-v8] via control_map
    - CAPSTAN → attach [220-capstan-winch] via control_map
    - INNERSTAY FURLER → attach [860-bamar-pi20] via control_map
    - STAYSAIL FURLER → attach [860-bamar-sit20] via control_map
    - JIB FURLER → attach [860-bamar-gfsi30] via control_map
    - CODE 0 FURLER → attach [860-bamar-pi20] via control_map
    - SPARE → create_flagged [—] via no_match
    - BACKSTAY DEFLECTOR → attach [840-cariboni-hydraulic-cylinders] via control_map
    - MAIN CUNNINGHAM → attach [840-cariboni-hydraulic-cylinders] via control_map
    - FORESTAY RTA → attach [860-bamar-gfsi30] via control_map
    - JIB CUNINGHAM → create_flagged [—] via no_match
    - BOW THRUSTER → attach [460-bow-thruster-oms-h300] via control_map
    - THRUSTER UP/DOWN → attach [840-cariboni-hydraulic-cylinders] via control_map
    - THRUSTER LOCK → attach [460-bow-thruster-oms-h300] via control_map
### openai — 119 elements
- agreed with all: 36 · unique to openai: 83
- unique reads (VERIFY THESE — disagreement or fabrication): THRUSTER LOCK — identifier 9 (identifier appears to denote the enclosing AFT BLOCK “B”, not a separately printed function number), TRANSOM CYLINDER, TENDER CAR CONTROL — identifier not visible in this crop, 16 — FLUID-PRESS FPT1/4 (per sheet part list), 15 — DANFOSS PVFC (per sheet part list), DOCK TENDER CYLINDER, DECK DOOR CYLINDER (no separate function identifier legible in this crop), 20 — REXROTH A-DRF16-1238-16-C, 18 — REXROTH A-VBSO-DE-78-14-35, MAIN SHEET TRAVELLER CYLINDER — function identifier not legible in this crop, 18 (BOM: Rexroth A-VBSO-DE-78-14-35), Ambiguous crop: six function labels are visible — MAIN SHEET TRAVELLER CYLINDER; SECONDARY WINCH PORT; PRIMARY WINCH PORT; TENDER HAULING WINCH; SECONDARY WINCH STB; PRIMARY WINCH STBD. No single target function is uniquely identified., Ambiguous crop: two printed function labels are visible, “PRIMARY WINCH PORT” (upper section, block identifier 10 nearby) and “PRIMARY WINCH STBD” (lower section, block identifier 8 nearby); no single target identifier is clearly isolated., CAPTIVE WINCH 2T, CAPTIVE WINCH 9T — Captive Block item 5, left-hand function section, Standalone captive-winch auxiliary/compensating valve assembly, CAPTIVE WINCH 2T (identifier as printed; the nearby vertical cylinder/graphic is marked “6T”, significance unclear), OUTHALL, MAST WINCH PORT AFT (no separate function identifier clearly legible in this crop), JIB UP/OUT, MAST WINCH PORT FWD (no separate identifier legible in crop), MAST WINCH STBD AFT (center vertical function; no separate function number legible), MAST WINCH STBD AFT (left-hand vertical section in MAST BLOCK, item 4); adjacent MAST WINCH STBD FWD section is also visible, so the intended single section is not explicitly marked, INTERSTAY RTA (identifier as printed; no separate function number legible), STAYSAIL FURLER (printed label); no separate function identifier legible in this crop, 16 (BOM: FLUID-PRESS FPT1/4), THRUSTER UP/DOWN (no separate identifier legible in the crop), JIB CUNNINGHAM, THRUSTER LOCK (printed label); nearby printed identifier “2” appears to identify the enclosing block/manifold, but its exact association with this function is not fully explicit in the crop, BACKSTAY — no separate function identifier is legible in this crop, 22 (BOM: WIKA 12719341), THRUSTER UP/DOWN — identifier 9 (AFT BLOCK “B”, inferred only from the clearly printed manifold callout 9 at the right edge of the shown block; no separate function number is legible), THRUSTER LOCK — identifier 9 is printed at the AFT BLOCK “B” assembly boundary; no separate function number is legible, DECK DOOR CYLINDER (identifier not legible in crop), TENDER WINCH, TENDER HAULING WINCH (identifier not visible in crop), 18 — REXROTH A-VBSO-DE-78-14-35 (per sheet part list), Ambiguous crop: two centered function slices are visible — “SECONDARY WINCH PORT” (upper block) and “SECONDARY WINCH STB” (lower block); no printed function identifier is legible., PRIMARY WINCH PORT — adjacent assembly/item callout 10; no separate function identifier is clearly readable, ENGINE ROOM POWER PACKS / pumps and auxiliary valves
- node routing (same backbone for every provider):
    - BACKSTAY → attach [840-cariboni-hydraulic-cylinders] via control_map
    - TRANSOM CYLINDER → create_flagged [—] via no_match
    - DOCK TENDER CYLINDER → create_flagged [—] via no_match
    - MAINSHEET TRAVELLER CYLINDER → attach [840-cariboni-hydraulic-cylinders] via control_map
    - SECONDARY WINCH PORT → attach [220-secondary-winch-port] via control_map
    - PRIMARY WINCH PORT → attach [220-primary-winch-port] via control_map
    - CAPTIVE WINCH 2T → attach [220-captive-mainsheet-9t] via control_map
    - Standalone captive-winch auxiliary/compensating valve assembly → create_flagged [—] via -
    - OUTHALL → create_flagged [—] via no_match
    - JIB UP/OUT → attach [840-cariboni-hydraulic-cylinders] via control_map
    - JIB UP/DOWN → attach [840-cariboni-hydraulic-cylinders] via control_map
    - VANG → attach [840-cariboni-hydraulic-cylinders] via control_map
    - BACKSTAY DEFLECTOR → attach [840-cariboni-hydraulic-cylinders] via control_map
    - MAIN CUNNINGHAM → attach [840-cariboni-hydraulic-cylinders] via control_map
    - FORESTAY RTA → attach [860-bamar-gfsi30] via control_map
    - JIB CUNNINGHAM → attach [840-cariboni-hydraulic-cylinders] via control_map
    - STERN THRUSTER → attach [461-stern-thruster-oms-h250] via control_map
    - THRUSTER UP/DOWN → attach [840-cariboni-hydraulic-cylinders] via control_map
    - THRUSTER LOCK → attach [460-bow-thruster-oms-h300] via control_map
    - TENDER CAR CONTROLLER → attach [270-tender-car-antal-ld1500] via control_map
    - TENDER WINCH → attach [270-tender-winch-warn-hy2000] via control_map
    - SECONDARY WINCH STB → attach [220-secondary-winch-stbd] via control_map
    - PRIMARY WINCH STBD → attach [220-primary-winch-stbd] via control_map
    - ENGINE ROOM POWER PACKS / pumps and auxiliary valves → create_flagged [—] via -
    - LIFTING KEEL → attach [130-apm-lifting-keel] via control_map
    - LOCKING PIN → create_flagged [—] via no_match
    - MAST WINCH PORT AFT → attach [220-mast-winch-aft-port] via control_map
    - MAST WINCH PORT FWD → attach [220-mast-winch-fwd-port] via control_map
    - MAST WINCH STBD AFT → attach [220-mast-winch-aft-port] via control_map
    - MAST WINCH STBD FWD → create_flagged [—] via no_match
    - WINDLASS → attach [250-windlass-lewmar-v8] via control_map
    - CAPSTAN → attach [220-capstan-winch] via control_map
    - INNERSTAY RTA → attach [860-bamar-sit20] via control_map
    - STAYSAIL FURLER → attach [860-bamar-sit20] via control_map
    - JIB FURLER → attach [860-bamar-gfsi30] via control_map
    - CODE 0 FURLER → attach [860-bamar-pi20] via control_map
    - BOW THRUSTER → attach [460-bow-thruster-oms-h300] via control_map
    - THRUSTER UP/DOWN → attach [840-cariboni-hydraulic-cylinders] via control_map
    - THRUSTER LOCK → attach [460-bow-thruster-oms-h300] via control_map
    - Block inlet/end and LS-compensating/shuttle sections distributed among manifolds → create_flagged [—] via -


## 2-electrical-distribution-schedule — GM-111_24V-DC-distribution

### anthropic — 196 elements
- agreed with all: 55 · unique to anthropic: 141
- unique reads (VERIFY THESE — disagreement or fabrication): Q45 10A - RADAR SYSTEM, Q46 10A - EXT. SCREENS, Q47 10A - B&G, Q48 10A - NAVIGATION PC, Q49 10A - AUTO PILOT, CT8, Q50 10A - NETWOR<illegible>, Q51 10A - AUX VH<illegible>, Q52 10A - CCTV, Q53 10A - /, Q54 10A - /, Re/, Q1 10A - AFT GREY WATER PUMP, Q2 20A, Q23 25A - ONYX (<illegible>, Q24 6A, Q1 10A, Q3 20A, Q4 10A, Q5 10A, Q6 20A, Q7 20A, Q8 20A, Q9 20A, Q10 20A, Q11 32A, Q12 32A, Q13 6A, Q14 10A, Q15 20A, Q16 10A, Q17 6A, Q18 6A, Q19 10A, Q20 10A, Q21 20A, Q22 6A, Q23 20A, Q25 10A, Q26 32A
### gemini — 92 elements
- agreed with all: 55 · unique to gemini: 37
- unique reads (VERIFY THESE — disagreement or fabrication): Tel. (027) 021-671 8001 | Cell 083 298 3305 | goetz@telkomsa.net, PROJECT | SWS 108'-01 " Gelliceaux ", CUSTOMER | SOUTHERN WIND SHIPYARD (PTY) LTD, YRIGHT OF THIS DRAWING IS EXPRESSLY RESERVED AND NO PART OF IT MAY BE COPIED WITHOUT PRIOR PERMISSION., AFT PANEL DC BREAKERS (Left Column), AFT PANEL DC BREAKERS (Right Column), FWD PANEL DC BREAKERS, EMERGENCY POWER SUPPLY, EMERGENCY PANEL, Input/Battery Supply Lines and General Fuses/Switches, NETWORK, AUX VHF, ONYX (AUTO FUEL TRANSFER PUMP), PASSARELLE LIGHT, WATER MAKER, AFT COMPANION WAY, SALOON COMPANION WAY, OIL TRANSFER PUMP, AFT DC SOCKET, AUTOPILOT PUMP, GALVANIC CONTROL, TENDER REFUELING PUMP, NAVIGATION LTS, COURTESY LTS, ENG. ROOM / LAZ. / TRANSOM LTS, YACHTICA SYSTEM, GALLEY LIGHTS, PORT/STBD CREW LTS, STBD CREW LIGHTS, PORT AFT GUEST LIGHTS, STBD AFT GUEST LIGHTS, FWD EMERGENCY LTS/HATCH SUPPLY, //, ENG.ROOM GAS RELEASE ALARM, GAS/CO2/PETROL VAPOUR ALARM, SERVICE BAT. VENTILATION, GMDSS /
### openai — 129 elements
- agreed with all: 55 · unique to openai: 74
- unique reads (VERIFY THESE — disagreement or fabrication): - CTB 7 = QI–POWER–485–300–LV, - CTB 8 = QI–POWER–485–LV, - CTB 9 = QI–POWER–485–LV, - CTB 10 = QI–POWER–485–LV, 24 V service supply, fuse/switch branches, CT8 feed, and pump/winch branches, AFT PANEL DC BREAKERS, including upper auxiliary rows and two main breaker columns, FWD PANEL DC BREAKERS and emergency breaker extension, EMERGENCY POWER SUPPLY breaker bank, EMERGENCY PANEL breaker bank, Emergency battery and emergency distribution interconnections to AFT/FWD panels, CTB communications definitions / notes block, Title block, SUPPLY bus, <UNKNOWN>, Fuse F5, F5, Switch SW6, SW6, Unlabelled continuation, <UNKNOWN-F5-DEST>, Fuse F6, F6, Switch SW7, SW7, Unlabelled right vertical bus, <UNKNOWN-RIGHT-BUS>, Fuse F7, F7, Switch SW8, SW8, Coil-operated contact SO 6, SO 6, BILGE PUMP, <UNKNOWN-BILGE-PUMP>, Fuse F8, F8, Switch SW9, SW9, Coil-operated contact SO 7, SO 7


## 2-electrical-distribution-schedule — GM-111a_emergency-supply

### anthropic — 226 elements
- agreed with all: 18 · unique to anthropic: 208
- unique reads (VERIFY THESE — disagreement or fabrication): CB8 20A EMERGENCY LTS, PRIMARY/EMERGENCY POWER IND. - 1, PRIMARY/EMERGENCY POWER IND. - 2, PRIMARY/EMERGENCY POWER IND. - 3, PRIMARY/EMERGENCY POWER IND. - 4, PRIMARY/EMERGENCY POWER IND. - 5, RED 1 - 1, GREEN 1 - 2, STERN 1 - 3, RED 2 - 4, GREEN 2 - 5, STERN 2 - 6, STEAM 1 - 7, STEAM 2 - 8, MUTE - 9, - 10, - 11, - 12, CB8 20A, EMERGENCY LTS, PRIMARY/EMERGENCY POWER IND., 1, 2, 3, 4, 5, RED 1, GREEN 1, STERN 1, RED 2, GREEN 2, STERN 2, STEAM 1, STEAM 2, MUTE, 10, 11, 12, DRAWN | GM, CUSTOMER | SOUTHERN WIND SHIPYARD (PTY) LTD
### gemini — 136 elements
- agreed with all: 18 · unique to gemini: 118
- unique reads (VERIFY THESE — disagreement or fabrication): DWG No. | GMMS 108'-111a | G.M. MARINE SERVICES, TITLE | EMERGENCY SUPPLY RADIO/NAV./LTS | Tel. (027) 021-671 8001 Cell 083 298 3305 goetz@telkomsa.net, DATE | 4/ 10/2023 | PROJECT | SWS 108'-01 " Gelliceaux ", DRAWN | GM | CUSTOMER | SOUTHERN WIND SHIPYARD (PTY) LTD, Power Sources (Batteries, Chargers, DC/DC), Breakers Q36-Q38, Breakers QE1-QE8, MASTERVOLT GMDSS PANEL, T/S E (1-4), T/S E (9-13), Relay Re1, T/S E (19-41, Nav Lights), Relays Re2-Re6, Terminals 42-58 (Emergency Lts), Title Block, NEGATIVE BUS, NEGATIVE_BUS, GMDSS BATTERY, GMDSS_BATTERY, SHUNT #2, SHUNT_2, F11, SW13, MASTERVOLT MASS CHARGER, MASTERVOLT_MASS_CHARGER, SHIPS 230V GEN INVERTER, SHIPS_230V_GEN_INVERTER, F10, to reset GMDSS, EMERGENCY BATTERY, EMERGENCY_BATTERY, SHUNT #3, SHUNT_3, F13, SW12, F12, 24V 50A, CHARGER_24V_50A, CT, NA
### openai — 251 elements
- agreed with all: 18 · unique to openai: 233
- unique reads (VERIFY THESE — disagreement or fabrication): DWG No. | GMMS 108’–111a, G.M. MARINE SERVICES, TITLE | EMERGENCY SUPPLY RADIO/NAV./LTS, Tel. (027) 021–671 8001 | Cell 083 298 3305 | goetz@telkomsa.net, DATE | 4/ 10/2023 | PROJECT | SWS 108’–01 ” Gelliceaux ”, DRAWN | GM | CUSTOMER | SOUTHERN WIND SHIPYARD (PTY) LTD, AFT DC panel service-bus lighting feeds and upper interconnect wiring, GMDSS battery, charger, emergency battery/charger, shunts, switches and source connections, Emergency/GMDSS distribution breaker banks (CB1-CB8 and QE bank), Mastervolt GMDSS panel / alarm interface enclosure, Emergency panel indication and lamp/mute circuits, Upper terminal-strip and relay interface around Re1, LOPO LED navigation and steaming-light outgoing circuits, Lower control relay bank Re2-Re6 with associated terminal strips, Lower numbered terminal groups and emergency/light control interfaces, Engine-room, tech-room, courtesy and emergency mast lighting endpoints, Title block, +24V SERVICE BUS, F6, SW7, AFT DC PANEL, NAVIGATION LTS, Q36, COURTESY LTS, Q37, ENG. ROOM LTS, Q38, T/S B terminal 6, fused terminal, T/S B-6, LAZ. / TRANSOM LTS, NEGATIVE BUS, NEG_BUS, GMDSS BATTERY, GMDSS_BAT, SHUNT #2, SHUNT_2, GMDSS battery positive fuse, F11, GMDSS battery switch, SW13


## 3-electrical-one-line — GM-102_230V-distribution

### anthropic — 73 elements
- agreed with all: 27 · unique to anthropic: 46
- unique reads (VERIFY THESE — disagreement or fabrication): CTA 13 = QI-POWER-485, TITLE | 230V AC POWER DISTRIBUTION | Tel. (027) 021-671 8001   Cell 083 298 3305   goetz@telkomsa.net, DATE | 4/10/2023 | PROJECT | SWS 108'-01 " Gelliceaux ", DRAWN | GM | CUSTOMER | SOUTHERN WIND SHIPYARD (PTY) LTD, THE COPYRIGHT OF THIS DRAWING IS EXPRESSLY RESERVED AND NO PART OF IT MAY BE COPIED WITHOUT PRIOR PERMISSION., AC DB PANEL - Main breaker column #1-#9 SERVICES/AIRCON/CHARGERS/GALLEY with earth leakage breakers, CTs and AUX supply, Q1-Q6 branch breakers feeding NAV STATION/ELECTRONICS loads (mast base), Earth Leakage 5-12 group feeding battery chargers, seawater cooling, CPP oil circuits, Q7-Q21 breaker bank feeding cabin/aircon/water heater/water maker loads, Q22-Q38 breaker bank feeding pumps, refrigeration, wine cooler, air compressor, engine room, ventilation, wifi, starlink, Re1/T1 relay & timer module near XA40 tap block, feeding pump control interlock, Terminal block 21-24 tap to XA40 monitoring, Terminal block 25-32 for fan power, no-power indication, passage panel MU-XX cable, Re1/Re2 relay pair driving ESS ventilation/tendergarage fan control near bottom right, INVERTER 205KW unit (24VDC to 230VAC) feeding earth leakage 13 / Q34-Q38 loads, Pump control connector blocks (RM35JA32MW, 3UG4621-1AW30) with I>< symbols feeding pump motors, CTA 1-13 = QI-POWER-485 text tag legend, bottom left, Title block bottom right, #1 SERVICES, #2 SERVICES, NAV. STATION ENTERTAINMENT, ELECTRONICS (MAST BASE), to AFT DB PANEL, WATER M... (ENG.RO...), FWD WATER H... (OWNERS C...), AFT WATER HE... (PORT GUEST ...), ENG.ROOM E..., FRESH WATER PUMP 1, FRESH WATER PUMP 2, REFRIGERATION SUPPLY, SALT WATER PUMP, WINE COOLER, AIR COMPRESSOR, SALOON UV STERILISER, LAZ / TECH-ROOM /, ENGINE ROOM, DECK FRIDGE, PUMP CONTROLLER (cropped, PUMP CON), PUMP CON..., PRESSURE (SW) - pressostat, automatic pressure-controlled switch feeding pump control circuit via terminals 18/19
### gemini — 124 elements
- agreed with all: 27 · unique to gemini: 97
- unique reads (VERIFY THESE — disagreement or fabrication): Main Bus and Primary Feeds, Breakers Q1-Q6, Earth Leakages 5-12, Q20-Q21, Breakers Q7-Q19, Breakers Q22-Q38, Pump Control Logic, Fan Control Logic, CT Signal Mapping List, Inverter Connection Block, 230V AC BUS, bus_230v_ac, SERVICES, #1, CT1, #2, CT2, #3, CT3, #4, CT4, #5, CT5, #6, CT6, #7, CT7, #8, CT8, #9, CT9, brk_aux_power, NAV. STATION ENTERTAINMENT, out, ELECTRONICS (MAST BASE), STBD SEAWATER COOLING, CPP SEAWATER COOLING, CPP OIL, WATER MAKER 1 (ENG.ROOM), FWD WATER HEATER (OWNERS CAB.), AFT WATER HEATER (PORT GUEST CAB.), ENG.ROOM BLOWER
### openai — 155 elements
- agreed with all: 27 · unique to openai: 128
- unique reads (VERIFY THESE — disagreement or fabrication): - CTA 1 = QI-POWER-485, - CTA 2 = QI-POWER-485, - CTA 3 = QI-POWER-485, - CTA 4 = QI-POWER-485, - CTA 5 = QI-POWER-485, - CTA 6 = QI-POWER-485, - CTA 7 = QI-POWER-485, - CTA 8 = QI-POWER-485, - CTA 9 = QI-POWER-485, - CTA 10 = QI-POWER-485, - CTA 11 = QI-POWER-485, - CTA 12 = QI-POWER-485, - CTA 13 = QI-POWER-485, DWG No. | GMMS 108’–102, TITLE | 230V AC POWER DISTRIBUTION, Tel. (027) 021-671 8001 | Cell 083 298 3305 | goetz@telkomsa.net, DATE | 4/ 10/2023 | PROJECT | SWS 108’–01 ” Gelliceaux ”, DRAWN | GM | CUSTOMER | SOUTHERN WIND SHIPYARD (PTY) LTD, THE COPYRIGHT OF THIS DRAWING IS EXPRESSLY RESERVED AND NO PART OF IT MAY BE COPIED WITHOUT PRIOR PERMISSION., Incoming 230 V AC bus, main service feeders #1–#9, auxiliary supply, CT bank, and earth-leakage protection, Left-center outgoing branch bank including entertainment/electronics, battery chargers, seawater cooling, and CPP auxiliaries, Center outgoing branch bank including accommodation loads, water heating, blowers/extractors, and air-conditioning, Right outgoing branch bank including pumps, refrigeration, ventilation, communications, and spare ways, Fresh-water and salt-water pump control/pressure-switch circuits with relay/overcurrent modules and terminals, Primary ventilation fan control, relay logic, terminal group, and passage-panel indication interface, 24 V DC to 230 V AC inverter auxiliary supply feeding an earth-leakage-protected AC branch, CTA 1–CTA 13 current-transformer text-tag legend, Title block and project/customer information, #1 SERVICES, #2 SERVICES, STBD SEAWATER COOLING, CPP SEAWATER COOLING, CPP OIL, CPP OIL BOOST, WATER MAKER 1 (ENG.ROOM), FWD WATER HEATER (OWNERS CAB.), AFT WATER HEATER (PORT GUEST CAB.), ENG.ROOM BLOWER, ENG.ROOM EXTRACTOR, AIRCON 1


## 3-electrical-one-line — GM-110a_24V-service-supply

### anthropic — 192 elements
- agreed with all: 15 · unique to anthropic: 177
- unique reads (VERIFY THESE — disagreement or fabrication): CTB 1 = QI-POWER-485-300-LV, CTB 2 = QI-POWER-485-300-LV, CTB 3 = QI-POWER-485-300-LV, CTB 4 = QI-POWER-485-300-LV, CTB 5 = QI-POWER-485-300-LV, CTB 6 = QI-POWER-485-300-LV, CTB 7 = QI-POWER-485-300-LV ( EMERGENCY BAT. ), HVPDU, MAPS, TITLE | 24V DC SERVICE SUPPLY | Tel. (027) 021-671 8001   Cell 083 298 3305   goetz@telkomsa.net, DATE | 4/ 10/2023 | PROJECT | SWS 108'-01 " Gelliceaux ", DRAWN | GM | CUSTOMER | SOUTHERN WIND SHIPYARD (PTY) LTD, THE COPYRIGHT OF THIS DRAWING IS EXPRESSLY RESERVED AND NO PART OF IT MAY BE COPIED WITHOUT PRIOR PERMISSION., PORT HVPDU Q1-Q4 32A breakers + F1/F2 500A fuses, STBD HVPDU Q1-Q4 32A breakers, PORT MAPS-1/2 2x5KW converters, STBD MAPS-1/2 2x5KW converters, CT1-CT4 current transformers feeding ONYX monitoring, ISOLATORS SW1-SW5 with SO1-SO5 contactor/solenoid group, 24V 110A AC/DC power supply (230VAC L/N in, 24VDC out, F18 125A), T/S S terminal strip 1-7 with contact group and Re1/Re2 relays, T/S S terminal strip 5-12 second group with Re1/Re2, T/S E terminal + QE7 6A emergency breaker, +24V Service Bus with F5-F9 fuses feeding FWD/AFT DC panel, bilge pump, fire pump, SW6-10/SO6-9, AUX SERVICE BAT 200Ah 24V with SW11 and F16 250A, PC CARD enclosure with numbered I/O 1-10, BEL-1/4 230V AC control, Negative bus / 230V AC ground bar with drop tags to panels, pump, batteries, CTB tag legend + HVPDU/MAPS notes, SHUNT #1 500A/50mV, PORT MAPS-1/2 2x5KW 600V DC / 24V DC, MAPS-1/2, F (partially visible, right edge), F<UNKNOWN>, Junction dot on 600V DC line (left), unknown, Junction dot on second horizontal line (left, below 600V DC line), STBD MAPS-1/2 2x5KW (600V DC / 24V DC) - MODULAR AUXILARY POWER SYSTEM 600V DC/24V DC, protected for over-current, electronically fused, 600V DC (second module, partially visible below), MAPS-1/2 (lower unit), F (partially visible fuse/breaker box at right edge, upper)
### gemini — 109 elements
- agreed with all: 15 · unique to gemini: 94
- unique reads (VERIFY THESE — disagreement or fabrication): _ CTB 1 = QI-POWER-485-300-LV, _ CTB 2 = QI-POWER-485-300-LV, _ CTB 3 = QI-POWER-485-300-LV, _ CTB 4 = QI-POWER-485-300-LV, _ CTB 5 = QI-POWER-485-300-LV, _ CTB 6 = QI-POWER-485-300-LV, _ CTB 7 = QI-POWER-485-300-LV ( EMERGENCY BAT. ), HVPDU: | HIGH VOLTAGE DC LINK, MAPS: | MODULAR AUXILARY POWER SYSTEM 600V DC/24V DC, THESE CONVERTERS ARE PROTECTED FOR OVER-CURRENT, AND ELECTRONICALLY FUSED., PORT HVPDU Bus, STBD HVPDU Bus, MAPS Power Converters, ISOLATORS (SW1-SW5), +24V SERVICE BUS Distribution, PC CARD, NEGATIVE BUS, T/S S (Pins 1-7), T/S S (Pins 8-12), T/S S (Pins 1-3), Relays Re1/Re2 & Control Switches, Sheet Legends, PORT HVPDU, port_hvpdu, 600V DC BUS, bus_600v_dc, Switch, switch_in, F1, F2, Q1, Q2, Q3, Q4, PORT MAPS-1/2 2x5KW, maps_port_1, maps_port_2, STBD MAPS-1/2 2x5KW, maps_stbd_1
### openai — 240 elements
- agreed with all: 15 · unique to openai: 225
- unique reads (VERIFY THESE — disagreement or fabrication): - CTB 1  = QI-POWER-485-300-LV, - CTB 2  = QI-POWER-485-300-LV, - CTB 3  = QI-POWER-485-300-LV, - CTB 4  = QI-POWER-485-300-LV, - CTB 5  = QI-POWER-485-300-LV, - CTB 6  = QI-POWER-485-300-LV, - CTB 7  = QI-POWER-485-300-LV ( EMERGENCY BAT., HVPDU:    HIGH VOLTAGE DC LINK, MAPS:     MODULAR AUXILARY POWER SYSTEM  600V DC/24V DC
          THESE CONVERTERS ARE PROTECTED FOR OVER-CURRENT
          AND ELECTRONICALLY FUSED., CTB definitions and HVPDU/MAPS notes, Port and starboard HVPDU 600 VDC bus breaker banks, MAPS converter and fused/CT-monitored 24 VDC feeds, Isolators, solenoids, transfer/selector contacts, relays, and associated terminal strips, +24 V service bus, shunt, auxiliary service battery, outgoing fused branches, and loads, PC card and BAE/AUX selector interface, Control terminal strips associated with isolator/relay wiring, Negative bus and return distribution, 230 VAC to 24 VDC auxiliary converter branch, MAPS-1, <UNKNOWN> — PORT 600V DC input, PORT_600V_SOURCE, PORT MAPS-1/2, PORT MAPS-1, PORT MAPS-2, F1, F2, <UNKNOWN> — STBD 600V DC input, STBD_600V_SOURCE, STBD MAPS-1/2, STBD MAPS-1, STBD MAPS-2, F3, F4, CT4, <UNKNOWN> — 24V DC destination beyond CT1, 24V_DEST_CT1, <UNKNOWN> — 24V DC destination beyond CT2, 24V_DEST_CT2, <UNKNOWN> — 24V DC destination beyond CT3, 24V_DEST_CT3


## 4-electrical-relay-terminal-wiring — GM-114a_bilge-system

### anthropic — 186 elements
- agreed with all: 50 · unique to anthropic: 136
- unique reads (VERIFY THESE — disagreement or fabrication): PLUG D, LAZARETTE BILGE, AFT BILGE, ENG. ROOM BILGE, FWD BILGE, SAIL LOCKER, BILGE PUMP SW, AUX PLUG ON PC BOARD, 7 - open, 8 - closed : FWD BILGE, 9 - open, 10 - closed : SAIL LOCKER, PROJECT | SW<illegible>, CUSTOMER | SC<illegible>, <illegible>SERVED AND NO PART OF <illegible>, 1, 2, 3, 4, <illegible>, T/S S (local pump switch terminal), T/S C (main terminal strip - valve/switch wiring 1-50), Re1-Re6 relay column with T/S B terminals 8-13, BILGE VALVE / OPEN-CLOSE contact groups (6 valve controllers), Bilge level switches (PORT/STBD LAZARETTE, AFT, ENG ROOM, FWD, SAIL LOCKER BILGE SW), MAIN PANEL PLUG C, MAIN PANEL indicator switches S20-S24, S13, PEDESTAL ALARM+MUTE / ALARM MOD, MAIN PANEL PC CARD (enclosure with open/closed indicator lights, diode array, +24V), Main bilge pump motor + F3 60A fuse, SW8, SO 6, Title block / drawing info, Relay coil (terminals 13,14,15), <UNKNOWN>, Relay coil terminal 13, Relay coil terminal 14, Relay coil terminal 15, Relay contact 1, Relay contact 2, Circled X lamp symbol (indicator light), Switch contact leading to LO
### gemini — 186 elements
- agreed with all: 50 · unique to gemini: 136
- unique reads (VERIFY THESE — disagreement or fabrication): Relays Re1-Re6, Terminal Strip T/S C, MAIN PANEL PC CARD / PLUG C & PLUG D, Bilge Valve Motors, T/S B, Re1, T/S C, MAIN PANEL, ann_main_panel, PLUG C, ann_plug_c, 1 << [1], PLUG_C_1, 2 << [2], PLUG_C_2, 3 << [3], PLUG_C_3, 4 << [4], PLUG_C_4, 5 << [5], PLUG_C_5, 6 << [6], PLUG_C_6, 7 << [7], PLUG_C_7, << [8], PLUG_C_8, << [9], PLUG_C_9, << [10], PLUG_C_10, << [11], PLUG_C_11, << [12], PLUG_C_12, LAZARETTE BILGE, S20, AFT BILGE, S21, ENG. ROOM BILGE
### openai — 241 elements
- agreed with all: 50 · unique to openai: 191
- unique reads (VERIFY THESE — disagreement or fabrication): Main bilge pump fused feed and local pump-switch control, Left-side +24 V service-battery protection and bilge-valve branch protection, Repeated bilge-valve control relays Re1–Re6, Central numbered terminal strip T/S C, Five repeated field groups: open/close contacts, bilge-valve actuators, and bilge switches, Main-panel Plug C, manual bilge switches, pump switch, and pedestal alarm/mute interface, Plug D and dotted Main Panel PC Card status-indicator interface, <UNKNOWN> incoming supply, <UNKNOWN>, Fuse, F3, SW8, Solenoid-operated contact, SO 6, MAIN BILGE PUMP, M, BILGE VALVES, Terminal strip B, T/S B, Fused terminal 8 (built-in inline protection symbol), T/S B:8, Relay Re1, Re1, XA40 pin 14 wired tag, XA40:14, XA40 pin 12 wired tag, XA40:12, Fused terminal 9 (built-in inline protection symbol), T/S B:9, Relay Re2, XA40 pin 16 wired tag, XA40:16, Fused terminal 10 (built-in inline protection symbol), T/S B:10, Relay Re3, XA10 pin 06 wired tag, XA10:06, Fused terminal 11 (built-in inline protection symbol), T/S B:11, Relay Re4


## 4-electrical-relay-terminal-wiring — GM-112_main-panel-A

### anthropic — 229 elements
- agreed with all: 22 · unique to anthropic: 207
- unique reads (VERIFY THESE — disagreement or fabrication): TITLE | MAIN PANEL SCHEMATIC "A", DATE | 4/ 10/2023 | PROJECT | SWS 108'-01 " Gelliceaux ", DRAWN | GM | CUSTOMER | SOUTHERN WIND SHIPYARD (PTY) LTD, THE COPYRIGHT OF THIS DRAWING IS EXPRESSLY RESERVED AND NO PART OF IT MAY BE COPIED WITHOUT PRIOR PERMISSION., Tel. (027) 021-671 8001    Cell 083 298 3305    goetz@telkomsa.net, T/S E and T/S F left side terminal strips (top), T/S F left side terminal strips (mid), Plug A / T/S C terminal block (upper, near PLUG A pins 1-4, 38-41), T/S C small terminal block (PORT/STBD XA41/XA61 taps), Plug A large terminal block (97-101,77-81,92-96) with alarm points, T/S E block (19,20) and Plug B block (110-120), PC CARD / Alarm Module dotted enclosure with diode arrays and output taps, Relay/buzzer/mute-test assembly bottom of PC card enclosure, Plug C / T/S C / T/S E lower blocks (Alarm Mod2, Emergency Stop, Emergency Lts), Switch/indicator column S8-S19 and lamp/output labels (ANCHOR LT, NAV LIGHTS, STEAMING LIGHTS, bilge/grey water/blackwater pump run indicators), Emergency Stop / Emergency Lts / Courtesy Lts output row bottom right, Title block, T/S F pin 1 - fused terminal, 36, T/S F pin 2, 61, T/S F pin 3, 65, T/S F pin 4 - fused terminal, 40, T/S F pin 5 - fused terminal, 43, T/S F pin 6 - fused terminal, 46, T/S F pin 7 - fused terminal, 58, T/S F pin 8 - fused terminal, 60, T/S F pin 9 - fused terminal, 64, T/S F pin 10, 54, T/S F pin 11, 55, T/S F pin 12
### gemini — 194 elements
- agreed with all: 22 · unique to gemini: 172
- unique reads (VERIFY THESE — disagreement or fabrication): T/S F MU5-12 / T/S E MU4a-12/1, T/S F MU4-12 / T/S E, T/S C (PLUG A / PLUG C), T/S C (XA41 / XA61 block), T/S C (XA61 block), Alarm / Pump Status Outputs, PLUG B, Mute / Test Control Block, ALARM MOD 2 / PLUG C, T/S C / T/S E / PLUG B (Emergency Stop/Lts), +24V EMERGENCY SUPPLY, 8, 36, 61, 65, 40, 43, 46, 58, 60, 64, 54, 55, 73, 59, 62, 38, 39, 41, 63, 66, 67, 68, STEAMING, 34, not used, 69, T/S F - 7, 7, T/S F - 8
### openai — 385 elements
- agreed with all: 22 · unique to openai: 363
- unique reads (VERIFY THESE — disagreement or fabrication): Upper-left terminal strips and MU4/MU5 multicore cable terminations, Central alarm module / PC card with indicator and diode logic, Mid-left T/S C and plug/terminal interface groups, Lower-left T/S F, T/S E, and associated multicore terminations, Right-side external switch, lamp, pump, bilge, alarm, and run-indication endpoints, Lower-center alarm output relay/contact and mute/test circuit, Bottom plug B/C and emergency/control terminal wiring, Terminal strip F, Terminal 36; built-in fuse, T/S F/36, Terminal 61, T/S F/61, Terminal 65, T/S F/65, Terminal 40; built-in fuse, T/S F/40, Terminal 43; built-in fuse, T/S F/43, Terminal 46; built-in fuse, T/S F/46, Terminal 58; built-in fuse, T/S F/58, Terminal 60; built-in fuse, T/S F/60, Terminal 64; built-in fuse, T/S F/64, Terminal 54, T/S F/54, Terminal 55, T/S F/55, Terminal 73, T/S F/73, 12-core multi-core cable MU5-12, MU5-12, Terminal strip E, Terminal 60, T/S E/60, T/S E/61, Terminal 62, T/S E/62


## 5-pid-plumbed — bilge-and-fire-schematic

### anthropic — 38 elements
- agreed with all: 0 · unique to anthropic: 38
- unique reads (VERIFY THESE — disagreement or fabrication): MAIN BILGE PUMP, DIESEL FIRE PUMP, ELECTRIC FIRE PUMP, AUXILIARY BILGE PUMP, OIL REMOVAL CARTRIDGE FILTER, SEAWATER/BILGE STRAINER, BILGE PICKUP STRUMBOX, HIGH LEVEL BILGE ALARM SWITCH, PRESSURE RELIEF VALVE, NON RETURN VALVE 2½", BALL VALVE 1½", BALL VALVE 2", ANTI-SIPHON MANIFOLD, SIPHONBREAK VALVE, BALL VALVE 3-WAY L PORT 1", BALL VALVE 3-WAY L PORT 2", ELECTRIC ROTARY ACTUATOR, BALL VALVE 2-WAY 316SS 2", FIRE HYDRANT VALVE, FIRE HOSE, FIRE HOSE NOZZLE, GARDENA-TYPE TAP CONNECTOR, WATER MIST SPRAY HEAD, BALL VALVE-MINI 1/2", AUXILIARY BILGE ALARM SWITCH, COOLANT LEAK ALARM, OWNERS HEAD / OWNERS CABIN / SALOON / GALLEY / GUEST CABINS, MAIN CONTROL PANEL, STBD GENSET, MAIN ENGINE RAW WATER PUMP, OVERBOARD VIA EXHAUST WATER SEPARATOR, FWD DECK LOCKER DRAIN, MAST AUX BILGE PUMP SUCTION MANIFOLD, ESS ENCLOSURE, TENDER GARAGE, SEAWATER PICKUP, BILGE OVERBOARD, PRIMING LINE FROM FRESH WATER SUPPLY
### gemini — 61 elements
- agreed with all: 0 · unique to gemini: 61
- unique reads (VERIFY THESE — disagreement or fabrication): 018-01, 015-01, 019-01, 020-01, 002-01, 011-01, 022-01, 011-03, 009-05, 016-01, 017-01, 010-01, 006-01, 007-01, 006-02, 006-03, 007-02, 025-01, 011-04, 006-04, 006-05, 014-02, 003-02, 014-03, 004-01, 021-01, 025-02, 007-03, 025-03, 016-03, 017-03, 016-04, 017-04, 007-04, 025-04, 006-06, 006-07, 021-03, 014-01, 003-01
### openai — 28 elements
- agreed with all: 0 · unique to openai: 28
- unique reads (VERIFY THESE — disagreement or fabrication): 002-01 DIESEL FIRE PUMP, 005-01 SEAWATER STRAINER, 005-01 LAZARETTE PICKUP, 007-01 BILGE ALARM, 006-02 MIDSHIP SUMP PICKUP, 006-03 MIDSHIP SUMP PICKUP, 007-02 BILGE ALARM, 003-02 E-R AUX BILGE PUMP, 004-01 OILY BILGE FILTER, 021-01 FLEX SUCTION HOSE CONNECTION, 006-04 ENGINE ROOM SUMP PICKUP, 006-05 ENGINE ROOM SUMP PICKUP, 007-03 BILGE ALARM, 003-01 MAST AREA BILGE PUMP, MAST AUX BILGE PUMP SUCTION MANIFOLD, 006-06 MAST AREA SUMP PICKUP, 007-04 BILGE ALARM, 006-08 ESS ENCLOSURE PICKUP, 007-06 BILGE ALARM, 005-02 SEAWATER STRAINER, 002-02 ELECTRIC FIRE PUMP, 003-01 MAIN BILGE PUMP, ANTI-SIPHON MANIFOLD 700mm ABOVE DWL, 006-08 SAIL LOCKER SUMP PICKUP, 007-05 BILGE ALARM, FIRE LINE SEAWATER SUPPLY, FIRE HYDRANT aft, FIRE HYDRANT forward


## 5-pid-plumbed — raw-water-schematic-515

### anthropic — 0 elements
- agreed with all: 0 · unique to anthropic: 0
### gemini — 14 elements
- agreed with all: 0 · unique to gemini: 14
- unique reads (VERIFY THESE — disagreement or fabrication): SEAWATER STRAINER, SEACHEST 001-01, SEACHEST, MAIN COOLING SEAWATER PUMP (PORT) (MCSWP-P), MAIN COOLING SEAWATER PUMP (STBD) (MCSWP-S), CPP SEAWATER PUMP (CPSW), PORT GENERATOR CUMMINS QSB 4.5 112kW @ 1500RPM, STBD GENERATOR CUMMINS QSB 4.5 112kW @ 1500RPM, MAIN SYSTEM HEAT EXCHANGER - PORT 010-01, MAIN SYSTEM HEAT EXCHANGER - STBD 010-02, HYDRAULIC PUMPS HEAT EXCHANGER, PITCH CONTROL HEAT EXCHANGER 012-01, ANTI-SIPHON MANIFOLD 015-01, ANTI-SIPHON MANIFOLD 015-02
### openai — 35 elements
- agreed with all: 0 · unique to openai: 35
- unique reads (VERIFY THESE — disagreement or fabrication): SEACHEST 001-01, ANTI-SIPHON MANIFOLD 015-01, ANTI-SIPHON MANIFOLD 015-02, MAIN SYSTEM HEAT EXCHANGER 010-01, MAIN SYSTEM HEAT EXCHANGER 010-02, HYDRAULIC PUMPS HEAT EXCHANGER 011-01, PITCH CONTROL HEAT EXCHANGER 012-01, CPP SEAWATER PUMP 005-05, MAIN COOLING SEAWATER PUMP (PORT), MAIN COOLING SEAWATER PUMP (STBD), FLOW SENSOR 016-01, FLOW SENSOR 016-02, 017-01, 017-02, 019-01, 019-02, 017-03, 017-04, 019-03, 019-04, 005-03, 005-04, 005-01, 005-06, 018-02, 018-01, CATHODIC GALVANIC PROTECTION CONTROL UNIT 009-01, 80L FWD BOILER, 80L AFT BOILER, PORT GENERATOR CUMMINS QSB 4.5 112kW @ 2500RPM, STBD GENERATOR CUMMINS QSB 4.5 112kW @ 2500RPM, 003-02 SEAWATER STRAINER, 003-03 SEAWATER STRAINER, AIRCON SYSTEM REF. DWG 108-01-S90-001, WATERMAKER UNITS REF. DWG 108-01-S10-001


## 6-plc-io — AFT-PLC-rev4-p21

### anthropic — 12 elements
- agreed with all: 0 · unique to anthropic: 12
- unique reads (VERIFY THESE — disagreement or fabrication): 2DO Module POS.13 - TYPE 750-508, CPU 750-8213 (DO-03), DO-03 CH 01 - EV 10.1A (transom door CLOSE), DO-03 CH 02 - EV 10.1B (transom door OPEN), Connector Type I (DO-03), 2DO Module POS.14 - TYPE 750-508, CPU 750-8213 (DO-04), DO-04 CH 01 - EV 10.2A (deck door OPEN), DO-04 CH 02 - EV 10.2B (deck door CLOSE), Connector Type I (DO-04), 2DO Module POS.15 - TYPE 750-508, CPU 750-8213 (DO-05), DO-05 CH 01 - EV 10.3A (mainsheet traveler TO PORT), DO-05 CH 02 - EV 10.3B (mainsheet traveler TO STBD), Connector Type I (DO-05)
### gemini — 22 elements
- agreed with all: 0 · unique to gemini: 22
- unique reads (VERIFY THESE — disagreement or fabrication): 2 DO MODULE (POS.13) 750-508 DO-03, 2 DO MODULE (POS.14) 750-508 DO-04, 2 DO MODULE (POS.15) 750-508 DO-05, 2DO, TYPE: 750-508, CPU: 750-8213, POS.: 13, DO-03
CH 01, DO-03
CH 02, transom door
CLOSE
(EV 10.1A), transom door
OPEN
(EV 10.1B), CONNECTOR TYPE I
(see sheet 4), POS.: 14, DO-04
CH 01, DO-04
CH 02, deck door
OPEN
(EV 10.2A), deck door
CLOSE
(EV 10.2B), POS.: 15, DO-05
CH 01, DO-05
CH 02, mainsheet
traveler
TO PORT
(EV 10.3A), mainsheet
traveler
TO STBD
(EV 10.3B)
### openai — 12 elements
- agreed with all: 0 · unique to openai: 12
- unique reads (VERIFY THESE — disagreement or fabrication): EV 10.1A — transom door CLOSE, EV 10.1B — transom door OPEN, EV 10.2A — deck door OPEN, EV 10.2B — deck door CLOSE, EV 10.3A — mainsheet traveler TO PORT, EV 10.3B — mainsheet traveler TO STBD, DO-03 — 2DO module TYPE 750-508, CPU 750-8213, POS. 13, DO-04 — 2DO module TYPE 750-508, CPU 750-8213, POS. 14, DO-05 — 2DO module TYPE 750-508, CPU 750-8213, POS. 15, CONNECTOR TYPE I (see sheet 4) — EV 10.1A/EV 10.1B, CONNECTOR TYPE I (see sheet 4) — EV 10.2A/EV 10.2B, CONNECTOR TYPE I (see sheet 4) — EV 10.3A/EV 10.3B


## 6-plc-io — AFT-PLC-rev4-p27

### anthropic — 9 elements
- agreed with all: 1 · unique to anthropic: 8
- unique reads (VERIFY THESE — disagreement or fabrication): 750-559 (5 AO module, POS.27/28), AO-01 CH01 (A1) - EV 10.5 Primary winch port, AO-01 CH02 (A2) - EV 10.4 secondary winch port, AO-01 CH03 (A3) - EV 8.4 Primary winch stbd, AO-01 CH04 (A4) - EV 8.3 secondary winch stbd, 16.8A +24Vdc (field), 20.7B 0V, 04.6 BK 1,5
### gemini — 6 elements
- agreed with all: 1 · unique to gemini: 5
- unique reads (VERIFY THESE — disagreement or fabrication): 5 AO MODULE 750-559, Primary winch port (EV 10.5), secondary winch port (EV 10.4), Primary winch stbd (EV 8.4), secondary winch stbd (EV 8.3)
### openai — 8 elements
- agreed with all: 1 · unique to openai: 7
- unique reads (VERIFY THESE — disagreement or fabrication): 5 AO / TYPE: 750-559 / CPU: 750-8213 / POS.: 28, Primary winch port (EV 10.5), secondary winch port (EV 10.4), Primary winch stbd (EV 8.4), secondary winch stbd (EV 8.3), +24Vdc (field), 0V


## 7-building-ga — steering-system-ga

### anthropic — 42 elements
- agreed with all: 4 · unique to anthropic: 38
- unique reads (VERIFY THESE — disagreement or fabrication): UPPER BEARING STRUCTURE (SEE DWG 108-05-151-001), LOWER BEARING STRUCTURE (SEE DWG 108-05-151-002), TRI-BEAM 11, 6 + 7, AUTOPILOT RAM SUPPORT / BOLTED THROUGH BHD L, BOND SHEAVE BOXES HORIZONTALLY, MAKE PENETRATION IN TRI-BEAM TO SUIT PILOT ROD MOVEMENT, DETAIL A (SCALE 1:10), PORT LOWER SHEAVE BOX DETAIL (SCALE NTS), PLAN VIEW (SCALE 1:20), SECTION B-B LOOKING TO PORT PARTITION LM HIDDEN (SCALE 1:20), SECTION C-C THROUGH RUDDER BLADE VIEW ROTATED 26° (SCALE 1:10), DETAIL D (SCALE 1:5), DETAIL E (SCALE 1:5), TRACK SUPPORT WITH 16mm TAPPING PLATE INSERT SEE DWG 108-01-150-006, STN 10, DWL, DATUM 0, ITEM 1 - 100mm ALUMINIUM SHEAVE, ITEM 2 - 220mm BOTTOM RUDDER BEARING, ITEM 3 - 220mm RUDDER BEARING HOUSING, ITEM 4 - 180mm TOP RUDDER BEARING, ITEM 5 - 180mm RUDDER BEARING HOUSING, ITEM 6 - WATER TIGHT SYSTEM NEOPRENE TUBE, ITEM 7 - SWS Rudderretainer, ITEM 8 - UPPER SHEAVE BOX, ITEM 9 - LOWER SHEAVE BOX, ITEM 10 - SHEAVE PINS SET, ITEM 11 - TRACK 1100mm, ITEM 12 - E-GLASS WEDGE STOPS, ITEM 13 - ASSEMBLED CAR, ITEM 14 - VECTRAN LINE 20mm, ITEM 15 - ROD LINK CARBON TUBE + BHD FITTINGS + M16 BALL JOINTS, ITEM 16 - PORT ASSEMBLED RACING TILLER ARM 1400mm ARM 600/240, ITEM 17 - STBD ASSEMBLED RACING TILLER ARM 1400mm ARM 600/240, ITEM 18 - RUDDER, ITEM 19 - AUTOPILOT RAM 300mm STROKE, ROD LINK LENGTH / TOE-IN ANGLE TABLE, ACKERMANN EFFECT TABLE
### gemini — 27 elements
- agreed with all: 4 · unique to gemini: 23
- unique reads (VERIFY THESE — disagreement or fabrication): TRI-BEAM 11, UPPER BEARING STRUCTURE
SEE DWG 108-05-151-001, LOWER BEARING STRUCTURE
SEE DWG 108-05-151-002, DETAIL A
SCALE 1 : 10, PORT LOWER SHEAVE
BOX DETAIL
SCALE NTS, PLAN VIEW
SCALE 1 : 20, ON DECK INNER SKIN, G10 SPACER, AUTOPILOT RAM SUPPORT
IS BOLTED THROUGH BHD L
BOND TAPPING PLATES ON FWD FACE, ON HULL OUTER SKIN, BOND SHEAVE BOXES HORIZONTALLY, SYSTEM NOTES:
- RUDDERS HAVE 1.8° TOE-IN ANGLE IN NEUTRAL
POSITION WITH THE ROD'S LINKS 2044mm LONG.
THIS CAN BE FINE TUNED BY CHANGING THE
LENGTH OF THE RODS
- CAR RACE TO BE ±365mm FROM CL
ACKERMANN EFFECT AS FOLLOWS:, SAFETY NOTES:
- NO EMERGENCY STEERING SYSTEM NEEDED.
- 3 INDEPENDENT SYSTEMS IN PLACE: 2 WHEELS + PILOT
- IN CASE OF SINGLE ROD FAILURE, ONE RUDDER STILL ACTIVE
- IN CASE OF SINGLE WHEEL FAILURE, SECOND WHEEL REMAINS
IN CONTROL OF BOTH RUDDERS
- IN CASE OF FAILURE OF BOTH WHEELS, PILOT STILL IN CONTROL
OF RUDDERS, VARIATION OF TOE-IN ANGLE
AT NEUTRAL POSITION DEPENDING
ON ROD LINK LENGTH, ACKERMANN EFFECT, STANDARD NOTES:
- DO NOT SCALE. PROJECTION : 1st ANGLE.
- ALL DIMENSIONS IN mm UNLESS OTHERWISE INDICATED.
- DIMENSIONS TO BE ±0.5mm UNLESS OTHERWISE INDICATED.
- BREAK ALL SHARP EDGES.
- ALL EQUIPMENT WEIGHTS TO BE NOTED, Southern Wind, APPROVED
REVIEWED, Steering System GA, SECTION C-C
THROUGH RUDDER BLADE
VIEW ROTATED 26°
SCALE 1 : 10, DETAIL D
SCALE 1 : 5, DETAIL E
SCALE 1 : 5, SECTION B-B
LOOKING TO PORT
PARTITION LM HIDDEN
SCALE 1 : 20
### openai — 17 elements
- agreed with all: 4 · unique to openai: 13
- unique reads (VERIFY THESE — disagreement or fabrication): UPPER BEARING STRUCTURE SEE DWG 108-05-151-001, TRI-BEAM 11, LOWER BEARING STRUCTURE SEE DWG 108-05-151-002, PORT LOWER SHEAVE BOX DETAIL, CL, AUTOPILOT RAM SUPPORT IS BOLTED THROUGH BHD L, TRACK SUPPORT WITH 16mm TAPPING PLATE INSERT SEE DWG 108-01-150-004, 16 PORT / 17 STBD, DWL, SYSTEM NOTES, SAFETY NOTES, Steering System GA, 108-01-150-001


## 7-building-ga — systems-ga-500-001b

### anthropic — 0 elements
- agreed with all: 0 · unique to anthropic: 0
### gemini — 0 elements
- agreed with all: 0 · unique to gemini: 0
### openai — 29 elements
- agreed with all: 0 · unique to openai: 29
- unique reads (VERIFY THESE — disagreement or fabrication): PORT LAZARETTE, STBD LAZARETTE, TRANSOM, PORT CREW CABIN, STBD CREW CABIN, MAIN FRIDGE & FREEZER UNIT, GALLEY, CREW MESS, AFT GUEST CABIN PORT, AFT GUEST CABIN STBD, PORT AFT GUEST HEAD, STBD AFT GUEST HEAD, AFT CREW HEAD, A/T CREW SHOWER, FWD CREW CABIN, FWD GUEST HEAD, FWD GUEST CABIN, SALOON (ENGINE ROOM BELOW), STUDIO, OWNERS CABIN, OWNERS HEAD, PORT FUEL TANK, PORT FRESH WATER TANK, STBD FUEL TANK, A/T GREY TANK, A/T BLACK TANK, PORT GREY TANK, STBD BLACK WATER TANK, PLAN VIEW - ENGINE ROOM


## 8-bae-interconnect-pinout — bae-block-interconnect-p12

### anthropic — 8 elements
- agreed with all: 2 · unique to anthropic: 6
- unique reads (VERIFY THESE — disagreement or fabrication): BEL (RTN1), BEL (RTN1) #2, SYNC (pins 10,3), SYNC (pins 9,4), CAN-A (Shield/HI/LO), CAN-A (Shield/HI/LO) #2
### gemini — 38 elements
- agreed with all: 2 · unique to gemini: 36
- unique reads (VERIFY THESE — disagreement or fabrication): G3-S3S1 FREQ_SELECT, BEL, G3-S3R1 VBATTERY RTN, RTN1, G3-S321 CHAIN_OUTPUT, SYNC, G3-S3R1 SYNC_RTN, 10, G3-S3S2 SYNC, 3, G3-S329 ENABLE, N/C, CAN-A, G3-S300a ADR_0, Shield, G3-S300b ADR_1, HI, G3-S3AH CANA_HI, LO, G3-S3AL CANA_LO, G3-S3AS CANA_Shield, G3-S3S3 CHAIN_SUPPLY, G3-S4S1 FREQ_SELECT, G3-S4R1 VBATTERY RTN, G3-S421 CHAIN_OUTPUT, G3-S4R1 SYNC_RTN, 9, G3-S4S2 SYNC, 4, G3-S429 ENABLE, G3-S400a ADR_0, G3-S400b ADR_1, G3-S4AH CANA_HI, G3-S4AL CANA_LO, G3-S4AS CANA_Shield, G3-S4S3 CHAIN_SUPPLY
### openai — 11 elements
- agreed with all: 2 · unique to openai: 9
- unique reads (VERIFY THESE — disagreement or fabrication): BEL / RTN1, SYNC / 10 / 3, CAN-A / Shield / HI / LO, SYNC / 9 / 4, G3-S3R1 SYNC RTN, G3-S4R1 SYNC_RTN, G3-S3S3 CHAIN_SUPPLY, G3-S4S3 CHAIN_SUPPLY, 1905D023


## 8-bae-interconnect-pinout — bae-pinout-p31

### anthropic — 0 elements
- agreed with all: 0 · unique to anthropic: 0
### gemini — 19 elements
- agreed with all: 0 · unique to gemini: 19
- unique reads (VERIFY THESE — disagreement or fabrication): CAN D STBD, CAN Terminator 120 Ohm, CAN Y CONNECTOR, 24V RTN to CAN shield, SCU, DISPLAY NAV, ESS, EDN STBD, HCP, ECP3, ECP4, BCP, ALARM NAV, ISOLATOR, BEL4, BEL3, MC43, CIB STBD, ENG STBD with 120 Ohm
### openai — 20 elements
- agreed with all: 0 · unique to openai: 20
- unique reads (VERIFY THESE — disagreement or fabrication): CAN D STBD, CAN Terminator 120 Ohm, CAN Y CONNECTOR, 24V RTN to CAN shield, SCU, DISPLAY AFT, ALARM NAV, ESS, EDN STBD, HEP, ECP3, ECP4, BCP, ISOLATOR, BL4, BEL3, MC43, CBS STBD, EMS STBD with 120 Ohm, 19D5D023


## 9-class-c-garbled-font — er-trunking-680-004

### anthropic — 6 elements
- agreed with all: 0 · unique to anthropic: 6
- unique reads (VERIFY THESE — disagreement or fabrication): 120W x 120H custom aluminium trunking (yellow), 200W x 50H perforated metal cable tray (teal), BOM table, Isometric trunking assembly view, Title block - Southern Wind, Hatch/door
### gemini — 0 elements
- agreed with all: 0 · unique to gemini: 0
### openai — 7 elements
- agreed with all: 0 · unique to openai: 7
- unique reads (VERIFY THESE — disagreement or fabrication): 120W x 120H custom aluminium trunking, 200W x 50H perforated metal cable tray, G68, DC FH, K:8, FCCA, Southern Wind


## 9-class-c-garbled-font — termodinamica-wiring-rev0

### anthropic — 0 elements
- agreed with all: 0 · unique to anthropic: 0
### gemini — 25 elements
- agreed with all: 0 · unique to gemini: 25
- unique reads (VERIFY THESE — disagreement or fabrication): Breaker B1 (Port), TMD Internet Interface, Touch Screen Interface (Addr.1, Port), MRMAXI18i (Addr.2), MRMAXI30i (Addr.3), MRMAXI18i (Addr.4), MRMAXI30i (Addr.5.0), MRMAXI30i (Addr.5.1), MRMAXI18i (Addr.6), AC/DC Current Sensor TRMS (Addr.31, Port), TMD Bridge (Addr.32, Port), VRV18E1 ENGINE ROOM PORT, SEA WATER PUMP TMD100 (Port), Switch BUS Box Connection, Breaker B1 (Stbd), Touch Screen Interface (Addr.1, Stbd), MRMAXI18i (Addr.7), MRMAXI18i (Addr.8), MRMAXI18i (Addr.9), MRMAXI30i (Addr.10), MRMAXI30i (Addr.11), AC/DC Current Sensor TRMS (Addr.31, Stbd), TMD Bridge (Addr.32, Stbd), VRV18E1 ENGINE ROOM STBD, SEA WATER PUMP TMD100 (Stbd)
### openai — 35 elements
- agreed with all: 0 · unique to openai: 35
- unique reads (VERIFY THESE — disagreement or fabrication): Main Switchboard / Breaker 40 amp C or D curve / B1 (PORT), VRV18E1 ENGINE ROOM PORT, SEA WATER PUMP TMD100 (PORT), INTERNET ROUTER, TMD Internet Interface, Touch Screen Interface Addr.1 (upper), MRMAXI18i Fwd Guest cabin Addr.2, MRMAXI30i Salon port Addr.3, MRMAXI18i Aft Guest cabin port Addr.4, MRMAXI30i Fwd Galley Addr.5.0, MRMAXI30i Aft Galley Addr.5.1, MRMAXI18i Aft Crew cabin port Addr.6, AC/DC Current Sensor TRMS Addr.31, TMD Bridge Addr.32, Switch BUS Box Connection, Main Switchboard / Breaker 40 amp C or D curve / B1 (STBD), VRV18E1 ENGINE ROOM STBD, SEA WATER PUMP TMD100 (STBD), Touch Screen Interface Addr.1 (lower), MRMAXI18i Aft Crew cabin stbd Addr.7, MRMAXI18i Fwd Crew cabin stbd Addr.8, MRMAXI18i Aft Guest cabin stbd Addr.9, MRMAXI30i Salon stbd Addr.10, MRMAXI30i Owner's cabin Addr.11, AC/DC Current Sensor TRMS Addr.31 (lower), TMD Bridge Addr.32 (lower), SxythSense Touch Screen Connection, VRV18E1 Terminal Block Connection, Sxythsense Touch Screen & SubSlave Air Handler Connection, Air Handler Wiring, Air Handler Port and Stbd Connection, Air Handler Master and Slave Air Handler Connection, TSTE 7” Exor Touch Screen & Dual Touch Screen Interfaces Connection, AC/DC Current Sensor TRMS mod. QI-50-V-485, Switch BUS Box Connection (detail)


## 10-photos-figures — harken-spares-photo-3325

### anthropic — 3 elements
- agreed with all: 0 · unique to anthropic: 3
- unique reads (VERIFY THESE — disagreement or fabrication): Harken parts bag label - Part Number A72931800, Description: Needle Roller Bearing 120x126x19, QTY 2, PO Number SWS108#1 ID13398
### gemini — 4 elements
- agreed with all: 0 · unique to gemini: 4
- unique reads (VERIFY THESE — disagreement or fabrication): HARKEN, A72931800, Needle Roller Bearing i20xi26x19, SWS108#1 ID13398
### openai — 1 elements
- agreed with all: 0 · unique to openai: 1
- unique reads (VERIFY THESE — disagreement or fabrication): HARKEN® — A72931800 — Needle Roller Bearing — 120x126x19


## 10-photos-figures — harken-spares-photo-3330

### anthropic — 1 elements
- agreed with all: 0 · unique to anthropic: 1
- unique reads (VERIFY THESE — disagreement or fabrication): Harken part label - A74506900 Needle roller bearing 25x35x15
### gemini — 4 elements
- agreed with all: 0 · unique to gemini: 4
- unique reads (VERIFY THESE — disagreement or fabrication): HARKEN, Part Number A74506900, Description Needle roller bearing 25x35x15, PO Number SWS108#1 ID13398
### openai — 2 elements
- agreed with all: 0 · unique to openai: 2
- unique reads (VERIFY THESE — disagreement or fabrication): HARKEN® A74506900 — Needle roller bearing i25xi35x15, SVS108#1 ID1338
