# Vision benchmark — side-by-side (engineer grades)

Generated 2026-07-15T19:40:34+00:00.

Per sheet: what each provider extracted, agreement/disagreement in element labels, runtime. Grade on: correctness vs the actual sheet, fabrication (worst failure), <UNKNOWN> honesty (credit), completeness.


## 1-hydraulic-manifold — mast_block

### anthropic — 60 elements
- agreed with all: 11 · unique to anthropic: 49
- unique reads (VERIFY THESE — disagreement or fabrication): LIFTING KEEL UP/DOWN (identifiers printed on crop: 111668, 157B5111), 111668, 157B5111, 300, unlabeled work-port relief, unlabeled check valve, LIFTING KEEL UP/DOWN (EV-6.1), 157B7122, 220, 60, MAST WINCH AFT PORT (EV-6.3), 250, 225, MAST WINCH FWD PORT / MAST WINCH AFT PORT (EV-6.4 / EV-6.5), MAST WINCH AFT STBD - EV-6.5, 230, PVG 32 MODULE, spool 40 lt/min, PVEU - 0-10 V, DOWN <5V =A / UP>5V =B, open neutral position, spool 5 lt/min, PVEO - ON/OFF, IN=A / OUT=B, closed neutral position, spool 65 lt/min, 1°&3° =A/2° =B, MAST<illegible> AFT<illegible>, MAST FWD S<illegible>, 2 MODULE, 65 lt/min, - ON/OFF, =A/2° =B, neutral position, 9 | 25/09/2023 | PT | PC | PRESSURE ADJUSTEMENT, 8 | 29/08/2023 | PT | PC | PRESSURE AFTER COMMISSIONING, 7 | 25/07/2023 | PT | -- | TENDER WINCH SPOOL, 6 | 12/06/2023 | PT | -- | CAPTIVE WINCH AND TENSIONER BLOCKS HARKEN, 5 | 29/05/2023 | PT | -- | DOORS OVERCENTER PRES., FORESTAY MAN. VALVE, 4 | 28/04/2023 | PT | -- | PITCH PROPELLER SYS. SUCTION AND RETURN LINE
- node routing (same backbone for every provider):
    - Danfoss PVG 32 → attach [570-danfoss-pvg-32-mast-block] via -
    - LIFTING KEEL UP/DOWN → attach [130-apm-lifting-keel] via control_map
    - LIFTING KEEL LOCKS → attach [130-apm-lifting-keel] via control_map
    - MAST WINCH AFT PORT → attach [220-mast-winch-aft-port] via control_map
    - MAST WINCH FWD PORT → attach [220-mast-winch-fwd-port] via control_map
    - MAST WINCH AFT STBD → attach [220-mast-winch-aft-stbd] via control_map
    - MAST WINCH FWD STBD → attach [220-mast-winch-fwd-stbd] via control_map
### gemini — 20 elements
- agreed with all: 11 · unique to gemini: 9
- unique reads (VERIFY THESE — disagreement or fabrication): EV-6.1 LIFTING KEEL UP/DOWN, 157B7122, EV-6.2 KEEL LIFTING KEEL LOCKS, 157B7125, 11130982, KEEL MAST WINCH AFT PORT / EV-6.3, MAST WINCH FWD PORT (EV-6.4), EV-6.5, MAST WINCH FWD STBD (EV-6.6)
- node routing (same backbone for every provider):
    - DANFOSS PVG 32 → attach [570-danfoss-pvg-32-mast-block] via -
    - LIFTING KEEL UP/DOWN → attach [130-apm-lifting-keel] via control_map
    - LIFTING KEEL LOCKS → attach [130-apm-lifting-keel] via control_map
    - MAST WINCH AFT PORT → attach [220-mast-winch-aft-port] via control_map
    - MAST WINCH FWD PORT → attach [220-mast-winch-fwd-port] via control_map
    - MAST WINCH AFT STBD → attach [220-mast-winch-aft-stbd] via control_map
    - MAST WINCH FWD STBD → attach [220-mast-winch-fwd-stbd] via control_map
### openai — 51 elements
- agreed with all: 11 · unique to openai: 40
- unique reads (VERIFY THESE — disagreement or fabrication): LIFTING KEEL L… — EV-6.1 (function text is cropped after “L”), 15783712, [no legible part identifier], KEEL LIFTING KEEL LOCKS — EV-6.2, 157B7125, 11130982, EL MAST WINCH AFT PORT — EV-6.3, 15781723, [illegible], [identifier illegible], MAST WINCH FWD PORT — EV-6.4, 15761723, MAST WINCH AFT STBD — EV-6.5, C50, C25, MAST WINCH FWD STBD — EV-6.6, 157817123, 230, 225, 10 | 16/04/2026 | PT | PC | PROPORTIONAL AFT WINCHES, 9 | 25/09/2023 | PT | PC | PRESSURE ADJUSTEMENT, 8 | 29/08/2023 | PT | PC | PRESSURE AFTER COMMISSIONING, 7 | 25/07/2023 | PT | -- | TENDER WINCH SPOOL, 6 | 12/06/2023 | PT | -- | CAPTIVE WINCH AND TENSIONER BLOCKS HARKEN, 5 | 29/05/2023 | PT | -- | DOORS OVERCENTER PRES., FORESTAY MAN. VALVE, 4 | 28/04/2023 | PT | -- | PITCH PROPELLER SYS. SUCTION AND RETURN LINE, 3 | 13/12/2022 | PT | -- | ADD. TAFT MAST SAILING, DECK DOOR 2nd LINE, 2 | 11/11/2022 | PT | PR | SAILING MAN., PRESSURE SENSORS, PVG UPDATE, 1 | 07/10/2022 | PR | PT | BACKUP P.PACK, CAPTIVE & EV NUM., WINDLASS, 0 | 27/07/2022 | PT | PR | FIRST ISSUE, REV | DATE | DRAWN | CHECKED | MODIFICATIONS, MYT SYSTEMS | JOB N°: | 22-53 | CLIENT: | Southern Wind Shipyard | PROJECT: | SWS 108, TITLE: | HYDRAULIC SYSTEM | REV: | 10, MYT-Systems S.r.l. | SECTION: | DIAGRAM | DATE: | 16/04/2026, Via Borzoli 39,130P,16153 Genova (GE) | DRAWN: | PT | CHECKED: | PC | SCALE: | not to scale @ A3 | SHEET: | 5 of 12, ITALY | FILE NAME: | SWS108-Hydraulic_System-rev10-Mast_block, Tel: +390185380903, email: info@myt-systems.com, This drawing and the contained informations are property of MYT-Systems S.r.l. and protected by law. Copying, disclosure, and any other use are prohibited except with written permission of MYT-Systems S.r.l..
- node routing (same backbone for every provider):
    - Danfoss PVG 32 → attach [570-danfoss-pvg-32-mast-block] via -
    - LIFTING KEEL UP/DOWN → attach [130-apm-lifting-keel] via control_map
    - LIFTING KEEL LOCKS → attach [130-apm-lifting-keel] via control_map
    - MAST WINCH AFT PORT → attach [220-mast-winch-aft-port] via control_map
    - MAST WINCH FWD PORT → attach [220-mast-winch-fwd-port] via control_map
    - MAST WINCH AFT STBD → attach [220-mast-winch-aft-stbd] via control_map
    - MAST WINCH FWD STBD → attach [220-mast-winch-fwd-stbd] via control_map
