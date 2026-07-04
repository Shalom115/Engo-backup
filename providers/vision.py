"""
Vision provider abstraction — image → structured description.

Same pattern as llm/embeddings/vectorstore: abstract interface, concrete vendor
implementation behind it, factory reads env. Code outside providers/ never
imports the anthropic SDK for vision.

The description a VisionProvider returns is the ONLY representation of the image
the agent will hold at retrieval time, so it must carry everything an engineer
would read off the figure: labels, values+units, topology, and — for the
locate-and-mark feature — per-component positions with confidence.

NO-INVENTION RULE (engineer mandate): the model lists only components it can
actually see with legible labels. A confidently-wrong marker on a wiring diagram
actively misdirects an engineer mid-repair — omission beats invention. Every
component carries a confidence level; markers render differently by confidence.

VIDEO SEAM: describe() takes one image; the locator metadata (page / timestamp /
figure_index) lives in the CALLER's chunk schema, not here — so video frames can
reuse this interface unchanged.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


# Prompt per content kind. Schematics get topology; photos get identification;
# certificates get transcription+stamps; figures get readings. Routing the kind
# is the caller's job (it knows the doc_type folder / page classification).
_KIND_INSTRUCTIONS = {
    "schematic": """\
This is an engineering schematic / wiring or piping diagram. Extract:
- Every visible component identifier and label (valve numbers, terminal IDs, wire
  numbers, fuse ratings, pin numbers) — VERBATIM.
- Every measured value and unit (pressures, voltages, amperages, flow rates).
- The TOPOLOGY: what connects to what, supply→load direction, which manifold/bus
  feeds which consumer. An engineer must be able to trace the circuit from your
  words alone.
- A plain-language summary of what this drawing shows and why it matters.""",
    "photo": """\
This is an equipment photograph aboard a yacht. Extract:
- What equipment is shown (type, and make/model if a nameplate or label is legible).
- Every legible label, nameplate value, serial number — VERBATIM.
- Physical context: where it appears to be installed, what it connects to.
- Condition observations only if clearly visible (corrosion, damage, markup).
Do NOT use circuit-topology language; this is identification, not a diagram.""",
    "certificate": """\
This is a certificate / official document (possibly scanned). Extract:
- FULL transcription of all text, verbatim, preserving structure.
- Issuer, holder, dates (issue/expiry), certificate numbers, standards referenced.
- Stamps, seals, signatures and their placement; any handwritten markup.""",
    "figure": """\
This is a figure from an engineering report (scope trace, chart, annotated photo,
test result). Extract:
- What the figure shows and what was measured.
- Every readable value: axis labels, units, peak values, trace names, cursor
  readings, annotations — VERBATIM.
- If the figure is a wiring/circuit diagram, ALSO capture connection topology per
  schematic rules: what connects to what, pin/terminal identities.
- What an engineer should conclude from it (only what the figure itself supports).""",
    "document_page": """\
This is a scanned document page with no machine-readable text layer. Extract:
- FULL transcription of all visible text, verbatim, preserving headings and tables.
- Any figures/diagrams on the page: describe per the schematic rules above.
- Layout notes only where they carry meaning (stamps, margins notes, revisions).""",
    "electrical_diagram": """\
This is an ELECTRICAL wiring/schematic sheet. Read it the way a marine electrician
traces a circuit. For EACH load/device on the sheet, capture as components and in
the description:
- the device and what it is (pump, valve, light, contactor, sensor…);
- its SUPPLY: the protective device that feeds it — by its printed IDENTIFIER and
  rating — and the board/row it sits on if shown. Read the device TYPE correctly:
  a breaker is not a fuse is not a switch; report what the symbol/label actually is.
- EVERY control point that operates it — local switch, panel switch, relay, PLC
  output, and any monitoring/alarm-system taps. List ALL of them; a device often
  has several. A status/signal line that reports state to automation is NOT a power
  feed — keep them distinct. Missing a control point is a real failure.
- terminal/connector IDs and the wire run (terminal strips, connectors, pins);
- CROSS-REFERENCES this sheet names (e.g. "see DWG <n>", "ref sheet <n>") — capture each.
If a symbol or label is ambiguous, mark it ambiguous rather than guessing.
Topology matters: state supply→device→control, and what continues on another sheet.""",
    "plumbed_diagram": """\
This is a PLUMBED system diagram (bilge, fire, fuel, fresh/raw water, hydraulics
fluid side, pneumatics). Read it as a flow path. Capture:
- every pump, valve, tank, strainer, manifold, heat exchanger — by identifier;
- FLOW direction and what each path connects (source → consumer/overboard);
- what ISOLATES what (which valve closes which branch), and any cross-overs;
- set-points/ratings printed on the sheet (pressures, capacities);
- cross-references to other sheets. Do NOT use electrical-circuit language.""",
    "general_arrangement": """\
This is a GENERAL ARRANGEMENT (GA) — a system- or vessel-level map showing how
parts INTERCONNECT (BAE GA, network GA, hydraulic system 'General', layout GAs).
Capture the interconnection graph: which equipment/nodes are shown, what links to
what, across systems; zones/locations if drawn. The value here is the connectivity
map, not per-component detail — describe what connects to what and through what.""",
}

# Behavioural rules (prose — the schema can't enforce judgment). Sent with the prompt.
_COMPONENT_RULES = """\
When you call record_figure:
- components: list ONLY components whose label you can actually read. Never guess
  or infer a label. Omission is correct; invention is the worst failure — a wrong
  marker misdirects an engineer mid-repair.
- bbox is normalized 0..1 [left, top, right, bottom] relative to image size. If you
  cannot place a component reliably, OMIT bbox and state where it is in 'note'
  ("upper-left quadrant, beside the manifold").
- confidence reflects BOTH label legibility AND position certainty: use "high"
  only when the label is clearly legible and the position is certain.
- For photos/certificates with no identifiable labelled components, components = [].
- description is the full searchable extraction; transcription is all visible text
  verbatim ("" if none).\
"""

# Tool schema — forces schema-valid structured output (no free-form JSON parsing).
_FIGURE_TOOL = {
    "name": "record_figure",
    "description": "Record the structured description of the engineering image.",
    "input_schema": {
        "type": "object",
        "properties": {
            "content_type": {"type": "string",
                             "enum": ["schematic", "photo", "certificate",
                                      "figure", "document_page", "electrical_diagram",
                                      "plumbed_diagram", "general_arrangement"]},
            "description": {"type": "string"},
            "transcription": {"type": "string"},
            "components": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "bbox": {"type": "array", "items": {"type": "number"}},
                        "confidence": {"type": "string",
                                       "enum": ["high", "medium", "low"]},
                        "note": {"type": "string"},
                    },
                    "required": ["label", "confidence"],
                },
            },
        },
        "required": ["content_type", "description", "components"],
    },
}


class VisionProvider(ABC):
    """Abstract vision interface."""

    @abstractmethod
    def describe(
        self,
        image_bytes: bytes,
        media_type: str,
        kind: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Describe one image. kind ∈ schematic|photo|certificate|figure|document_page.
        context (optional): {file_name, system, equipment} — grounding hints only.
        Returns {content_type, description, transcription, components, model}.
        Raises on transport failure; returns description="" only if the model
        genuinely could not read the image.
        """
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...


class AnthropicVisionProvider(VisionProvider):
    """Claude vision implementation."""

    MAX_SIDE = 1568  # API tiling sweet spot; larger costs more and adds nothing.

    def __init__(self, api_key: str, model: str):
        from anthropic import Anthropic
        self._client = Anthropic(api_key=api_key)
        self._model = model

    def _prepare(self, image_bytes: bytes, media_type: str):
        """Downscale to MAX_SIDE and re-encode (JPEG for photos-like content)."""
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        w, h = img.size
        scale = self.MAX_SIDE / max(w, h)
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)))
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue(), "image/png"

    def describe(self, image_bytes, media_type, kind, context=None):
        data, mt = self._prepare(image_bytes, media_type)
        ctx_lines = ""
        if context:
            bits = [f"{k}: {v}" for k, v in context.items() if v]
            if bits:
                ctx_lines = ("\nKnown context (for grounding only — do not invent "
                             "beyond the image): " + "; ".join(bits))
        instructions = _KIND_INSTRUCTIONS.get(kind, _KIND_INSTRUCTIONS["figure"])
        prompt = (f"{instructions}{ctx_lines}\n\n{_COMPONENT_RULES}\n\n"
                  "Call record_figure with the structured result.")

        resp = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            tools=[_FIGURE_TOOL],
            tool_choice={"type": "tool", "name": "record_figure"},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image",
                     "source": {"type": "base64", "media_type": mt,
                                "data": base64.b64encode(data).decode()}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        tool_block = next((b for b in resp.content if b.type == "tool_use"), None)
        if tool_block is None:
            raise ValueError(f"Vision returned no tool_use (stop={resp.stop_reason}).")
        parsed = self._normalize(dict(tool_block.input))
        parsed["model"] = self._model
        return parsed

    def extract(self, image_bytes, media_type, prompt, tool_schema, max_tokens=4096):
        """
        Generic structured vision call: run `prompt` against the image and force
        the caller-supplied `tool_schema`, returning the tool input dict. The
        PROMPT and SCHEMA are owned by the caller — this keeps domain logic (and
        the gold-blind discovery prompts) out of the provider, while the vendor
        SDK stays inside providers/ per architecture rule #1.
        """
        data, mt = self._prepare(image_bytes, media_type)
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            tools=[tool_schema],
            tool_choice={"type": "tool", "name": tool_schema["name"]},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image",
                     "source": {"type": "base64", "media_type": mt,
                                "data": base64.b64encode(data).decode()}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        tool_block = next((b for b in resp.content if b.type == "tool_use"), None)
        if tool_block is None:
            raise ValueError(f"Vision returned no tool_use (stop={resp.stop_reason}).")
        out = dict(tool_block.input)
        out["_model"] = self._model
        return out

    @staticmethod
    def _normalize(obj: Dict[str, Any]) -> Dict[str, Any]:
        """Validate/clamp the structured tool input (already valid JSON via the SDK)."""
        obj.setdefault("content_type", "figure")
        obj.setdefault("description", "")
        obj.setdefault("transcription", "")
        comps = []
        for c in obj.get("components") or []:
            if not c.get("label"):
                continue
            bbox = c.get("bbox")
            if bbox is not None:
                try:
                    bbox = [max(0.0, min(1.0, float(v))) for v in bbox][:4]
                    if len(bbox) != 4 or bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
                        bbox = None
                except (TypeError, ValueError):
                    bbox = None
            comps.append({
                "label": str(c["label"]),
                "bbox": bbox,
                "confidence": c.get("confidence", "low"),
                "note": c.get("note", ""),
            })
        obj["components"] = comps
        return obj

    @property
    def model_name(self) -> str:
        return self._model


def get_vision_provider() -> VisionProvider:
    """Factory: read env, return configured provider."""
    provider = os.getenv("VISION_PROVIDER", "anthropic").lower()
    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set in .env")
        model = os.getenv("VISION_MODEL", "claude-sonnet-4-6")
        return AnthropicVisionProvider(api_key=api_key, model=model)
    raise NotImplementedError(f"VISION_PROVIDER='{provider}' not implemented.")
