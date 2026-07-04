"""
SFI classification — folder path → metadata.

Logic from the proven Drive walker classifier on the SWS 108 library.
Folder path → SFI section → category → priority.

Returns a dict suitable for direct merge into Chroma chunk metadata.
Empty/None values are omitted (Chroma metadata cannot store None).
"""
from __future__ import annotations

import re
from pathlib import Path

SFI_MAP = {
    "001": "001 General Condition",
    "100": "100 Structure / Hull",
    "200": "200 Deck",
    "300": "300 Interiors",
    "400": "400 Propulsion / Machinery",
    "500": "500 Systems",
    "600": "600 Electrical",
    "700": "700 Nav / Comm / Entertainment",
    "800": "800 Rigging / Sailing",
    "900": "900 Miscellaneous",
}


def detect_sfi(folder_path: str) -> str:
    p = folder_path
    for code in SFI_MAP:
        if f"/{code}, " in p or p.startswith(f"{code}, "):
            return code
    matches = re.findall(r'/([0-9]{3})\b', p) + re.findall(r'^([0-9]{3})\b', p)
    for m in matches:
        n = int(m)
        if 100 <= n < 200: return "100"
        if 200 <= n < 300: return "200"
        if 300 <= n < 400: return "300"
        if 400 <= n < 500: return "400"
        if 500 <= n < 600: return "500"
        if 600 <= n < 700: return "600"
        if 700 <= n < 800: return "700"
        if 800 <= n < 900: return "800"
        if 900 <= n: return "900"
    pl = p.lower()
    if any(k in pl for k in ['bae', 'mastervolt', 'akasol', 'barthelme',
                              'dinnteco', 'tecnoseal', 'marinelec', 'onyx',
                              'firepro']):
        return "600"
    if any(k in pl for k in ['cummins', 'hundested', 'vulkan', 'propeller']):
        return "400"
    if any(k in pl for k in ['watermaker', 'hem', 'greywater', 'bilge',
                              'aircon', 'termodinamica', 'grundfos', 'fire',
                              'sea-fire', 'frigomar', 'bowman']):
        return "500"
    if any(k in pl for k in ['hall spars', 'bamar', 'doyle', 'rigging',
                              'furler', 'harken', 'sail', 'mast']):
        return "800"
    if any(k in pl for k in ['furuno', 'navnet', 'sonance', 'autopilot',
                              'ocean signal', 'pixel sur mer']):
        return "700"
    if any(k in pl for k in ['lofrans', 'windlass', 'ketten', 'manson',
                              'window']):
        return "200"
    if any(k in pl for k in ['miele', 'interior']):
        return "300"
    if any(k in pl for k in ['survitec', 'life raft', 'bauer', 'medical',
                              'safety']):
        return "900"
    return ""


CATEGORY_PATTERNS = [
    (r"\bmanual\b|user.?guide|owner|operating|operations?\b|\bom-|setup", "Manual"),
    (r"schematic|wiring|layout|p[\&\s]?id|\bGA\b|general arrangement", "Schematic"),
    (r"drawing|render|3D|sketch|blueprint", "Drawing"),
    (r"spec(ification)?|tech(nical)? (spec|details|package|data)|datasheet|brochure", "Specification"),
    (r"certif|class|MCA|RINA|stability|approved|compliance|booklet", "Cert/Class"),
    (r"inventory|spare|parts list", "Inventory/Spares"),
    (r"service|maintenance|bulletin|service.?letter|investigation|report|fault|fix", "Service/Maint"),
    (r"acceptance|trial|test|megger|calibration|recording|regen|motoring", "Acceptance/Test"),
    (r"upholstery|paint|varnish|canvas|cover|fabric|finish", "Finish/Trim"),
    (r"sail|spinnaker|jib|main|staysail|code\s?0|deflector|squaretop|pinhead", "Sail/Rig"),
    (r"alarm|fire detect|monitoring|sensor", "Alarm/Monitor"),
    (r"licence|license|backup|polar|deviation|settings?", "Configuration"),
    (r"diagram|graph|flow", "Diagram"),
]


def detect_category(name: str, path: str) -> str:
    text = (name + " " + path).lower()
    for pat, cat in CATEGORY_PATTERNS:
        if re.search(pat, text):
            return cat
    return "Other"


CRITICAL_KEYWORDS = re.compile(
    r'\b(bae|propulsion|schematic|wiring|manual|class|stability|compliance|'
    r'keel|rudder|steering|fire|battery|generator|hybrigen|cpp|thruster|'
    r'hv\b|low voltage|engine|hydraulic|investigation|fault.?isolation)\b',
    re.I)


def detect_priority(name: str, path: str, category: str) -> str:
    text = name + " " + path
    if CRITICAL_KEYWORDS.search(text):
        return "Critical"
    if category in ("Manual", "Schematic", "Cert/Class", "Specification", "Drawing"):
        return "Critical"
    if category in ("Service/Maint", "Inventory/Spares", "Alarm/Monitor", "Acceptance/Test"):
        return "Important"
    return "Normal"


def extract_metadata(file_path: Path) -> dict:
    """Public entry point. Returns dict with sfi_section, sfi_label,
    category, priority. Omits keys when empty (Chroma metadata cannot
    store None)."""
    folder_path = str(file_path.parent)
    name = file_path.name
    sfi = detect_sfi(folder_path)
    cat = detect_category(name, folder_path)
    pri = detect_priority(name, folder_path, cat)
    result = {}
    if sfi:
        result["sfi_section"] = sfi
        result["sfi_label"] = SFI_MAP.get(sfi, "")
    if cat and cat != "Other":
        result["category"] = cat
    if pri:
        result["priority"] = pri
    return result
