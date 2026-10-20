"""V3: the fixed nodes of a patient tree -> PatientProfile, by the rule tables (spec 4, 5.5). Pure: no model, no I/O.

- Food allergies (kind 414285001) -> allergen groups and extra ingredients (allergy_substance.csv); a food
  substance with no rule is `unmapped`, never silently dropped.
- Conditions in problems.active, plus the rules for every patient ("*") -> per-serving nutrient limits
  (condition_nutrient.csv, api/patient/nutrition.py). `filter` rules are hard limits; `soft` rules (those that
  would leave under half of the Recipes, ADR-0007) become preferences for ranking plus a warning. Per nutrient
  and per kind the strictest limit wins; the evidence
  keeps every rule that named it (an overridden one too). Opposite rules on one nutrient -> no filter, a warning.
  A per-kg limit needs a weight measured within WEIGHT_MAX_AGE_DAYS of the record date, else it is a warning.
- The Dietary Rule Engine (dietary_rules.py, dietary_rules.json) adds hard per-serving limits for the same
  conditions. Where the CSV rules already limit the column the stricter one wins, and its evidence is added to the
  CSV rules' (docs/adr/0009). Soft rules, warnings and ratio nutrients stay with the CSV tables.
- Medications in meds.active -> excluded ingredients or warnings (drug_food.csv, substring of the RxNorm name).
"""

import re
from collections import defaultdict
from datetime import date

from .. import config
from . import dietary_rules, nutrition
from .models import Evidence, PatientNode, PatientProfile, constraint_ids
from .rules import NUTRIENT_COLUMN, RuleSet

FOOD_ALLERGY = "414285001"
WEIGHT_LOINC = "29463-7"
WEIGHT_MAX_AGE_DAYS = 730  # spec 4.4.3: older than 2 years -> warn
_TAG = re.compile(r"\s*\((finding|disorder|situation|substance|morphologic abnormality)\)\s*$")

WARN_TEXT = {  # Vietnamese warnings for rules in warn mode (shown to the user, cite their evidence)
    "sugar_pct_kcal": "Nên ưu tiên món ít đường (đường dưới 10% năng lượng, WHO).",
    "potassium_mg": "Lưu ý lượng kali trong món (bệnh thận mạn).",
    "phosphorus_mg": "Lưu ý lượng phospho trong món (bệnh thận mạn); dữ liệu công thức không có số liệu phospho.",
}
SOFT_TEXT = {  # shown once per soft rule; M5 ranks Recipes that meet it first (MV3)
    "sat_fat_pct_kcal": "Ưu tiên món ít chất béo bão hòa (dưới 6% năng lượng, DASH).",
    "fiber_per_1000kcal": "Ưu tiên món nhiều chất xơ (từ 14 g mỗi 1.000 kcal, ADA).",
}
NUTRIENT_VI = {"sodium_mg": "natri", "sat_fat_pct_kcal": "chất béo bão hòa", "fiber_per_1000kcal": "chất xơ",
               "protein_g_per_kg": "đạm", "sugar_pct_kcal": "đường", "potassium_mg": "kali", "phosphorus_mg": "phospho"}


def _short(display: str | None) -> str:
    return _TAG.sub("", display or "?").strip()


def _facts(nodes: list[PatientNode], node_id: str) -> list[dict]:
    return next((n.facts for n in nodes if n.node_id == node_id), [])


def _root(nodes: list[PatientNode]) -> str:
    return next((n.node_id for n in nodes if n.kind == "root"), "patient")


def _weight(nodes: list[PatientNode], record_date: date) -> tuple[float | None, dict | None]:
    for f in _facts(nodes, "vitals.latest"):
        if f.get("loinc") == WEIGHT_LOINC and f.get("value") and f.get("date"):
            if (record_date - date.fromisoformat(f["date"])).days <= WEIGHT_MAX_AGE_DAYS:
                return float(f["value"]), f
            return None, f  # present but too old
    return None, None


def build_profile(nodes: list[PatientNode], rs: RuleSet, record_date: date, mode: str = "vectorless",
                  patient_id: str | None = None) -> PatientProfile:
    root = _root(nodes)
    pid = patient_id or root.removeprefix("patient:")
    allergens, ingredients = set(), set()
    limits: dict[str, tuple[str, float]] = {}
    soft: dict[str, tuple[str, float]] = {}
    warnings: list[str] = []
    unmapped: list[str] = []
    evidence: dict[str, list[Evidence]] = defaultdict(list)

    # ---- food allergies -------------------------------------------------------------------------------------
    for f in _facts(nodes, "allergies"):
        if f.get("kind_code") != FOOD_ALLERGY:
            continue
        reactions = ", ".join(_short(r) for r in f.get("reactions") or [])
        text = " – ".join(x for x in [_short(f.get("substance")), ", ".join(
            x for x in [reactions, f.get("severity") or ""] if x)] if x)
        ev = Evidence("allergies", f.get("entry_id") or "", text)
        rule = rs.allergy.get(f.get("substance_code") or "")
        if rule is None or not (rule.allergens or rule.extra_ingredients):
            unmapped.append(f"allergy:{f.get('substance_code')} {f.get('substance')}")
            continue
        for a in rule.allergens:
            allergens.add(a)
            evidence[f"allergen:{a}"].append(ev)
        for name in rule.extra_ingredients:
            ingredients.add(name)
            evidence[f"ingredient:{name}"].append(ev)

    # ---- conditions -> nutrient limits ----------------------------------------------------------------------
    problems = {f.get("code"): f for f in _facts(nodes, "problems.active")}
    triggered = []  # (rule, evidence)
    for r in rs.nutrient:
        if r.conditions == ("*",):
            triggered.append((r, Evidence(root, "", f"Mọi bệnh nhân – {r.source}")))
            continue
        for code in r.conditions:
            if code in problems:
                p = problems[code]
                if r.mode == "unmapped":
                    unmapped.append(f"condition:{code} {_short(p.get('display'))}")
                else:
                    triggered.append((r, Evidence("problems.active", p.get("entry_id") or "",
                                                  f"{_short(p.get('display'))} – {r.source}")))
                break
    unmapped = list(dict.fromkeys(unmapped))

    weight, weight_fact = _weight(nodes, record_date)
    by_nutrient: dict[str, list] = defaultdict(list)
    for r, ev in triggered:
        by_nutrient[r.nutrient].append((r, ev))
    for nutrient, group in by_nutrient.items():
        for r, ev in group:
            if r.mode == "warn" and WARN_TEXT.get(nutrient) not in warnings:
                warnings.append(WARN_TEXT.get(nutrient, f"Lưu ý {NUTRIENT_VI.get(nutrient, nutrient)}."))
                evidence[f"warning:{nutrient}"].append(ev)
        for kind, target, key in (("filter", limits, "nutrient"), ("soft", soft, "soft")):
            rows = [(r, ev) for r, ev in group if r.mode == kind]
            if rows:
                _limit(nutrient, rows, target, key, weight, weight_fact, warnings, evidence)
                if kind == "soft" and SOFT_TEXT.get(nutrient) and SOFT_TEXT[nutrient] not in warnings:
                    warnings.append(SOFT_TEXT[nutrient])

    if rs.diet is not None:
        _diet_limits(nodes, rs.diet, pid, problems, limits, warnings, evidence)

    # ---- medications ----------------------------------------------------------------------------------------
    for f in _facts(nodes, "meds.active"):
        name = (f.get("display") or "").lower()
        for d in rs.drug:
            if d.match not in name:
                continue
            ev = Evidence("meds.active", f.get("entry_id") or "", f"{f.get('display')} – {d.message_vi}")
            if d.action == "exclude":
                for t in d.targets:
                    ingredients.add(t)
                    evidence[f"ingredient:{t}"].append(ev)
            elif d.message_vi not in warnings:
                warnings.append(d.message_vi)
                evidence[f"warning:drug:{d.match}"].append(ev)

    return PatientProfile(pid, frozenset(allergens), frozenset(ingredients), limits, warnings, unmapped,
                          dict(evidence), rs.version, mode, soft)


def _diet_limits(nodes, book, pid, problems, limits, warnings, evidence):
    """The Dietary Rule Engine's filters into `limits`: the stricter of its value and the CSV's wins, and its evidence
    sits beside the CSV rules' (an overridden one too). What the engine cannot filter (saturated fat in g, gout) stays
    in its own plan, GET /patients/{id}/diet-plan; the CSV already covers saturated fat as a share of energy."""
    plan = dietary_rules.derive_diet_plan(dietary_rules.profile_from_nodes(pid, nodes), book,
                                          dietary_rules.filterable_nutrients(), config.MEALS_PER_DAY)
    for key, value in plan.filters.items():
        column = key.removeprefix("max_")
        # the evidence text names the rule and its review status; the full source is in dietary_rules.json and /diet-plan
        ev = [Evidence("problems.active", problems[c.code].get("entry_id") or "",
                       f"{_short(c.description)} – {a.rule_id} ({a.rule_status})")
              for a in plan.evidence if a.nutrient == column for c in a.conditions]
        have = limits.get(column)
        if have and have[0] != "max":  # a max beside a min on one column: no filter, a warning (spec 4.4.4)
            del limits[column]
            warnings.append(f"Các khuyến nghị về {NUTRIENT_VI.get(column, column)} trái chiều nhau; "
                            "không lọc theo chất này.")
            evidence[f"warning:{column}"].extend([*evidence.pop(f"nutrient:{column}", []), *ev])
            continue
        limits[column] = ("max", value if have is None else min(value, have[1]))
        evidence[f"nutrient:{column}"].extend(ev)


def _limit(nutrient, rows, target, key, weight, weight_fact, warnings, evidence):
    """The strictest limit of `rows` (one nutrient, one kind) into `target`, with its evidence."""
    if len({r.op for r, _ in rows}) > 1:  # spec 4.4.4: opposite rules -> no limit, a warning
        warnings.append(f"Các khuyến nghị về {NUTRIENT_VI.get(nutrient, nutrient)} trái chiều nhau; "
                        "không lọc theo chất này.")
        evidence[f"warning:{nutrient}"].extend(ev for _, ev in rows)
        return
    if nutrient == "protein_g_per_kg" and weight is None:
        why = "cân nặng đo đã quá 2 năm" if weight_fact else "hồ sơ không có cân nặng"
        warnings.append(f"Chưa áp ngưỡng đạm theo cân nặng ({why}); nên chọn món ít đạm.")
        evidence["warning:protein_g_per_kg"].extend(ev for _, ev in rows)
        return
    op = rows[0][0].op
    values = [nutrition.per_serving_limit(r, weight) for r, _ in rows]
    column = NUTRIENT_COLUMN[nutrient]
    target[column] = (op, min(values) if op == "max" else max(values))  # exact: never rounded (ADR-0007)
    evidence[f"{key}:{column}"].extend(ev for _, ev in rows)
    if nutrient == "protein_g_per_kg" and weight_fact:
        evidence[f"{key}:{column}"].append(
            Evidence("vitals.latest", weight_fact.get("entry_id") or "",
                     f"Cân nặng {weight_fact.get('value')} {weight_fact.get('unit') or ''} ({weight_fact.get('date')})"))


def record_groups(profile: PatientProfile, nodes: list[PatientNode]) -> list[dict]:
    """The record constraints grouped by the allergy entry they come from (MV5, ADR-0008): one group per entry,
    id record:allergy/<SNOMED code>, with the evidence text and its member constraint ids. A constraint two
    entries yield is in both groups. Nutrient limits are not grouped: they are lifted one by one."""
    code_of = {f.get("entry_id"): f.get("substance_code") for f in _facts(nodes, "allergies") if f.get("entry_id")}
    groups: dict[str, dict] = {}
    for cid in constraint_ids(profile):
        if not cid.startswith(("allergen:", "ingredient:")):
            continue
        for e in profile.evidence.get(cid, []):
            code = code_of.get(e.entry_id)
            if not code:
                continue
            g = groups.setdefault(f"record:allergy/{code}", {"group_id": f"record:allergy/{code}", "node_id": e.node_id,
                                                             "text": e.text, "members": []})
            if cid not in g["members"]:
                g["members"].append(cid)
    return list(groups.values())
