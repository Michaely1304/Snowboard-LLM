import re

TERRAIN_MAP = {
    "all mountain": "All_Mountain",
    "all-mountain": "All_Mountain",
    "allmountain": "All_Mountain",
    "park": "Park",
    "pow": "Powder",
    "powder": "Powder",
    "carving": "Carving",
    "split": "Splitboard",
    "splitboard": "Splitboard",
}

POSITIVE_KWS = {
    "edge hold": ["edge hold","ice","hardpack","magnetraction","traction"],
    "float": ["float","powder","rocker nose","taper"],
    "pop": ["pop","snappy","lively","camber"],
    "stability": ["stable","damp","chatter","vibration","directional flex"],
    "butterability": ["butter","press","playful","soft flex"],
    "carving": ["carve","sidecut","trench","radius","torsional"],
}

def clean_text(t: str) -> str:
    if not t: return ""
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:1500]

def parse_terrain_blob(s: str) -> dict:
    d = {v:0 for v in ["Park","All_Mountain","Powder","Carving","Splitboard"]}
    if not s: return d
    # split by separators and find "name number"
    parts = re.split(r'[;,/|]+', s.lower())
    for p in parts:
        m = re.search(r'([a-z\-\s]+?)\s*([0-9]{1,2})(?!\S)', p.strip())
        if m:
            name, score = m.group(1).strip(), int(m.group(2))
            key = TERRAIN_MAP.get(name.replace("  "," ").strip())
            if key:
                d[key] = max(d[key], min(score,10))
    # Heuristics: if the blob uses adjectives (e.g., "carving focus"), map to 7
    if not any(d.values()):
        for name, key in [("park","Park"),("all mountain","All_Mountain"),
                          ("powder","Powder"),("carving","Carving"),
                          ("splitboard","Splitboard")]:
            if name in s.lower():
                d[key] = max(d[key], 7)
    return d

def extract_key_features(text: str) -> list:
    tl = (text or "").lower()
    found = []
    for tag, kws in POSITIVE_KWS.items():
        if any(kw in tl for kw in kws):
            found.append(tag)
    return found

def summarize_desc(text: str) -> str:
    if not text: return ""
    s = clean_text(text)
    # first sentence + highlights
    m = re.split(r'(?<=[.!?])\s+', s)
    lead = m[0] if m else s[:200]
    feats = extract_key_features(text)
    extra = f" Highlights: {', '.join(feats)}." if feats else ""
    out = (lead[:250] + ("..." if len(lead) > 250 else "")) + extra
    return out

def rationale_hint(profile: str, flex: int, t: dict) -> str:
    bits = []
    try:
        flex_val = int(flex)
    except Exception:
        flex_val = None
    if t.get("All_Mountain",0) >= 8: bits.append("versatile all-mountain performance")
    if t.get("Carving",0) >= 7 and str(profile).lower().startswith("camber"):
        bits.append("strong edge hold and response on groomers")
    if t.get("Powder",0) >= 6: bits.append("better float on deeper days")
    if t.get("Park",0) >= 6: bits.append("playful feel for park features")
    if flex_val is not None:
        if flex_val >= 7: bits.append("more stability at speed")
        elif flex_val <= 4: bits.append("more forgiveness for progression")
    if not bits: bits.append("balanced ride characteristics")
    return " ; ".join(bits)

def normalize_row(row: dict) -> dict:
    # Ensure required keys
    out = {k: row.get(k, "") for k in
           ["Brand","Name","Gender","Profile","Flex",
            "Description_raw","Source_url","Terrain_blob"]}
    t = parse_terrain_blob(out.get("Terrain_blob",""))
    out.update({
        "Park": t["Park"],
        "All_Mountain": t["All_Mountain"],
        "Powder": t["Powder"],
        "Carving": t["Carving"],
        "Splitboard": t["Splitboard"],
    })
    out["Description_raw"] = clean_text(out.get("Description_raw",""))
    feats = extract_key_features(out["Description_raw"])
    out["Key_features"] = ", ".join(feats)
    out["Desc_summary"] = summarize_desc(out["Description_raw"])
    out["Rationale_hint"] = rationale_hint(out.get("Profile",""), out.get("Flex",""), t)
    # Coerce types
    try: out["Flex"] = int(str(out.get("Flex","")).strip() or 0)
    except: out["Flex"] = 0
    return out
