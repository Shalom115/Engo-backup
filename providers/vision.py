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
import logging
import os
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger("providers.vision")

# Bounded retry for TRANSIENT API failures (rate limit, overloaded, connection
# drop, 5xx). One transient error must never kill a long paid extraction run —
# the Gold #2 lesson (a one-shot network call crashed the whole run), fixed at
# the PROVIDER so every caller is covered. Permanent errors (4xx bad request)
# are NOT retried — they fail loud immediately.
_RETRY_ATTEMPTS = 4
_RETRY_BACKOFF = (2.0, 5.0, 15.0)  # seconds between attempts


def _is_transient_api_error(exc: Exception) -> bool:
    """True for rate-limit / overloaded / connection / server-side errors."""
    import anthropic
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError,
                        anthropic.RateLimitError)):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        # 429 rate limit, 5xx server errors, 529 overloaded
        return exc.status_code == 429 or exc.status_code >= 500
    return False


def _call_with_retry(fn, *args, **kwargs):
    """Run an API call with bounded retry on transient errors only."""
    last_exc: Exception | None = None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if not _is_transient_api_error(e):
                raise
            last_exc = e
            if attempt < _RETRY_ATTEMPTS - 1:
                backoff = _RETRY_BACKOFF[min(attempt, len(_RETRY_BACKOFF) - 1)]
                logger.warning("Transient vision-API error (attempt %d/%d): %s — "
                               "retrying in %.0fs", attempt + 1, _RETRY_ATTEMPTS, e, backoff)
                time.sleep(backoff)
    assert last_exc is not None
    raise last_exc


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
    """Abstract vision interface.

    All three read methods are part of the CONTRACT (formalized 2026-07-12 —
    pipeline extractors were already calling extract/extract_multi on the
    concrete class; a provider swap must fail at the interface, not deep in a
    paid run). Prompts and tool schemas are ALWAYS caller-owned: domain logic
    and the gold-blind discovery prompts live in pipeline/, never here.
    """

    #: Longest image edge (px) this provider accepts before downscaling.
    #: Pipeline tiling math derives crop footprints from this — never hardcode.
    max_side: int = 1568

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

    @abstractmethod
    def extract(self, image_bytes: bytes, media_type: str, prompt: str,
                tool_schema: Dict[str, Any], max_tokens: int = 4096) -> Dict[str, Any]:
        """Generic structured vision call: run caller-owned `prompt` against the
        image and return a dict matching the caller-owned `tool_schema`."""
        ...

    @abstractmethod
    def extract_multi(self, images, prompt: str, tool_schema: Dict[str, Any],
                      max_tokens: int = 4096) -> Dict[str, Any]:
        """Like extract() but with MULTIPLE ordered (image_bytes, media_type)
        pairs in one call, so the model can cross-reference them (tight crop +
        downsampled full sheet)."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...


# Claude models with high-resolution vision (2576px long edge, pixel-accurate
# coordinates — Opus 4.7+ / Sonnet 5 / Fable 5). Older models cap at 1568px,
# which is the constraint the §4 crop-footprint tiling was designed around.
_CLAUDE_HIGHRES_PREFIXES = ("claude-opus-4-7", "claude-opus-4-8",
                            "claude-sonnet-5", "claude-fable-5", "claude-mythos-5")


class AnthropicVisionProvider(VisionProvider):
    """Claude vision implementation."""

    MAX_SIDE = 1568  # legacy alias; instance max_side (model-dependent) is authoritative.

    def __init__(self, api_key: str, model: str):
        from anthropic import Anthropic
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self.max_side = (2576 if model.startswith(_CLAUDE_HIGHRES_PREFIXES) else 1568)

    def _prepare(self, image_bytes: bytes, media_type: str):
        """Downscale to max_side and re-encode (JPEG for photos-like content)."""
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        w, h = img.size
        scale = self.max_side / max(w, h)
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

        resp = _call_with_retry(
            self._client.messages.create,
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
        resp = _call_with_retry(
            self._client.messages.create,
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

    def extract_multi(self, images, prompt, tool_schema, max_tokens=4096):
        """
        Like extract(), but sends MULTIPLE images in one call so the model can
        CROSS-REFERENCE them. `images` is an ordered list of (image_bytes,
        media_type) — the prompt is responsible for saying what each image is
        (e.g. "IMAGE 1 = full sheet for context, IMAGE 2 = detail crop"). Used
        by the electrical/schematic readers to give a tight high-res crop AND a
        downsampled full-page overview together, so an element ambiguous in the
        crop is resolved by what it connects to on the full sheet.
        """
        content = []
        for i, (img_bytes, mt_in) in enumerate(images, 1):
            data, mt = self._prepare(img_bytes, mt_in)
            content.append({"type": "text", "text": f"IMAGE {i}:"})
            content.append({"type": "image",
                            "source": {"type": "base64", "media_type": mt,
                                       "data": base64.b64encode(data).decode()}})
        content.append({"type": "text", "text": prompt})
        resp = _call_with_retry(
            self._client.messages.create,
            model=self._model,
            max_tokens=max_tokens,
            tools=[tool_schema],
            tool_choice={"type": "tool", "name": tool_schema["name"]},
            messages=[{"role": "user", "content": content}],
        )
        tool_block = next((b for b in resp.content if b.type == "tool_use"), None)
        if tool_block is None:
            raise ValueError(f"Vision returned no tool_use (stop={resp.stop_reason}).")
        out = dict(tool_block.input)
        out["_model"] = self._model
        return out

    @staticmethod
    def _normalize(obj: Dict[str, Any]) -> Dict[str, Any]:
        return _normalize_figure(obj)

    @property
    def model_name(self) -> str:
        return self._model


def _normalize_figure(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Validate/clamp a record_figure-shaped dict (shared across providers)."""
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


def _downscale(image_bytes: bytes, max_side: int):
    """Downscale to max_side and re-encode PNG (shared across providers)."""
    from PIL import Image
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    w, h = img.size
    scale = max_side / max(w, h)
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue(), "image/png"


def _retry_generic(fn, is_transient):
    """Bounded retry on transient errors, vendor-agnostic (same policy as
    _call_with_retry; the predicate is per-vendor)."""
    last_exc: Exception | None = None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            return fn()
        except Exception as e:
            if not is_transient(e):
                raise
            last_exc = e
            if attempt < _RETRY_ATTEMPTS - 1:
                backoff = _RETRY_BACKOFF[min(attempt, len(_RETRY_BACKOFF) - 1)]
                logger.warning("Transient vision-API error (attempt %d/%d): %s — "
                               "retrying in %.0fs", attempt + 1, _RETRY_ATTEMPTS, e, backoff)
                time.sleep(backoff)
    assert last_exc is not None
    raise last_exc


class GeminiVisionProvider(VisionProvider):
    """
    Google Gemini vision implementation (google-genai SDK). Same contract as
    the Anthropic provider: caller-owned prompts + tool schemas, structured
    JSON back. Structured output rides Gemini's response_schema (the caller's
    input_schema, with JSON-Schema keys Gemini doesn't support stripped).

    Env: GEMINI_API_KEY (or GOOGLE_API_KEY); GEMINI_VISION_MODEL overrides the
    default model id — if Google renames models, fix it there, not in code.
    """

    max_side = 3072  # Gemini tiles internally; larger effective resolution.

    def __init__(self, api_key: str, model: str):
        try:
            from google import genai
        except ImportError as e:
            raise RuntimeError(
                "google-genai not installed. pip install google-genai") from e
        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self._model = model

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        if isinstance(code, int):
            return code == 429 or code >= 500
        return isinstance(exc, (TimeoutError, ConnectionError, OSError))

    @staticmethod
    def _clean_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
        """Strip JSON-Schema keys Gemini's response_schema rejects, recursively."""
        drop = {"additionalProperties", "$schema", "default"}
        def walk(node):
            if isinstance(node, dict):
                return {k: walk(v) for k, v in node.items() if k not in drop}
            if isinstance(node, list):
                return [walk(v) for v in node]
            return node
        return walk(schema)

    def _generate(self, parts: list, schema: Dict[str, Any], max_tokens: int) -> Dict[str, Any]:
        from google.genai import types
        cfg = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=self._clean_schema(schema),
            max_output_tokens=max_tokens,
        )
        resp = _retry_generic(
            lambda: self._client.models.generate_content(
                model=self._model, contents=parts, config=cfg),
            self._is_transient,
        )
        text = resp.text
        if not text:
            raise ValueError(f"Gemini returned no text (model={self._model}).")
        out = json.loads(text)
        if not isinstance(out, dict):
            raise ValueError(f"Gemini returned non-object JSON: {type(out).__name__}")
        return out

    def _image_part(self, image_bytes: bytes, media_type: str):
        from google.genai import types
        data, mt = _downscale(image_bytes, self.max_side)
        return types.Part.from_bytes(data=data, mime_type=mt)

    def describe(self, image_bytes, media_type, kind, context=None):
        ctx_lines = ""
        if context:
            bits = [f"{k}: {v}" for k, v in context.items() if v]
            if bits:
                ctx_lines = ("\nKnown context (for grounding only — do not invent "
                             "beyond the image): " + "; ".join(bits))
        instructions = _KIND_INSTRUCTIONS.get(kind, _KIND_INSTRUCTIONS["figure"])
        prompt = (f"{instructions}{ctx_lines}\n\n{_COMPONENT_RULES}\n\n"
                  "Respond with the structured JSON result.")
        out = self._generate([self._image_part(image_bytes, media_type), prompt],
                             _FIGURE_TOOL["input_schema"], 4096)
        parsed = _normalize_figure(out)
        parsed["model"] = self._model
        return parsed

    def extract(self, image_bytes, media_type, prompt, tool_schema, max_tokens=4096):
        out = self._generate([self._image_part(image_bytes, media_type), prompt],
                             tool_schema["input_schema"], max_tokens)
        out["_model"] = self._model
        return out

    def extract_multi(self, images, prompt, tool_schema, max_tokens=4096):
        parts = []
        for i, (img_bytes, mt_in) in enumerate(images, 1):
            parts.append(f"IMAGE {i}:")
            parts.append(self._image_part(img_bytes, mt_in))
        parts.append(prompt)
        out = self._generate(parts, tool_schema["input_schema"], max_tokens)
        out["_model"] = self._model
        return out

    @property
    def model_name(self) -> str:
        return self._model


class OpenAIVisionProvider(VisionProvider):
    """
    OpenAI GPT vision implementation (openai SDK). Same contract. Structured
    output rides forced function-calling (the caller's tool schema becomes the
    function's parameters — the closest mirror of the Anthropic tool_choice
    mechanism, so no schema rewriting for strict mode is needed).

    Env: OPENAI_API_KEY; OPENAI_VISION_MODEL overrides the default model id.
    """

    max_side = 2048  # OpenAI high-detail input cap.

    def __init__(self, api_key: str, model: str):
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError("openai not installed. pip install openai") from e
        self._client = OpenAI(api_key=api_key)
        self._model = model

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        import openai
        if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError,
                            openai.RateLimitError)):
            return True
        status = getattr(exc, "status_code", None)
        return isinstance(status, int) and (status == 429 or status >= 500)

    def _image_block(self, image_bytes: bytes, media_type: str) -> Dict[str, Any]:
        data, _mt = _downscale(image_bytes, self.max_side)
        b64 = base64.b64encode(data).decode()
        return {"type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}}

    def _call(self, content: list, tool_schema: Dict[str, Any], max_tokens: int) -> Dict[str, Any]:
        tool = {"type": "function",
                "function": {"name": tool_schema["name"],
                             "description": tool_schema.get("description", ""),
                             "parameters": tool_schema["input_schema"]}}
        resp = _retry_generic(
            lambda: self._client.chat.completions.create(
                model=self._model,
                max_completion_tokens=max_tokens,
                tools=[tool],
                tool_choice={"type": "function",
                             "function": {"name": tool_schema["name"]}},
                messages=[{"role": "user", "content": content}],
            ),
            self._is_transient,
        )
        calls = resp.choices[0].message.tool_calls or []
        if not calls:
            raise ValueError(
                f"OpenAI returned no tool call (model={self._model}, "
                f"finish={resp.choices[0].finish_reason}).")
        out = json.loads(calls[0].function.arguments)
        if not isinstance(out, dict):
            raise ValueError(f"OpenAI returned non-object arguments: {type(out).__name__}")
        return out

    def describe(self, image_bytes, media_type, kind, context=None):
        ctx_lines = ""
        if context:
            bits = [f"{k}: {v}" for k, v in context.items() if v]
            if bits:
                ctx_lines = ("\nKnown context (for grounding only — do not invent "
                             "beyond the image): " + "; ".join(bits))
        instructions = _KIND_INSTRUCTIONS.get(kind, _KIND_INSTRUCTIONS["figure"])
        prompt = (f"{instructions}{ctx_lines}\n\n{_COMPONENT_RULES}\n\n"
                  f"Call {_FIGURE_TOOL['name']} with the structured result.")
        content = [self._image_block(image_bytes, media_type),
                   {"type": "text", "text": prompt}]
        parsed = _normalize_figure(self._call(content, _FIGURE_TOOL, 4096))
        parsed["model"] = self._model
        return parsed

    def extract(self, image_bytes, media_type, prompt, tool_schema, max_tokens=4096):
        content = [self._image_block(image_bytes, media_type),
                   {"type": "text", "text": prompt}]
        out = self._call(content, tool_schema, max_tokens)
        out["_model"] = self._model
        return out

    def extract_multi(self, images, prompt, tool_schema, max_tokens=4096):
        content = []
        for i, (img_bytes, mt_in) in enumerate(images, 1):
            content.append({"type": "text", "text": f"IMAGE {i}:"})
            content.append(self._image_block(img_bytes, mt_in))
        content.append({"type": "text", "text": prompt})
        out = self._call(content, tool_schema, max_tokens)
        out["_model"] = self._model
        return out

    @property
    def model_name(self) -> str:
        return self._model


# ---------------------------------------------------------------------------
# Factory + per-drawing-class routing
#
# VISION_ROUTES maps a task class to a vendor, e.g. in .env:
#   VISION_ROUTES=electrical:gemini,hydraulic_schematic:anthropic,pid:openai
# Unrouted classes (and no task_class at all) use VISION_PROVIDER (default
# anthropic). Vendor model ids come from VISION_MODEL / GEMINI_VISION_MODEL /
# OPENAI_VISION_MODEL — model renames are an env edit, never a code edit.
# Routing is set from the engineer-graded benchmark (tests/vision_bench.py),
# never from vibes.
# ---------------------------------------------------------------------------

_PROVIDER_CACHE: Dict[str, VisionProvider] = {}


def _make_provider(vendor: str) -> VisionProvider:
    vendor = vendor.lower().strip()
    if vendor in _PROVIDER_CACHE:
        return _PROVIDER_CACHE[vendor]
    if vendor == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set in .env")
        model = os.getenv("VISION_MODEL", "claude-sonnet-5")
        p: VisionProvider = AnthropicVisionProvider(api_key=api_key, model=model)
    elif vendor == "gemini":
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) not set in .env")
        model = os.getenv("GEMINI_VISION_MODEL", "gemini-3-pro")
        p = GeminiVisionProvider(api_key=api_key, model=model)
    elif vendor == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set in .env")
        model = os.getenv("OPENAI_VISION_MODEL", "gpt-5.2")
        p = OpenAIVisionProvider(api_key=api_key, model=model)
    else:
        raise NotImplementedError(f"vision vendor '{vendor}' not implemented "
                                  f"(anthropic | gemini | openai).")
    _PROVIDER_CACHE[vendor] = p
    return p


def _routes() -> Dict[str, str]:
    raw = os.getenv("VISION_ROUTES", "")
    routes: Dict[str, str] = {}
    for pair in raw.split(","):
        if ":" in pair:
            k, v = pair.split(":", 1)
            routes[k.strip().lower()] = v.strip().lower()
    return routes


def get_vision_provider(task_class: Optional[str] = None) -> VisionProvider:
    """
    Factory: return the vision provider for a drawing/task class.

    task_class (optional): e.g. "hydraulic_schematic", "electrical", "pid",
    "ga", "plc", "photo". Looked up in VISION_ROUTES; unrouted classes fall
    back to the VISION_PROVIDER default. Callers that don't know their class
    call with no argument and get the default — fully backward compatible.
    """
    default_vendor = os.getenv("VISION_PROVIDER", "anthropic")
    vendor = default_vendor
    if task_class:
        vendor = _routes().get(task_class.lower(), default_vendor)
    return _make_provider(vendor)
