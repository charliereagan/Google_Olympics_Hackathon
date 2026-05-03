"""Wikidata SPARQL fetcher (secondary, optional).

Per BUILD_SPEC §5.7: Wikidata fills in variant names — nicknames, alternate
spellings, married names, native-language labels — that the Olympedia CSV
scrape doesn't carry. Cross-referenced by family name + given name + birth
year.

Polite-use:
  - Custom ``User-Agent`` per Wikidata SPARQL endpoint policy.
  - Single batched query; cache the response to disk.
  - Soft-fails: if the endpoint times out or returns 5xx, return [] so the
    pipeline still produces a registry from Olympedia alone.

Coverage:
  - Olympic athletes via either ``wdt:P166`` (award received) -> Olympic medal
    Q-IDs, or ``wdt:P1344`` (participant in) -> Olympic Games event Q-IDs.
  - Paralympic athletes via ``wdt:P166`` -> Paralympic medal Q-IDs (this is
    the gap that Olympedia/KeithGalli doesn't cover).

We deliberately keep the SPARQL conservative: a broad-coverage query that
returns >50K rows would time out + waste politeness budget. We aim for a
~2-3K-row response that primarily delivers variant-name signal.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "data" / "cache" / "olympedia"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = (
    "TheStorytellersRoom/0.1 (charliereagan@gmail.com) Hackathon-research-only"
)

ENDPOINT = "https://query.wikidata.org/sparql"

# US Paralympic medalists. Q-IDs verified by rdfs:label probe 2026-05-03:
#   Q15243424 = Paralympic gold medal
#   Q15243447 = Paralympic silver medal
#   Q15243454 = Paralympic bronze medal
# (If a future Wikidata rename breaks any of these, the query simply returns
# 0 rows and the loader falls back to Olympedia alone.)
PARALYMPIC_QUERY = (
    "SELECT DISTINCT ?p ?pLabel ?dob ?sportLabel ?nativeLabel WHERE { "
    "  ?p wdt:P31 wd:Q5 ; wdt:P27 wd:Q30 ; "
    "     wdt:P166 ?medal . "
    "  VALUES ?medal { wd:Q15243424 wd:Q15243447 wd:Q15243454 } . "
    "  OPTIONAL { ?p wdt:P569 ?dob } . "
    "  OPTIONAL { ?p wdt:P641 ?sport } . "
    "  OPTIONAL { ?p wdt:P1559 ?nativeLabel } . "
    "  SERVICE wikibase:label { bd:serviceParam wikibase:language 'en' } "
    "} LIMIT 5000"
)

# US Olympic medalists. Q-IDs verified by rdfs:label probe 2026-05-03:
#   Q15243387 = Olympic gold medal
#   Q15889641 = Olympic silver medal
#   Q15889643 = Olympic bronze medal
OLYMPIC_QUERY = (
    "SELECT DISTINCT ?p ?pLabel ?dob ?sportLabel ?nativeLabel WHERE { "
    "  ?p wdt:P31 wd:Q5 ; wdt:P27 wd:Q30 ; "
    "     wdt:P166 ?medal . "
    "  VALUES ?medal { wd:Q15243387 wd:Q15889641 wd:Q15889643 } . "
    "  OPTIONAL { ?p wdt:P569 ?dob } . "
    "  OPTIONAL { ?p wdt:P641 ?sport } . "
    "  OPTIONAL { ?p wdt:P1559 ?nativeLabel } . "
    "  SERVICE wikibase:label { bd:serviceParam wikibase:language 'en' } "
    "} LIMIT 5000"
)


@dataclass
class WikidataAthlete:
    qid: str
    full_name_raw: str
    born_year: int | None = None
    sport: str | None = None
    olympic_or_paralympic: str = "olympic"
    native_labels: list[str] = field(default_factory=list)


def _run_query(query: str, cache_name: str, force_refresh: bool = False) -> dict | None:
    cache_path = CACHE_DIR / cache_name
    if cache_path.exists() and not force_refresh and cache_path.stat().st_size > 0:
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/sparql-results+json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        data = json.loads(body)
        cache_path.write_text(body, encoding="utf-8")
        return data
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"  [wikidata] query {cache_name!r} failed (non-fatal): {exc}", file=sys.stderr)
        return None


def _parse_year(s: str | None) -> int | None:
    if not s:
        return None
    if len(s) >= 4 and s[:4].isdigit():
        try:
            return int(s[:4])
        except ValueError:
            return None
    return None


def _bindings_to_athletes(data: dict, kind: str) -> list[WikidataAthlete]:
    """Aggregate by qid. Multiple bindings per athlete (multi-sport, multi-medal)
    collapse into a single record with merged native_labels."""
    by_qid: dict[str, WikidataAthlete] = {}
    for row in (data.get("results", {}) or {}).get("bindings", []) or []:
        qid_uri = (row.get("p", {}) or {}).get("value", "")
        if not qid_uri:
            continue
        qid = qid_uri.rsplit("/", 1)[-1]
        label = (row.get("pLabel", {}) or {}).get("value", "").strip()
        if not label or label == qid:
            continue  # skip un-labeled rows
        rec = by_qid.get(qid)
        if rec is None:
            rec = WikidataAthlete(
                qid=qid,
                full_name_raw=label,
                born_year=_parse_year((row.get("dob", {}) or {}).get("value", "")),
                sport=(row.get("sportLabel", {}) or {}).get("value") or None,
                olympic_or_paralympic=kind,
            )
            by_qid[qid] = rec
        native = (row.get("nativeLabel", {}) or {}).get("value", "").strip()
        if native and native not in rec.native_labels and native != rec.full_name_raw:
            rec.native_labels.append(native)
    return list(by_qid.values())


def fetch(force_refresh: bool = False) -> tuple[list[WikidataAthlete], dict]:
    """Fetch Olympic + Paralympic medalists from Wikidata."""
    out: list[WikidataAthlete] = []
    attribution = {
        "endpoint": ENDPOINT,
        "olympic_query": OLYMPIC_QUERY,
        "paralympic_query": PARALYMPIC_QUERY,
        "user_agent": USER_AGENT,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    olympic = _run_query(OLYMPIC_QUERY, "wikidata_olympic.json", force_refresh=force_refresh)
    if olympic:
        recs = _bindings_to_athletes(olympic, "olympic")
        out.extend(recs)
        attribution["olympic_count"] = len(recs)
    else:
        attribution["olympic_count"] = 0

    paralympic = _run_query(PARALYMPIC_QUERY, "wikidata_paralympic.json", force_refresh=force_refresh)
    if paralympic:
        recs = _bindings_to_athletes(paralympic, "paralympic")
        out.extend(recs)
        attribution["paralympic_count"] = len(recs)
    else:
        attribution["paralympic_count"] = 0

    attribution["total"] = len(out)
    return out, attribution


if __name__ == "__main__":
    refresh = "--refresh" in sys.argv
    recs, attr = fetch(force_refresh=refresh)
    print(f"Wikidata: {attr.get('olympic_count', 0)} olympic + {attr.get('paralympic_count', 0)} paralympic")
    for r in recs[:5]:
        print(f"  - {r.full_name_raw} | qid={r.qid} | sport={r.sport} | dob={r.born_year} | native={r.native_labels[:2]}")
