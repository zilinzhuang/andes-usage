"""Validate the reviewed catalog and stage the public GitHub Pages files."""

import hashlib
import json
import math
import re
import shutil
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "_site"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", value):
        return False
    try:
        date.fromisoformat((value + "-01-01")[:10])
        return True
    except ValueError:
        return False


def unique_text(rows, key):
    values = set()
    for row in rows:
        value = row[key].strip().casefold()
        require(value and value not in values, f"Empty or repeated {key}: {value}")
        values.add(value)
    return values


def validate(catalog):
    papers = catalog["papers"]
    places = catalog["institutions"]
    unique_text(papers, "id")
    unique_text(papers, "title")
    unique_text([p for p in papers if p.get("doi")], "doi")
    unique_text(places, "id")
    place_ids = {place["id"] for place in places}
    require(valid_date(catalog["reviewedThrough"]), "Expected a valid catalog review date")
    for place in places:
        for key in ("name", "city", "country"):
            require(place[key].strip(), f"Missing {key} for {place['id']}")
        for key, limit in (("lat", 90), ("lon", 180)):
            coord = place[key]
            require(math.isfinite(coord) and abs(coord) <= limit, f"Invalid {key} for {place['id']}")
    for p in papers:
        require(valid_date(p["date"]), f"Invalid publication date for {p['id']}")
        require(all(p[key] for key in ("authors", "venue", "type", "usage")), f"Incomplete paper {p['id']}")
        require(p["evidence"]["locator"].strip(), f"Missing evidence locator for {p['id']}")
        for link in (p["url"], p["evidence"]["url"]):
            parts = urlsplit(link)
            require(parts.scheme == "https" and parts.hostname, f"Invalid source link for {p['id']}")
        ids = p["institutions"]
        require(len(ids) == len(set(ids)) and set(ids) <= place_ids, f"Invalid affiliation for {p['id']}")


def main():
    catalog = json.loads((ROOT / "data/papers.json").read_text(encoding="utf-8"))
    validate(catalog)
    status = json.loads((ROOT / "data/status.json").read_text(encoding="utf-8"))
    require("lastSuccessfulSearch" in status, "Missing search status")
    SITE.mkdir(exist_ok=True)
    (SITE / "data").mkdir(exist_ok=True)
    shutil.copytree(ROOT / "assets", SITE / "assets", dirs_exist_ok=True)
    revision = hashlib.sha256()
    for name in ("papers.json", "status.json"):
        shutil.copyfile(ROOT / "data" / name, SITE / "data" / name)
        revision.update((SITE / "data" / name).read_bytes())
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    html = html.replace('data-catalog-version=""', f'data-catalog-version="{revision.hexdigest()[:12]}"')
    for asset in ("assets/app.js", "assets/site.css"):
        digest = hashlib.sha256((SITE / asset).read_bytes()).hexdigest()[:12]
        html = html.replace(f'"{asset}"', f'"{asset}?v={digest}"')
    (SITE / "index.html").write_text(html, encoding="utf-8")
    print(f"Staged {len(catalog['papers'])} papers and {len(catalog['institutions'])} institutions")


if __name__ == "__main__":
    main()
