from __future__ import annotations
import argparse, json, math
from collections import Counter
from pathlib import Path
from typing import Any
from .plan_media_sampling import alias_entries, family_for_label, load_jsonl

def counts(path: Path) -> Counter[str]:
    return Counter(str(e.get("label")) for r in load_jsonl(path) for e in (r.get("entities") or []) if str(e.get("label") or "").startswith("org.ent."))

def build_plan(seeds_path: Path, validation_path: Path, test_path: Path, family: str, minimum: int, languages: list[str], max_queries: int, sample_factor: float = 1.5) -> dict[str, Any]:
    validation, test = counts(validation_path), counts(test_path)
    rows, gaps = [], []
    for seed in json.loads(seeds_path.read_text(encoding="utf-8")):
        label = str(seed.get("label") or "")
        if seed.get("trainable") is False or family_for_label(label) != family:
            continue
        vm, tm = max(minimum - validation[label], 0), max(minimum - test[label], 0)
        needed = vm + tm
        if not needed:
            continue
        planned_candidates = math.ceil(needed * sample_factor)
        gaps.append({"label": label, "validation": validation[label], "validation_missing": vm, "test": test[label], "test_missing": tm, "needed": needed, "planned_candidates": planned_candidates})
        aliases = alias_entries(seed, languages)[:max_queries]
        remaining = planned_candidates
        for item in aliases:
            planned = min(math.ceil(planned_candidates / len(aliases)), remaining)
            rows.append({"family": family, "label": label, "canonical_id": seed.get("canonical_id"), "display_name": seed.get("display_name"), "language": item["language"], "query": item["query"], "planned_new": planned, "missing": needed, "reason": "holdout_deficit", "priority": 100})
            remaining -= planned
            if remaining <= 0: break
    return {"family": family, "rows": rows, "gaps": gaps, "settings": {"minimum": minimum, "sample_factor": sample_factor}}

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Plan sampling for validation/test positive-count gaps.")
    p.add_argument("--family", choices=["pressagency", "radiostation"], required=True); p.add_argument("--seeds", type=Path, required=True)
    p.add_argument("--validation", type=Path, required=True); p.add_argument("--test", type=Path, required=True); p.add_argument("--minimum", type=int, default=5)
    p.add_argument("--languages", nargs="+", required=True); p.add_argument("--max-queries", type=int, default=3); p.add_argument("--sample-factor", type=float, default=1.5); p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    if a.sample_factor < 1.0: p.error("--sample-factor must be at least 1.0")
    plan = build_plan(a.seeds, a.validation, a.test, a.family, a.minimum, a.languages, a.max_queries, a.sample_factor)
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({"output": str(a.output), "labels_below_minimum": len(plan["gaps"]), "planned_samples": sum(r["planned_new"] for r in plan["rows"])}, sort_keys=True))
    for g in plan["gaps"]: print(f"  {g['label']}: validation={g['validation']} (-{g['validation_missing']}), test={g['test']} (-{g['test_missing']}), sample={g['planned_candidates']}")
    return 0
if __name__ == "__main__": raise SystemExit(main())
