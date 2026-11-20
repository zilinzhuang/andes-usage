# ANDES Usage Atlas

[Explore the atlas](https://zilinzhuang.github.io/andes-usage/)

A searchable index and world map of research papers that document using the [ANDES power system simulator](https://docs.andes.app/). This independent catalog is maintained by Zilin Zhuang. The index starts with a reviewed selection and grows as further papers are verified.

## Reading the map

Markers locate the author affiliations of included studies, approximately at the institution or city level. Select an institution to filter its publications. Papers with several affiliations appear at several places but count once in the total. The publication list runs from newest to oldest. Each record gives a use summary and a link to the relevant section, figure, or supporting material.

## Inclusion and corrections

Include a study when the authors' methods, results, figures, or associated research code identify an actual ANDES calculation, simulation, implementation, data generation step, or benchmark in that study. A citation, background discussion, or mention of the larger CURENT testbed by itself is insufficient. Record the original source URL and a precise locator, and summarize the work in your own words. List affiliations as published. Only count organizations whose authors contributed to the paper, regardless of where a dataset or computing facility was hosted.

Keep one record for a preprint and its published version. Prefer the publisher's first online publication date where documented. If only a month or year is known, retain that precision. Mark preprints explicitly.

- [Suggest a paper or report a correction](https://github.com/zilinzhuang/andes-usage/issues/new). Provide the paper title, DOI or stable URL, evidence location, and the relevant institution.
- Reviewed records and institution coordinates live in [data/papers.json](data/papers.json). A maintainer can accept an item by adding or updating its record and corresponding affiliations through a pull request. Advance `reviewedThrough` when completing a review.
- [data/candidates.json](data/candidates.json) is the daily discovery queue. A candidate enters the map and publication counts only when accepted into the reviewed catalog.

## Publishing

[Discover papers](https://github.com/zilinzhuang/andes-usage/actions/workflows/discover.yml) runs each day at 08:23 UTC and can also be started manually. [Publish atlas](https://github.com/zilinzhuang/andes-usage/actions/workflows/pages.yml) validates the reviewed data, builds the public files, and deploys to GitHub Pages. The site reports the last successful search separately from catalog review.

Discovery checks works citing the 2018 and 2021 ANDES papers, OpenAlex text matches, arXiv metadata, and recent Crossref deposits in selected power-system journals. The queue retains DOI or arXiv identifiers, source names, review state, and available arXiv body passages. Inspect a candidate's full paper before accepting it. Set `reviewState` to `excluded` to retain a rejection across future searches. Accepted records are removed from the queue on the next search. Individual provider outcomes appear in [data/status.json](data/status.json).

For local preview, run the following commands from the repository and open `http://localhost:8000/`:

```sh
python scripts/build.py
python -m http.server 8000 --directory _site
```

The world basemap uses [Natural Earth](https://www.naturalearthdata.com/) 1:110m boundary data. The map uses [Leaflet](https://leafletjs.com/) under its [BSD license](assets/vendor/leaflet/LICENSE). The site serves the boundaries and map library locally.
