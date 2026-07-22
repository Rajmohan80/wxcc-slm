#!/usr/bin/env python3
"""
STEP 3 - Verify the corpus before ingest.

Catches the four failure modes we've already hit on this project:
  1. Duplicate content across files (the cascading split bug - 1,264 duplicate lines)
  2. Missing provenance headers (the B8 "2024 Q2" fabrication, at corpus scale)
  3. Surviving boilerplate (cookie banners embedding as chunks)
  4. Stub files counted as real coverage

Run this BEFORE ingest. Every finding here is cheaper to fix now than in Qdrant.

Usage:
    python 3_verify_corpus.py --corpus-dir ./webex_slm_corpus
"""
import argparse, sys, hashlib, json, re
from itertools import combinations
from pathlib import Path

# --- Windows console safety -------------------------------------------------
# Manifest titles contain characters (em dash, arrows) that the default Windows
# console encoding (cp1252) cannot render. Without this, printing manifest data
# raises UnicodeEncodeError even though the files themselves write fine.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
# ---------------------------------------------------------------------------


HERE = Path(__file__).parent
MANIFEST = json.loads((HERE / "corpus_manifest.json").read_text(encoding="utf-8"))

BOILERPLATE_CHECKS = [
    "Was this article helpful",
    "By continuing to use our website",
    "Privacy Statement",
    "Except as otherwise noted, the content of this page",
    "Java is a registered trademark",
    "view(s)",
    "Send feedback",
]

def blocks(text):
    body = text.split("---", 2)[-1] if "---" in text[:2500] else text
    parts = [re.sub(r"\s+", " ", p).strip() for p in body.split("\n\n")]
    return {hashlib.md5(p.encode()).hexdigest(): p for p in parts if len(p) > 120}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-dir", default="./webex_slm_corpus")
    args = ap.parse_args()
    root = Path(args.corpus_dir)

    files = sorted(p for p in root.rglob("*.md") if p.name != "README.md" and "_registry" not in str(p))
    if not files:
        print("No corpus files found."); return

    print(f"=== CORPUS VERIFICATION - {len(files)} files ===\n")

    stubs, no_prov, no_tier, boiler = [], [], [], []
    texts = {}
    for f in files:
        t = f.read_text(encoding="utf-8", errors="ignore")
        texts[f] = t
        if "## Status: NOT RETRIEVED" in t:
            stubs.append(f); continue
        if "**Provenance tier:**" not in t:
            no_prov.append(f)
        if "**Source URL:**" not in t or "NOT SET" in t[:1200]:
            no_tier.append(f)
        hits = [b for b in BOILERPLATE_CHECKS if b in t]
        if hits:
            boiler.append((f, hits))

    real = [f for f in files if f not in stubs]

    print("1. COVERAGE")
    print(f"   real documents : {len(real)}")
    print(f"   stubs (gaps)   : {len(stubs)}")
    for s in stubs:
        print(f"      - {s.relative_to(root)}")

    print("\n2. PROVENANCE")
    if no_prov:
        print(f"   MISSING provenance header: {len(no_prov)}")
        for f in no_prov: print(f"      - {f.relative_to(root)}")
    else:
        print("   all real documents carry a provenance header  v")
    if no_tier:
        print(f"   missing/unset source URL: {len(no_tier)}")
        for f in no_tier: print(f"      - {f.relative_to(root)}")

    print("\n3. BOILERPLATE")
    if boiler:
        print(f"   surviving boilerplate in {len(boiler)} file(s):")
        for f, hits in boiler:
            print(f"      - {f.relative_to(root)}: {', '.join(hits[:3])}")
        print("   -> these embed as chunks and compete with real content for top-k slots")
    else:
        print("   no boilerplate detected  v")

    print("\n4. DUPLICATION")
    H = {f: blocks(texts[f]) for f in real}
    dupes = 0
    for a, b in combinations(real, 2):
        shared = set(H[a]) & set(H[b])
        if shared:
            pa = len(shared) / max(len(H[a]), 1) * 100
            pb = len(shared) / max(len(H[b]), 1) * 100
            print(f"   {a.name} <-> {b.name}: {len(shared)} identical blocks ({pa:.0f}%/{pb:.0f}%)")
            dupes += 1
    if not dupes:
        print("   no cross-file duplication  v")
    else:
        print(f"   -> {dupes} duplicate pair(s). Duplicate chunks skew retrieval and INFLATE")
        print("      Phase 3 retrieval-accuracy validation. Fix before ingest.")

    print("\n5. TIER DISTRIBUTION")
    tiers = {}
    for f in real:
        m = re.search(r"\*\*Provenance tier:\*\* TIER (\d)", texts[f])
        if m: tiers[m.group(1)] = tiers.get(m.group(1), 0) + 1
    for t in sorted(tiers):
        print(f"   Tier {t}: {tiers[t]:3d} files - {MANIFEST['tiers'][t][:60]}")

    print("\n6. FOLDER COVERAGE")
    for folder in MANIFEST["folders"]:
        fp = root / folder
        n = len([p for p in fp.glob("*.md") if p.name != "README.md"]) if fp.exists() else 0
        planned = len([d for d in MANIFEST["documents"] if d["folder"] == folder])
        flag = "" if n >= planned else f"  <- {planned - n} missing"
        print(f"   {folder:26s} {n:2d}/{planned:2d}{flag}")

    blockers = len(no_prov) + dupes + len(boiler)
    print(f"\n=== {'READY FOR INGEST' if blockers == 0 else f'{blockers} ISSUE(S) TO FIX FIRST'} ===")

if __name__ == "__main__":
    main()
