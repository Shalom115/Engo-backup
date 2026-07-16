"""
Local web chat for Engo — a thin HTTP layer over agent.loop.query().

Zero new dependencies (stdlib http.server). Serves a single-page chat UI
and two JSON endpoints:

    GET  /                       -> comms/webchat.html
    GET  /api/history?cid=<id>   -> saved conversation turns (for page reload)
    POST /api/query              -> {"question": str, "conversation_id": str}
                                    runs the real agent loop, returns its dict

The agent path is EXACTLY the CLI path — same query(), same retrieval, same
conversation memory files under data/state/conversations/. No shortcut.

Run:  python3.12 -m comms.webchat            (http://127.0.0.1:8765)
      python3.12 -m comms.webchat --host 0.0.0.0 --port 8765   (crew LAN)
"""

from __future__ import annotations

import argparse
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse

from agent.loop import query
from agent.conversation import conversation_path

logger = logging.getLogger("engo.webchat")

_HTML_PATH = Path(__file__).parent / "webchat.html"


def _history(conversation_id: str) -> List[Dict[str, Any]]:
    """Verbatim turns of a saved conversation (empty list if none yet)."""
    path = conversation_path(conversation_id)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        {"question": t["question"], "answer": t["answer"],
         "turn_index": t["turn_index"]}
        for t in data.get("turns", [])
    ]


def _conversations() -> List[Dict[str, Any]]:
    """All saved conversations, newest first: id, updated_at, first question."""
    conv_dir = conversation_path("x").parent
    out: List[Dict[str, Any]] = []
    if not conv_dir.exists():
        return out
    for p in conv_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            turns = data.get("turns", [])
            title = turns[0]["question"] if turns else "(empty)"
            out.append({
                "id": data.get("conversation_id", p.stem),
                "updated_at": data.get("updated_at", ""),
                "title": title[:80],
                "n_turns": data.get("turns_compressed", 0) + len(turns),
            })
        except (ValueError, KeyError, json.JSONDecodeError):
            continue  # corrupt file: skip in the list, fail loud on open
    out.sort(key=lambda c: c["updated_at"], reverse=True)
    return out


class _Handler(BaseHTTPRequestHandler):
    """One request handler; the LLM call is synchronous per request."""

    def _send_json(self, obj: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            body = _HTML_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/api/conversations":
            self._send_json({"conversations": _conversations()})
        elif parsed.path == "/api/history":
            cid = parse_qs(parsed.query).get("cid", [""])[0].strip()
            if not cid:
                self._send_json({"error": "missing cid"}, 400)
                return
            try:
                self._send_json({"turns": _history(cid)})
            except (ValueError, json.JSONDecodeError) as e:
                self._send_json({"error": f"corrupt conversation: {e}"}, 500)
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/query":
            self._send_json({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            question = str(payload.get("question", "")).strip()
            cid = str(payload.get("conversation_id", "")).strip() or None
            if not question:
                self._send_json({"error": "empty question"}, 400)
                return
            result = query(question, conversation_id=cid)
            self._send_json(result)
        except Exception as e:  # fail loud to the page, never a fake answer
            logger.exception("query failed")
            self._send_json({"error": f"{type(e).__name__}: {e}"}, 500)

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.info("%s %s", self.address_string(), fmt % args)


def main() -> None:
    """Start the chat server (blocking)."""
    p = argparse.ArgumentParser(description="Engo local web chat")
    p.add_argument("--host", default="127.0.0.1",
                   help="bind address (0.0.0.0 for crew LAN)")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    server = ThreadingHTTPServer((args.host, args.port), _Handler)
    print(f"Engo chat: http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
