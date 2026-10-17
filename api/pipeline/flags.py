"""Pipeline switches and the presets of the comparison (sườn báo cáo 4.3). A preset is only a set of flags:
every configuration runs the same code (CLAUDE.md rule 10)."""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Flags:
    qu: bool = True              # M1: understand the query (off: the raw message goes to retrieval, no constraints)
    conv: bool = True            # M2: keep constraints and history across turns (off: every turn stands alone)
    filter: bool = True          # M4: constraints become WHERE conditions (off: they are appended to the query text)
    norm: bool = True            # M4: filter on canonical ingredients and tags (off: ILIKE on raw ingredient lines)
    rerank: bool = True          # M5: cross-encoder reranking
    generate: bool = True        # M6: write an answer (off: retrieval only, as A1)
    verify: bool = True          # M7: citation check
    unknown_strict: bool = False  # M4: with an allergen constraint, also drop Recipes that have unknown lines (D8)
    # Patient record (docs/plan/A3_vectorless_ho_so.md 5.8): used only when the session has a patient_id
    profile: bool = True         # V1-V3: apply the record's constraints (off: S-Profile, dialogue constraints only)
    profile_mode: str = "vectorless"  # direct | vectorless | vectorless_nofixed | vector


PROFILE_MODES = {"direct", "vectorless", "vectorless_nofixed", "vector"}
MV4_MODES = {"vectorless_nofixed", "vector"}  # need api/patient/baselines.py (MV4)


S = Flags()
PRESETS: dict[str, Flags] = {
    "B0": Flags(qu=False, conv=False, filter=False, norm=False, generate=False, verify=False),  # A1 Hybrid
    "B1": Flags(qu=False, conv=False, filter=False, norm=False, verify=False),                  # naive RAG on A1
    "S": S,
    "S-QU": replace(S, qu=False),
    "S-Filter": replace(S, filter=False),
    "S-Norm": replace(S, norm=False),
    "S-Conv": replace(S, conv=False),
    "S-Rerank": replace(S, rerank=False),
    "S-Verify": replace(S, verify=False),
    "S+Unknown": replace(S, unknown_strict=True),
    # patient presets: with no patient_id they behave exactly as S
    "S-Profile": replace(S, profile=False),
    "P-Direct": replace(S, profile_mode="direct"),
    "P-Vectorless": S,
    "P-Vectorless-Fixed": replace(S, profile_mode="vectorless_nofixed"),
    "P-Vector": replace(S, profile_mode="vector"),
}


def preset(name: str) -> Flags:
    if name not in PRESETS:
        raise ValueError(f"unknown preset {name!r}; known: {', '.join(PRESETS)}")
    return PRESETS[name]
