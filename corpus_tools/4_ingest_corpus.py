#!/usr/bin/env python3
"""
STEP 4 - Ingest into the vector store, Phase 7 compatible.

WHY THIS REPLACES `ingest_v2.py --reset`
----------------------------------------
`--reset` wipes and rebuilds the collection. Your Phase 7 spec (Workflow 3) says:

    "upsert to Qdrant with ingested_at, source_version, supersedes fields -
     mark superseded chunks with active=false filter flag (never hard-delete;
     retrieval filters on active=true)"

Those two designs contradict each other. If you --reset now and build Phase 7
later, the first Apply workflow fights the ingest tool. This script implements
the Phase 7 model from the start:

  - re-ingesting a changed document marks old chunks active=false (not deleted)
  - new chunks get ingested_at, source_version, supersedes
  - retrieval filters on active=true
  - provenance_tier travels into chunk metadata so Tier 1 can outrank Tier 2

`--rebuild` exists as an explicit escape hatch. It is NOT the default.

Install:
    pip install qdrant-client sentence-transformers langchain-text-splitters

Usage:
    python 4_ingest_corpus.py --corpus-dir ./webex_slm_corpus --dry-run
    python 4_ingest_corpus.py --corpus-dir ./webex_slm_corpus
    python 4_ingest_corpus.py --corpus-dir ./webex_slm_corpus --rebuild   # destructive
"""
import argparse, sys, hashlib, json, re, sys
from datetime import datetime, timezone
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


COLLECTION = "wxcc_slm_corpus"
EMBED_MODEL = "BAAI/bge-m3"          # per architecture decision - replaced all-MiniLM-L6-v2
CHUNK_SIZE, CHUNK_OVERLAP = 1000, 150

def parse_header(text):
    """Pull provenance metadata out of the header block."""
    meta = {}
    head = text[:2500]
    for key, field in [
        ("Doc ID", "doc_id"), ("Corpus folder", "folder"), ("Source URL", "source_url"),
        ("Retrieved", "retrieved"), ("Priority", "priority"), ("Provenance tier", "tier_raw"),
    ]:
        m = re.search(rf"\*\*{re.escape(key)}:\*\*\s*(.+)", head)
        if m:
            meta[field] = m.group(1).strip()
    t = re.search(r"TIER (\d)", meta.get("tier_raw", ""))
    meta["provenance_tier"] = int(t.group(1)) if t else 2   # default to Tier 2 if unstated
    meta.pop("tier_raw", None)
    return meta

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-dir", default="./webex_slm_corpus")
    ap.add_argument("--qdrant-url", default="http://localhost:6333")
    ap.add_argument("--qdrant-key", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rebuild", action="store_true",
                    help="DESTRUCTIVE: drop and recreate. Breaks Phase 7 chunk lifecycle. Avoid.")
    args = ap.parse_args()

    root = Path(args.corpus_dir)
    files = [p for p in root.rglob("*.md")
             if p.name != "README.md" and "_registry" not in str(p)]

    docs = []
    for f in files:
        t = f.read_text(encoding="utf-8", errors="ignore")
        if "## Status: NOT RETRIEVED" in t:
            print(f"  skip stub: {f.relative_to(root)}")
            continue
        meta = parse_header(t)
        body = t.split("\n---\n", 1)[-1] if "\n---\n" in t[:2500] else t
        meta.update({
            "filename": f.name,
            "folder": meta.get("folder") or f.parent.name,
            "source_version": hashlib.sha256(body.encode()).hexdigest()[:16],
            "active": True,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        })
        docs.append((f, body, meta))

    print(f"\n=== INGEST PLAN - {len(docs)} documents ===")
    tiers = {}
    for _, _, m in docs:
        tiers[m["provenance_tier"]] = tiers.get(m["provenance_tier"], 0) + 1
    for t in sorted(tiers):
        print(f"  Tier {t}: {tiers[t]} docs")

    if args.dry_run:
        print("\n--dry-run: no writes. Sample chunk metadata:\n")
        if docs:
            _, _, m = docs[0]
            print(json.dumps(m, indent=2))
        return

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import (Distance, VectorParams, PointStruct,
                                          Filter, FieldCondition, MatchValue)
        from sentence_transformers import SentenceTransformer
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError as e:
        sys.exit(f"Missing dependency: {e}\npip install qdrant-client sentence-transformers langchain-text-splitters")

    client = QdrantClient(url=args.qdrant_url, api_key=args.qdrant_key)
    model = SentenceTransformer(EMBED_MODEL)
    dim = model.get_sentence_embedding_dimension()

    if args.rebuild:
        print("\n  !! --rebuild: dropping collection. This discards chunk history and")
        print("     contradicts the Phase 7 active/supersedes lifecycle.")
        if input("     Type REBUILD to confirm: ") != "REBUILD":
            sys.exit("aborted")
        client.delete_collection(COLLECTION)

    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        # record the embedding model + version in collection metadata (GAP-RAG-01)
        print(f"  created collection '{COLLECTION}' (dim={dim}, model={EMBED_MODEL})")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP,
        separators=["\n## ", "\n### ", "\n\n", "\n", " "],
    )

    total = superseded = 0
    for f, body, meta in docs:
        # Phase 7 lifecycle: supersede rather than delete
        try:
            old, _ = client.scroll(
                collection_name=COLLECTION,
                scroll_filter=Filter(must=[
                    FieldCondition(key="filename", match=MatchValue(value=meta["filename"])),
                    FieldCondition(key="active", match=MatchValue(value=True)),
                ]),
                limit=1000,
            )
            stale = [p for p in old if p.payload.get("source_version") != meta["source_version"]]
            if stale:
                client.set_payload(
                    collection_name=COLLECTION,
                    payload={"active": False, "superseded_at": meta["ingested_at"]},
                    points=[p.id for p in stale],
                )
                superseded += len(stale)
                print(f"  superseded {len(stale)} chunk(s) of {meta['filename']} (never deleted)")
            elif old:
                print(f"  unchanged: {meta['filename']} - skip")
                continue
        except Exception:
            pass  # first run, collection empty

        chunks = splitter.split_text(body)
        vecs = model.encode(chunks, show_progress_bar=False)
        pts = []
        for i, (c, v) in enumerate(zip(chunks, vecs)):
            pid = int(hashlib.md5(f"{meta['filename']}:{meta['source_version']}:{i}".encode()).hexdigest()[:15], 16)
            payload = dict(meta)
            payload.update({"text": c, "chunk_index": i, "embed_model": EMBED_MODEL})
            pts.append(PointStruct(id=pid, vector=v.tolist(), payload=payload))
        client.upsert(collection_name=COLLECTION, points=pts)
        total += len(pts)
        print(f"  {meta['filename']:44s} {len(pts):3d} chunks  (tier {meta['provenance_tier']})")

    print(f"\n  {total} chunks upserted, {superseded} superseded (active=false, retained).")
    print("\n  RETRIEVAL REMINDER: filter on active=true, and rank provenance_tier=1 above tier 2/3.")

if __name__ == "__main__":
    main()
