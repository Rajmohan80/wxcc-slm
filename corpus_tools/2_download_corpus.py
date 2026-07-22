#!/usr/bin/env python3
"""
STEP 2 - Download corpus documents.

Fixes over the naive version:
  1. Writes to the 14-folder taxonomy (not ad-hoc folder names)
  2. Strips nav/footer/cookie boilerplate BEFORE conversion (Phase 7 extraction discipline)
  3. Stamps a provenance header on every file (tier, source, retrieval date)
  4. Reads corpus_manifest.json - edit the manifest, not this script
  5. Writes a stub when a URL is missing or a fetch fails, so the slot exists

Install:
    pip install requests html2text pdfminer.six beautifulsoup4

Usage:
    python 2_download_corpus.py --corpus-dir ./webex_slm_corpus --dry-run
    python 2_download_corpus.py --corpus-dir ./webex_slm_corpus --batch 2
    python 2_download_corpus.py --corpus-dir ./webex_slm_corpus            # all batches
"""
import argparse, sys, json, re, sys, time
from datetime import date
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

# ---------------------------------------------------------------- boilerplate
# Lines matching these are dropped. Cisco help pages and Google Cloud docs both
# carry nav, cookie banners, feedback widgets and licence blocks on EVERY page.
# Left in, they become chunk noise: the same paragraph embeds dozens of times
# and competes with real content for top-k slots.
NOISE_PATTERNS = [
    r"^\s*By continuing to use our website, you acknowledge the use of cookies",
    r"^\s*Privacy Statement\s*$",
    r"^\s*Change Settings\s*$",
    r"^\s*Was this article helpful\??\s*$",
    r"^\s*Yes,? thank you!?\s*$",
    r"^\s*Not really\s*$",
    r"^\s*\d+ view\(s\)",
    r"^\s*\d+ people thought this was helpful",
    r"^\s*View change log\s*$",
    r"^\s*Subscribe\s*$",
    r"^\s*In this article\s*$",
    r"^\s*Feedback\??\s*$",
    r"^\s*This article applies to:\s*$",
    r"^\s*Send feedback\s*$",
    r"^\s*Was this helpful\??\s*$",
    r"^\s*Need to tell us more\?",
    r"^\s*Except as otherwise noted, the content of this page is licensed under",
    r"^\s*Java is a registered trademark of Oracle",
    r"^\s*For details, see the Google Developers Site Policies",
    r"^\s*\[\[\[\"Easy to understand\"",
    r"^\s*Skip to main content\s*$",
    r"^\s*Contact Us\s*$",
    r"^\s*Start free\s*$",
    r"^\s*Sign in\s*$",
    r"^\s*Console\s*$",
]
NOISE_RE = [re.compile(p, re.I) for p in NOISE_PATTERNS]

# Whole-block removals (nav bars, cookie modals) by CSS selector
STRIP_SELECTORS = [
    "nav", "header", "footer", "script", "style", "noscript",
    "[role=navigation]", "[role=banner]", "[role=contentinfo]",
    ".cookie-banner", "#onetrust-banner-sdk", ".feedback", ".devsite-footer",
    ".devsite-book-nav", ".devsite-header", "#book-nav", ".article-feedback",
]

def clean_lines(text: str) -> str:
    out, blanks = [], 0
    for line in text.split("\n"):
        if any(rx.search(line) for rx in NOISE_RE):
            continue
        if not line.strip():
            blanks += 1
            if blanks > 2:      # collapse runs of blank lines
                continue
        else:
            blanks = 0
        out.append(line.rstrip())
    return "\n".join(out).strip() + "\n"

def header(doc, url, method):
    star = " [KEY - Phase 7 monitored source, high change rate]" if "STAR" in doc.get("note", "") else ""
    tier_desc = MANIFEST["tiers"][str(doc["tier"])]
    return (
        f"# {doc['title']}\n\n"
        f"> **Doc ID:** {doc['id']}{star}\n"
        f"> **Corpus folder:** {doc['folder']}\n"
        f"> **GCP bucket path:** webex-slm-corpus/{doc['folder']}/{doc['filename']}\n"
        f"> **Provenance tier:** TIER {doc['tier']} - {tier_desc}\n"
        f"> **Source URL:** {url or 'NOT SET - see manifest'}\n"
        f"> **Retrieved:** {date.today().isoformat()}\n"
        f"> **Retrieval method:** {method}\n"
        f"> **Priority:** {doc['priority']}\n"
        f"> **Note:** {doc.get('note', '-')}\n"
        f"> **Retrieval weighting:** "
        + ("rank above Tier 2/3 sources on the same query.\n" if doc["tier"] == 1
           else "rank BELOW Tier 1 sources on the same query.\n")
        + "\n---\n\n"
    )

def stub(doc, reason):
    return header(doc, doc.get("url", ""), "MANUAL - not yet retrieved") + (
        f"## Status: NOT RETRIEVED\n\n"
        f"**Reason:** {reason}\n\n"
        f"### To fill this slot\n\n"
        f"1. Open the source URL (add it to `corpus_manifest.json` if blank)\n"
        f"2. Save the page as text/markdown, or print to PDF and extract\n"
        f"3. Replace everything below this line - keep the header block above intact\n"
        f"4. Re-run the ingest\n\n"
        f"This stub exists so the corpus slot is visible and the gap is countable.\n"
    )

def fetch_web(url):
    import requests
    from bs4 import BeautifulSoup
    import html2text
    r = requests.get(url, timeout=45, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AbhavTech-SLM-corpus/1.0; +https://abhavtech.com)"
    })
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for sel in STRIP_SELECTORS:
        for el in soup.select(sel):
            el.decompose()
    main = (soup.select_one("main") or soup.select_one("article")
            or soup.select_one(".devsite-article-body") or soup.body or soup)
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0
    return clean_lines(h.handle(str(main)))

def fetch_pdf(url):
    import requests
    from pdfminer.high_level import extract_text
    import io
    r = requests.get(url, timeout=90, headers={"User-Agent": "AbhavTech-SLM-corpus/1.0"})
    r.raise_for_status()
    return clean_lines(extract_text(io.BytesIO(r.content)))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-dir", default="./webex_slm_corpus")
    ap.add_argument("--batch", type=int, default=None, help="1=India+EU, 2=Cisco official, 3=Google AI, 4=EU regs, 5=Cisco Live")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--delay", type=float, default=2.0, help="Polite crawl delay (seconds)")
    args = ap.parse_args()

    root = Path(args.corpus_dir)
    if not root.exists():
        sys.exit(f"Corpus dir missing: {root}\nRun 1_create_folders.py first.")

    docs = MANIFEST["documents"]
    if args.batch:
        docs = [d for d in docs if d["batch"] == args.batch]

    ok = skip = stubbed = fail = 0
    for d in docs:
        dest = root / d["folder"] / d["filename"]
        url = d.get("url", "")

        if d.get("skip"):
            # Pointer entry: content lives in another document. Downloading it would
            # create duplicate chunks in the vector store.
            print(f"  [ptr   ] {d['id']:6s} {d['title'][:44]:44s} covered elsewhere - not fetched")
            skip += 1
            continue
        if d.get("have_local"):
            print(f"  [local ] {d['id']:6s} {d['filename']:44s} already have - place manually")
            skip += 1
            continue
        if dest.exists() and "NOT RETRIEVED" not in dest.read_text(encoding="utf-8", errors="ignore")[:2000]:
            print(f"  [exists] {d['id']:6s} {d['filename']:44s} skip")
            skip += 1
            continue
        if not url:
            if not args.dry_run:
                dest.write_text(stub(d, "No URL in manifest - add it and re-run"), encoding="utf-8")
            print(f"  [stub  ] {d['id']:6s} {d['filename']:44s} no URL")
            stubbed += 1
            continue
        if args.dry_run:
            print(f"  [plan  ] {d['id']:6s} {d['folder']}/{d['filename']}  <- {url[:52]}")
            continue

        try:
            body = fetch_pdf(url) if d["type"] == "pdf" else fetch_web(url)
            if len(body) < 400:
                raise ValueError(f"suspiciously short ({len(body)} chars) - likely JS-rendered or blocked")
            dest.write_text(header(d, url, f"{d['type']} fetch + boilerplate strip") + body, encoding="utf-8")
            print(f"  [ok    ] {d['id']:6s} {d['filename']:44s} {len(body):>7,} chars")
            ok += 1
            time.sleep(args.delay)
        except Exception as e:
            dest.write_text(stub(d, f"Fetch failed: {e}"), encoding="utf-8")
            print(f"  [FAIL  ] {d['id']:6s} {d['filename']:44s} {str(e)[:44]}")
            fail += 1
            time.sleep(1)

    print(f"\n  ok={ok}  skipped={skip}  stubbed={stubbed}  failed={fail}")
    if fail or stubbed:
        print("\n  Stubs are placeholders - fill them manually. Cisco pages often need session cookies;")
        print("  print-to-PDF in the browser then extract is the reliable fallback.")
    print(f"\n  Next: python 3_verify_corpus.py --corpus-dir {args.corpus_dir}")

if __name__ == "__main__":
    main()
