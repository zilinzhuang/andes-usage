"""Find possible ANDES uses. Only data/papers.json supplies the public atlas."""

import datetime as dt
import json
import os
from pathlib import Path
import re
import time
import unicodedata
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SEED_DOIS = ("10.1109/TPWRS.2020.3017019", "10.1109/NAPS.2018.8600596")
USER_AGENT = "ANDES-Usage-Atlas/1.0 (+https://github.com/zilinzhuang/andes-usage)"
ARXIV_ID = re.compile(r"(?:arxiv\.org/(?:abs|html|pdf)/|10\.48550/arxiv\.|^arxiv:)(\d{4}\.\d{4,5})(?:v\d+)?", re.I)
OA_FIELDS = "id,doi,display_name,publication_date,primary_location,locations,ids"
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
OPENSEARCH = "{http://a9.com/-/spec/opensearch/1.1/}"
LAST_ARXIV = 0.0


def get(url):
    """Fetch public metadata with bounded retries, size and arXiv request pacing."""
    global LAST_ARXIV
    host = urlparse(url).hostname
    for attempt in range(3):
        if host in ("arxiv.org", "export.arxiv.org"):
            time.sleep(max(0, 3.1 - (time.monotonic() - LAST_ARXIV)))
            LAST_ARXIV = time.monotonic()
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=18) as response:
                body = response.read(12_000_001)
                if len(body) > 12_000_000:
                    raise RuntimeError(f"{host} response exceeds size limit")
                return body
        except HTTPError as exc:
            if exc.code not in (408, 429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError(f"{host} HTTP {exc.code}") from None
            retry_header = exc.headers.get("Retry-After", "")
            delay = int(retry_header) if retry_header.isdigit() else 2 ** (attempt + 1)
            if delay > 30:
                raise RuntimeError(f"{host} requested a later retry (HTTP {exc.code})") from None
        except (TimeoutError, URLError, OSError) as exc:
            if attempt == 2:
                raise RuntimeError(f"{host} unavailable ({type(exc).__name__})") from None
            delay = 2 ** (attempt + 1)
        time.sleep(delay)


def clean(text):
    return " ".join((text or "").split())


def doi_id(value):
    return re.sub(r"^https?://(?:dx\.)?doi\.org/|^doi:\s*", "", (value or "").strip(), flags=re.I).lower()


def arxiv_id(*values):
    for value in values:
        match = ARXIV_ID.search(value or "")
        if match:
            return match.group(1)
    return None


def oa_request(path, **params):
    if os.getenv("OPENALEX_API_KEY"):
        params["api_key"] = os.environ["OPENALEX_API_KEY"]
    return json.loads(get(f"https://api.openalex.org/works{path}?{urlencode(params)}"))


def oa_results(**params):
    # Basic paging works without an OpenAlex key. Cursor paging after page 1 does not.
    page_size = 100
    page = 1
    results = []
    while True:
        data = oa_request("", **params, select=OA_FIELDS, per_page=page_size, page=page)
        works = data["results"]
        for work in works:
            title = clean(work.get("display_name"))
            if not title:
                continue
            doi = doi_id(work.get("doi"))
            loc = work.get("primary_location") or {}
            locations = work.get("locations") or []
            aid = arxiv_id(doi, *(item.get("landing_page_url") for item in locations))
            results.append({
                "title": title, "date": work.get("publication_date"), "doi": doi or None,
                "arxivId": aid, "openalexId": work["id"].rsplit("/", 1)[-1],
                "url": "https://doi.org/" + doi if doi else loc.get("landing_page_url") or work["id"],
            })
        if page * page_size >= int(data["meta"]["count"]):
            return results
        if not works or page * page_size >= 10_000:
            raise RuntimeError("OpenAlex basic paging incomplete; narrow this query")
        page += 1


def citing_works():
    ids = []
    for doi in SEED_DOIS:
        work = oa_request("/https://doi.org/" + doi, select="id")
        ids.append(work["id"].rsplit("/", 1)[-1])
    # Re-scan all years. Older papers and late-added citations remain discoverable.
    return oa_results(filter="cites:" + "|".join(ids))


def software_mentions():
    phrases = '("ANDES simulator" OR "ANDES software" OR "ANDES toolbox" OR "ANDES simulation platform" OR "CURENT/andes")'
    domain = '("power system" OR "power grid" OR "grid-forming" OR "transient stability")'
    return oa_results(search=f"{phrases} AND {domain}", filter="from_publication_date:2015-01-01")


def crossref_recent(since):
    """Inspect new DOI deposits in power-system journals, even without open abstracts."""
    # TPWRS, TSG, TSTE and International Journal of Electrical Power & Energy Systems.
    journals = ("0885-8950", "1949-3053", "1949-3029", "0142-0615")
    references = {doi.lower() for doi in SEED_DOIS}
    results = []
    for issn in journals:
        offset = 0
        while True:
            params = {"filter": "from-created-date:" + since, "rows": 100, "offset": offset,
                      "select": "DOI,title,abstract,reference,published", "sort": "created", "order": "asc"}
            api = f"https://api.crossref.org/journals/{issn}/works?{urlencode(params)}"
            data = json.loads(get(api))["message"]
            items = data["items"]
            for item in items:
                title = clean((item.get("title") or [""])[0])
                doi = doi_id(item.get("DOI"))
                cites = {doi_id(ref.get("DOI")) for ref in item.get("reference", [])}
                mentions = re.search(r"\bANDES\b", title + " " + (item.get("abstract") or ""))
                if not title or not doi or (not mentions and cites.isdisjoint(references)):
                    continue
                parts = (item.get("published", {}).get("date-parts") or [[]])[0]
                date = "-".join(str(v).zfill(2) for v in parts) or None
                results.append({"title": title, "doi": doi, "date": date, "url": "https://doi.org/" + doi})
            offset += len(items)
            if offset >= data["total-results"]:
                break
            if not items or offset >= 10_000:
                raise RuntimeError(f"Crossref paging incomplete for journal {issn}")
    return results


def arxiv_mentions():
    query = '(ti:ANDES OR abs:ANDES) AND (abs:"power system" OR abs:"power systems" OR abs:"power grid" OR abs:"grid-forming" OR abs:"transient stability")'
    records = []
    start = 0
    while True:
        params = {"search_query": query, "sortBy": "lastUpdatedDate", "sortOrder": "descending",
                  "start": start, "max_results": 100}
        root = ET.fromstring(get("https://export.arxiv.org/api/query?" + urlencode(params)))
        total = int(root.findtext(OPENSEARCH + "totalResults"))
        entries = root.findall(ATOM + "entry")
        for entry in entries:
            aid = arxiv_id(entry.findtext(ATOM + "id"))
            if not aid:
                raise RuntimeError("arXiv returned an unexpected feed entry")
            records.append({
                "title": clean(entry.findtext(ATOM + "title")), "date": entry.findtext(ATOM + "published", "")[:10],
                "doi": doi_id(entry.findtext(ARXIV + "doi")) or None, "arxivId": aid,
                "url": "https://arxiv.org/abs/" + aid,
            })
        start += len(entries)
        if start >= total:
            return records
        if not entries or start > 6000:
            raise RuntimeError("arXiv query did not complete pagination")


def keys(row):
    doi = doi_id(row.get("doi"))
    aid = row.get("arxivId") or arxiv_id(doi, row.get("url"), (row.get("evidence") or {}).get("url"))
    identifiers = {key for key in (doi, "arxiv:" + aid if aid else None, row.get("openalexId")) if key}
    # A normalized exact title also aligns journal and preprint records lacking cross-links.
    title = re.sub(r"[^\w]+", " ", unicodedata.normalize("NFKC", row["title"]).casefold()).strip()
    if len(title) > 25:
        identifiers.add("title:" + title)
    return identifiers


def update_queue(queue, papers, by_source, today):
    published = {key for paper in papers for key in keys(paper)}
    queue = [record for record in queue if keys(record).isdisjoint(published)]
    lookup = {key: record for record in queue for key in keys(record)}
    for source, records in by_source.items():
        for row in records:
            ids = keys(row)
            if not ids or not published.isdisjoint(ids):
                continue
            existing = next((lookup[k] for k in sorted(ids) if k in lookup), None)
            if existing is None:
                existing = {**row, "firstSeen": today, "reviewState": "pending", "sources": []}
                queue.append(existing)
            for field in ("arxivId", "doi", "openalexId", "date"):
                if row.get(field) and not existing.get(field):
                    existing[field] = row[field]
            if source not in existing["sources"]:
                existing["sources"].append(source)
            for key in ids:
                lookup[key] = existing
    return sorted(queue, key=lambda r: (r.get("date") or "", r["title"]), reverse=True)


class BodyParagraphs(HTMLParser):
    """Read arXiv HTML paragraphs with section labels. References are never review hints."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections = {}
        self.heading_level = None
        self.heading = []
        self.para = None
        self.anchor = ""
        self.matches = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if re.fullmatch(r"h[1-6]", tag):
            self.heading_level = int(tag[1])
            self.heading = []
        if tag in ("div", "section", "p") and attrs.get("id"):
            self.anchor = attrs["id"]
        if tag == "p":
            self.para = []

    def handle_data(self, data):
        if self.heading_level is not None:
            self.heading.append(data)
        if self.para is not None:
            self.para.append(data)

    def handle_endtag(self, tag):
        if self.heading_level is not None and tag == f"h{self.heading_level}":
            self.sections = {level: text for level, text in self.sections.items() if level < self.heading_level}
            self.sections[self.heading_level] = clean("".join(self.heading))
            self.heading_level = None
        if tag != "p" or self.para is None:
            return
        paragraph = clean("".join(self.para))
        self.para = None
        section = " / ".join(self.sections[k] for k in sorted(self.sections) if k > 1)
        match = re.search(r"\bANDES\b", paragraph)
        if not match or not section or re.search(r"\b(references|bibliography|abstract)\b", section, re.I):
            return
        # A short literal excerpt helps a reviewer find the source; it never authorizes inclusion.
        words = paragraph.split()
        index = len(paragraph[:match.start()].split())
        start = max(0, index - 7)
        excerpt = " ".join(words[start:start + 22])
        weight = bool(re.search(r"\b(simulat\w*|implement\w*|compar\w*|validat\w*|generate\w*)\b", paragraph, re.I))
        methods = bool(re.search(r"case stud|experiment|simulat|method|numerical|implement|validation|results", section, re.I))
        self.matches.append((int(weight) + 2 * int(methods), excerpt, section, self.anchor))


def collect_hints(queue, today, limit=8):
    # Check oldest uninspected entries first; periodically retry inaccessible or revised papers.
    cutoff = (dt.date.fromisoformat(today) - dt.timedelta(days=30)).isoformat()
    eligible = [r for r in queue if r.get("reviewState") == "pending" and r.get("arxivId")
                and r.get("fulltextChecked", "") <= cutoff]
    eligible.sort(key=lambda r: r.get("fulltextChecked", ""))
    for row in eligible[:limit]:
        row["fulltextChecked"] = today
        url = "https://arxiv.org/html/" + row["arxivId"]
        try:
            parser = BodyParagraphs()
            parser.feed(get(url).decode("utf-8", "replace"))
            parser.close()
            if parser.matches:
                _, excerpt, section, anchor = max(parser.matches, key=lambda match: match[0])
                row["reviewHint"] = {"excerpt": excerpt, "section": section,
                                     "url": url + ("#" + anchor if anchor else "")}
                row["fulltextStatus"] = "passage located; needs review"
            else:
                row["fulltextStatus"] = "no body passage located"
                row.pop("reviewHint", None)
        except (RuntimeError, ValueError) as exc:
            row["fulltextStatus"] = str(exc)
            print(f"Full-text lookup for arXiv {row['arxivId']}: {exc}")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, obj):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def main():
    folder = ROOT / "data"
    papers = read(folder / "papers.json")["papers"]
    queue = read(folder / "candidates.json")["candidates"]
    status = read(folder / "status.json")
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    previous = status["sources"].get("Crossref journal deposits", {}).get("lastSuccess", now)
    since = (dt.date.fromisoformat(previous[:10]) - dt.timedelta(days=7)).isoformat()
    sources = {"OpenAlex citations": citing_works, "OpenAlex text search": software_mentions,
               "arXiv metadata": arxiv_mentions, "Crossref journal deposits": lambda: crossref_recent(since)}
    obtained = {}
    for name, fetch in sources.items():
        state = status["sources"].setdefault(name, {})
        try:
            obtained[name] = fetch()
            state.update(outcome="success", lastSuccess=now, records=len(obtained[name]))
            state.pop("error", None)
            print(f"{name}: {len(obtained[name])} records retrieved")
        except (RuntimeError, ValueError, ET.ParseError, KeyError, TypeError) as exc:
            state.update(outcome="unavailable", error=str(exc))
            print(f"::warning::{name} incomplete: {exc}")
    if not obtained:
        raise SystemExit("No search completed; previous queue and status preserved.")
    queue = update_queue(queue, papers, obtained, now[:10])
    collect_hints(queue, now[:10])
    status["lastAttempt"] = now
    status["outcome"] = "success" if len(obtained) == len(sources) else "partial"
    if status["outcome"] == "success":
        status["lastSuccessfulSearch"] = now
    write(folder / "candidates.json", {"candidates": queue})
    write(folder / "status.json", status)
    pending = sum(r["reviewState"] == "pending" for r in queue)
    print(f"Discovery {status['outcome']}; {pending} candidates awaiting review. Published papers untouched.")


if __name__ == "__main__":
    main()
