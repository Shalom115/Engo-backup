# HyDE question archetypes — deferred from ingestion, NOT dropped

Recorded 2026-07-31 from the engineer's reading-order note. These are the
questions a populated node should be able to answer. They are **not** part of
the extraction pass: extraction records what is DRAWN; these are derived from a
node once its facts and traced loops are in place. Building them during
ingestion would mean inventing consequences before the circuit is known.

Run this AFTER the book ingestion lands, against the written nodes.

## 1. Protection consequence — "what does this fuse protect?"
Engineer, verbatim: *"when seeing a fuse think what it protects (this specific
one is also very good for HyDE — what it protects and what will not work if it
burns)."*

Per protective device on a node, generate both directions:
- what sits DOWNSTREAM of `F3 60A` — i.e. everything that loses supply if it opens;
- for each downstream load, what protects it — the reverse lookup an engineer
  actually makes at 3am.

Answerable only from a **complete** traced loop, which is why it waits for
ingestion. The `loop_completeness` record on each sheet says which devices are
fully traced and therefore safe to generate against — never generate a
consequence claim from a half-traced device.

## 2. Fault scenarios — "what happens when a scenario changes or a fault occurs"
- coil de-energised / energised on each relay, with the NO-vs-NC consequence
  stated (a load on NC is ON until the coil energises);
- a rail lost: which loads drop with `+24V SERVICE`, which survive on
  `+24V EMERGENCY`;
- a relay chain broken mid-way — what still operates downstream;
- pump/valve lineup changes for fluid systems (the P&ID `flow_scenarios`
  already record the normal and alternate lineups; the FAULT variants are HyDE).

## 3. Interaction questions — one component, several relationships
Engineer: *"each component can interact with more than one thing."* A relay
that switches a pump AND reports status to the monitoring system needs both
relationships reachable from either side.

## 4. Cross-sheet continuation
Where `loop_completeness` reports a device leaving the sheet, the HyDE question
is the continuation: *"the return for X leaves on DWG 110c — where does it
land?"* These are already filed as open questions during ingestion
(`pipeline/open_questions.py`); HyDE turns the ANSWERED ones into retrievable
Q&A.

## Guard rail
Every generated question must cite the node fact it derives from. A HyDE answer
with no underlying traced fact is a fabrication with a question mark on it, and
is worse than no coverage — it is retrievable and reads as authoritative.
