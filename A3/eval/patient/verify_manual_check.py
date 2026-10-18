"""Độc lập với api/patient: đọc lại C-CDA và so với eval/patient/manual_check.csv.
Chạy: uv run python -I verify_manual_check.py eval/patient/manual_check.csv [repo_root]
In ra từng bệnh nhân: mục có trong file gốc nhưng thiếu ở đáp án (MISSING) và ngược lại (EXTRA).
"""
import csv, sys, re, pathlib
from lxml import etree

NS = {"c": "urn:hl7-org:v3"}
SEC = {"allergy": "48765-2", "med": "10160-0", "problem": "11450-4"}


def sec(t, code):
    for s in t.iterfind(".//c:section", NS):
        c = s.find("c:code", NS)
        if c is not None and c.get("code") == code:
            return s


def ts(v):
    return (v or "")[:8]


def parse(path):
    t = etree.parse(open(path, "rb"))
    now = ts(t.getroot().find("c:effectiveTime", NS).get("value"))
    out = {"allergy": {}, "problem": {}, "med": {}, "_raw": {}}
    s = sec(t, SEC["allergy"])
    for act in (s.iterfind("c:entry/c:act", NS) if s is not None else []):
        ob = act.find(".//c:observation", NS)
        typ = ob.find("c:value", NS).get("code")
        pe = ob.find(".//c:playingEntity/c:code", NS)
        active = act.find("c:statusCode", NS).get("code") == "active" and act.find("c:effectiveTime/c:high", NS) is None
        if active and typ == "414285001":
            out["allergy"][pe.get("code")] = pe.get("displayName")
    s = sec(t, SEC["problem"])
    for act in (s.iterfind("c:entry/c:act", NS) if s is not None else []):
        v = act.find(".//c:observation/c:value", NS)
        hi = act.find("c:effectiveTime/c:high", NS)
        active = act.find("c:statusCode", NS).get("code") == "active" and hi is None
        name = v.get("displayName") or ""
        out["_raw"].setdefault("problem", []).append((name, v.get("code"), active))
        if active and name.endswith("(disorder)"):
            out["problem"][v.get("code")] = name
    s = sec(t, SEC["med"])
    for sa in (s.iterfind("c:entry/c:substanceAdministration", NS) if s is not None else []):
        highs = sa.findall("c:effectiveTime/c:high", NS)
        h = highs[0] if highs else None
        active = h is None or h.get("nullFlavor") == "UNK" or (h.get("value") and ts(h.get("value")) >= now)
        m = sa.find(".//c:manufacturedMaterial/c:code", NS)
        low = sa.find("c:effectiveTime/c:low", NS)
        out["_raw"].setdefault("med", []).append((m.get("displayName"), m.get("code"), active,
                                                  ts(low.get("value")) if low is not None else "", h.get("value") if h is not None and h.get("value") else (h.get("nullFlavor") if h is not None else None)))
        if active:
            out["med"][m.get("code")] = m.get("displayName")
    return out


def codes(cell):
    return set(re.findall(r"\((\d+)\)\s*(?:;|$)", cell or ""))


def main():
    csv_path = pathlib.Path(sys.argv[1])
    root = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path(".")
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    for r in rows:
        f = root / r["file"]
        print("=" * 80, "\n", r["patient_id"], r["source"], f.name)
        if not f.exists():
            print("  !! không thấy file"); continue
        g = parse(f)
        for key, col in [("allergy", "food_allergies_key"), ("problem", "conditions_key"), ("med", "medications_key")]:
            want, got = set(g[key]), codes(r[col])
            ok = want == got
            print(f"  {key:8s} {'OK ' if ok else 'DIFF'}  file={len(want)} key={len(got)}")
            for c in sorted(want - got): print(f"     MISSING in key: {g[key][c]} ({c})")
            for c in sorted(got - want): print(f"     EXTRA  in key: ({c})")
        # gợi ý để soát tay
        dm = [p for p in g["_raw"].get("problem", []) if "diabetes" in p[0].lower() or "prediabetes" in p[0].lower()]
        if dm: print("  diabetes-related problems (name, code, active):", dm)
        meds = [m for m in g["_raw"].get("med", []) if m[2]]
        once = [m for m in meds if any(w in m[0].lower() for w in ["alteplase", "injection", "vaccine"])]
        if once: print("  active meds that look one-off (name, code, active, low, high):", once)


if __name__ == "__main__":
    main()
