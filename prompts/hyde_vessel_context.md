Vessel: SY Gelliceaux — Southern Wind 108 hybrid sailing yacht.

- Exocet (Pixel Sur Mer) data channels use names like BAE_Motor_LoadPower_pt
  (port MPCS motor load), BAE_Motor_LoadPower_stbd (stbd), BAE_MPCS_* for motor
  control system channels. Engineers search by these exact channel names when
  diagnosing faults.
- Propulsion: ACTM = BAE GPM-12 (direct-drive, oil-less), driven by either MPCS_P
  or MPCS_S via the HVPDU S2 switch. Only one MPCS drives the motor at a time;
  both channels showing load simultaneously is a fault condition.
- Key systems: BEL (inverter), MPCS (Modular Propulsion Control System),
  HVPDU (high voltage power distribution unit), MAPS (Modular Accessory Power
  System), EDN-S (shore power converter), ESS (Akasol energy storage),
  SCU3 (System Control Unit), ISG (Integrated Starter Generator).
- Engineers abbreviate freely: "the BAE", "S2 switch", "stbd MPCS", "the BEL
  crashed", "running on batteries" (EV mode), "both sides hot" (S1 isolation
  fault), "the Hundested" (CPP), "the rams" (sailing hydraulic cylinders).
