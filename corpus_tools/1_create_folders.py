#!/usr/bin/env python3
"""
STEP 1 - Create the corpus folder structure.

Creates the 14-folder taxonomy locally, writes a README into each folder
explaining what belongs there, and optionally mirrors the structure to GCS.

Usage:
    python 1_create_folders.py --corpus-dir ./webex_slm_corpus
    python 1_create_folders.py --corpus-dir ./webex_slm_corpus --gcs gs://abhavtech-wxcc-slm-corpus
"""
import argparse, sys, json, os
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

README_TEMPLATE = """# {folder}

{description}

## What belongs here

{doc_list}

## Provenance tiers

- **TIER 1** - official vendor/regulator primary source (Cisco help/docs, Google Cloud docs, EUR-Lex)
- **TIER 2** - organisation-authored or third-party synthesis; ranks below Tier 1 at retrieval
- **TIER 3** - conference deck / blog / marketing; point-in-time, patterns not facts

Every file in this folder must carry a provenance header block. See `download_corpus.py`.

## Rules

1. Never mix workbooks into corpus folders. Workbooks are the structured layer; this is RAG substrate.
2. The link between a workbook row and a corpus doc is the **source citation column**, not folder location.
3. Every document with a live URL gets a Phase 7 source registry entry at ingestion time.
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-dir", default="./webex_slm_corpus")
    ap.add_argument("--gcs", default=None, help="Optional GCS bucket, e.g. gs://abhavtech-wxcc-slm-corpus")
    args = ap.parse_args()

    root = Path(args.corpus_dir)
    root.mkdir(parents=True, exist_ok=True)

    docs_by_folder = {}
    for d in MANIFEST["documents"]:
        docs_by_folder.setdefault(d["folder"], []).append(d)

    print(f"Creating corpus structure at: {root.resolve()}\n")

    for folder, desc in MANIFEST["folders"].items():
        fp = root / folder
        fp.mkdir(exist_ok=True)

        docs = docs_by_folder.get(folder, [])
        if docs:
            lines = []
            for d in sorted(docs, key=lambda x: (x["batch"], x["id"])):
                star = " [KEY]" if "STAR" in d.get("note", "") else ""
                lines.append(f"- `{d['id']}` **{d['title']}** (Tier {d['tier']}, {d['priority']}){star}")
            doc_list = "\n".join(lines)
        else:
            doc_list = "_No documents mapped yet._"

        (fp / "README.md").write_text(
            README_TEMPLATE.format(folder=folder, description=desc, doc_list=doc_list),
            encoding="utf-8"
        )
        print(f"  {folder:26s} {len(docs):2d} docs mapped")

    # registry folder for Phase 7
    reg = root / "_registry"
    reg.mkdir(exist_ok=True)
    (reg / "README.md").write_text(
        "# _registry\n\nPhase 7 knowledge-currency automation state.\n\n"
        "- `source_registry.json` - monitored sources, hashes, check frequency\n"
        "- `change_register.jsonl` - append-only change log\n"
        "- `snapshots/{source_id}/` - cached page text for diffing\n\n"
        "Not corpus content. Never ingested into the vector store.\n",
        encoding="utf-8"
    )
    (reg / "snapshots").mkdir(exist_ok=True)
    print(f"  {'_registry':26s} (Phase 7 state - not ingested)")

    print(f"\nDone. {len(MANIFEST['folders'])} folders + _registry created.")

    if args.gcs:
        print(f"\n--- GCS mirror commands ---")
        print(f"gsutil mb -l asia-south1 {args.gcs}   # Mumbai; match your tenant region")
        print(f"gsutil versioning set on {args.gcs}    # Security Pillar 4: version every document")
        for folder in MANIFEST["folders"]:
            print(f"gsutil cp {root}/{folder}/README.md {args.gcs}/{folder}/")
        print(f"gsutil cp {root}/_registry/README.md {args.gcs}/_registry/")

if __name__ == "__main__":
    main()
