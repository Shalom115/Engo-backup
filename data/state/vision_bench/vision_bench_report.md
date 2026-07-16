# Vision benchmark — side-by-side (engineer grades)

Generated 2026-07-15T20:09:10+00:00.

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


## 1-hydraulic-manifold — AFT_blockC

### anthropic — 32 elements
- agreed with all: 9 · unique to anthropic: 23
- unique reads (VERIFY THESE — disagreement or fabrication): TRANSOM DOOR - PVG 32 MODULE (EV-10.1), part 11166838, 157B7121, DECK DOOR - EV-10.2 (PVG 32 MODULE), MAINSHEET TRAVELER, SECONDARY WINCH PORT - PVG 32 MODULE - EV-10.4, PRIMARY WINCH PORT - PVG 32 MODULE (EV-10.5), part 11166832, 157B7126, illegible symbol - possible flow control/check, PRIMARY WINCH PORT -> PVG 32 MODULE (EV-10.7 label visible on this crop, though sheet table associates EV-10.5 with "PRIMARY WINCH PORT" spool 65 lt/min - see note in illegible), 157B2014, <UNKNOWN>, UNLABELED VALVE (M/LS area, left of Transom Door), TRANSOM DOOR - PVG 32 MODULE (function slice, part of AFT BLOCK C: DANFOSS PVG 32 - 5 FUNCTIONS), AUXILIARY VALVE 1, PRIMARY WINCH PORT - EV-10.5 (PVG 32 MODULE, AFT BLOCK C), AUXILIARY VALVE 2, SECONDARY WINCH PORT -> PVG 32 MODULE (EV-10.4), JOB N°: 22-53 | CLIENT: Southern Wind Shipyard | PROJECT: SWS 108, TITLE: HYDRAULIC SYSTEM | REV: 10, SECTION: DIAGRAM | DATE: 16/04/2026, DRAWN: PT | CHECKED: PC | SCALE: not to scale @ A3 | SHEET: 8 of 12, FILE NAME: SWS108-Hydraulic_System-rev10-AFT_blockC, This drawing and the contained informations are property of MYT-Systems S.r.l. and protected by law. Copying, disclosure and any other use are prohibited except with written permission of MYT-Systems S.r.l..
- node routing (same backbone for every provider):
    - Danfoss PVG 32 → attach [570-danfoss-pvg-32-aft-blockc] via -
    - TRANSOM DOOR → attach [260-transom-door] via control_map
    - DECK DOOR → attach [260-deck-door] via control_map
    - MAINSHEET TRAVELER → attach [840-cariboni-hydraulic-cylinders] via control_map
    - SECONDARY WINCH PORT → attach [220-secondary-winch-port] via control_map
    - PRIMARY WINCH PORT → attach [220-primary-winch-port] via control_map
    - UNLABELED VALVE (M/LS area, left of Transom Door) → attach [260-transom-door] via control_map
    - AUXILIARY VALVE 1 → create_flagged [—] via no_match
    - AUXILIARY VALVE 2 → create_flagged [—] via no_match
### gemini — 31 elements
- agreed with all: 9 · unique to gemini: 22
- unique reads (VERIFY THESE — disagreement or fabrication): 157B7121, DECK DOOR (EV-10.2), 157B7125, 157B6203, MAINSHEET TRAVELER, MAINSHEET TRAVELER EV-10.3, SECONDARY WINCH PORT (EV-10.4), 157B7126, LSA, LSB, 11166832 (EV-10.5), EV-10.6, 10 | 16/04/2026 | PT | PC | PROPORTIONAL AFT WINCHES, 9 | 25/09/2023 | PT | PC | PRESSURE ADJUSTEMENT, 8 | 29/08/2023 | PT | PC | PRESSURE AFTER COMMISSIONING, 7 | 25/07/2023 | PT | -- | TENDER WINCH SPOOL, 6 | 12/06/2023 | PT | -- | CAPTIVE WINCH AND TENSIONER BLOCKS HARKEN, 5 | 29/05/2023 | PT | -- | DOORS OVERCENTER PRES., FORESTAY MAN. VALVE, 4 | 28/04/2023 | PT | -- | PITCH PROPELLER SYS. SUCTION AND RETURN LINE, 3 | 13/12/2022 | PT | -- | ADD. T AFT MAST SAILING, DECK DOOR 2nd LINE, 2 | 11/11/2022 | PT | PR | SAILING MAN., PRESSURE SENSORS, PVG UPDATE, 1 | 07/10/2022 | PR | PT | BACKUP P.PACK, CAPTIVE & EV NUM., WINDLASS
- node routing (same backbone for every provider):
    - DANFOSS PVG 32 → attach [570-danfoss-pvg-32-aft-blockc] via -
    - TRANSOM DOOR → attach [260-transom-door] via control_map
    - DECK DOOR → attach [260-deck-door] via control_map
    - MAINSHEET TRAVELER → attach [840-cariboni-hydraulic-cylinders] via control_map
    - SECONDARY WINCH PORT → attach [220-secondary-winch-port] via control_map
    - PRIMARY WINCH PORT → attach [220-primary-winch-port] via control_map
### openai — 57 elements
- agreed with all: 9 · unique to openai: 48
- unique reads (VERIFY THESE — disagreement or fabrication): TRANSOM DOOR — EV-10.1, PVEO, DECK DOOR — EV-10.2, 157B?245, 11166838 (block/package marking), MAINSHEET TRAVELLER, MAINSHEET TRAVELLER — EV-10.3, 15781712, SECONDARY WINCH PORT — EV-10.4, 15787216, PRIMARY WINCH PORT — EV-10.5, 15787126, PVG 32 MODULE, SPOOL 25 lt/min, PVEO - ON/OFF, OPEN=B / CLOSE=A, open neutral position, EV-101, pressure to
be checked:
45 bar in
opening and
170 in closing, A, B, spool 5 lt/min, TO PORT=A / TO STBD=B, closed neutral position, EV-10.3, spool 40 lt/min, 1°&3° =A/2° =B, EV-10.4, spool 65 lt/min, PVED - ON/OFF, 10 | 16/04/2026 | PT | PC | PROPORTIONAL AFT WINCHES, 9 | 25/09/2023 | PT | PC | PRESSURE ADJUSTEMENT, 8 | 29/08/2023 | PT | PC | PRESSURE AFTER COMMISSIONING, 7 | 25/07/2023 | PT | -- | TENDER WINCH SPOOL, 6 | 12/06/2023 | PT | -- | CAPTIVE WINCH AND TENSIONER BLOCKS HARKEN, 5 | 29/05/2023 | PT | -- | DOORS OVERCENTER PRES., FORESTAY MAN. VALVE, 4 | 28/04/2023 | PT | -- | PITCH PROPELLER SYS. SUCTION AND RETURN LINE, 3 | 13/12/2022 | PT | -- | ADD. T AFT MAST SAILING, DECK DOOR 2nd LINE, 2 | 11/11/2022 | PT | PR | SAILING MAN., PRESSURE SENSORS, PVG UPDATE, 1 | 07/10/2022 | PR | PT | BACKUP P.PACK, CAPTIVE & EV NUM., WINDLASS
- node routing (same backbone for every provider):
    - Danfoss PVG 32 → attach [570-danfoss-pvg-32-aft-blockc] via -
    - TRANSOM DOOR → attach [260-transom-door] via control_map
    - DECK DOOR → attach [260-deck-door] via control_map
    - MAINSHEET TRAVELLER → attach [840-cariboni-hydraulic-cylinders] via control_map
    - SECONDARY WINCH PORT → attach [220-secondary-winch-port] via control_map
    - PRIMARY WINCH PORT → attach [220-primary-winch-port] via control_map
