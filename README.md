# ANDES Usage Atlas

[Explore the atlas](https://zilinzhuang.github.io/andes-usage/)

A searchable index and world map of research papers that document using the [ANDES power system simulator](https://docs.andes.app/). This independent catalog is maintained by Zilin Zhuang. The index starts with a reviewed selection and grows as further papers are verified.

## Reading the map

Markers locate the author affiliations of included studies, approximately at the institution or city level. Select an institution to filter its publications. Papers with several affiliations appear at several places but count once in the total. A verified paper whose authors omit their affiliations still appears in the publication list, with no map marker. The list runs from newest to oldest. Each record gives a use summary and a link to the relevant section, figure, or supporting material.

## Inclusion and corrections

Include a study when the authors' methods, results, figures, or associated research code identify an actual ANDES calculation, simulation, implementation, data generation step, or benchmark in that study. A citation, background discussion, or mention of the larger CURENT testbed by itself is insufficient. Record the original source URL and a precise locator, and summarize the work in your own words. List affiliations as published. Only count organizations whose authors contributed to the paper, regardless of where a dataset or computing facility was hosted.

Keep one record for a preprint and its published version. Prefer the publisher's first online publication date where documented. If only a month or year is known, retain that precision. Mark preprints explicitly.

- [Suggest a paper or report a correction](https://github.com/zilinzhuang/andes-usage/issues/new). Provide the paper title, DOI or stable URL, evidence location, and the relevant institution.
- [data/papers.json](data/papers.json) holds the verified papers and their affiliations. [data/candidates.json](data/candidates.json) preserves leads and exclusions from the previous search. The atlas reads its publication counts from the verified catalog.

## Updating the catalog on demand

The maintainer starts a literature search in ChatGPT or another research assistant whenever an update is useful. The assistant can search for new and previously missed papers, check the original evidence, and prepare the update as one batch. Before editing, read the latest catalog, match existing works by DOI, arXiv ID and title, and reuse existing institution IDs. When a preprint has been published, update the existing record. For a new institution, use the author's published affiliation and verified location. Keep a paper with no stated affiliation in the catalog with an empty `institutions` array.

Update `reviewedThrough` when the evidence review is complete. For a completed literature search, record its actual UTC completion time in `lastSuccessfulSearch` in [data/status.json](data/status.json). The previous provider-specific records retain their original timestamps. A metadata correction alone changes no search date. Validate changes with `python scripts/build.py` before publishing. An assistant with repository write access can submit the requested update. In a read-only chat, ask for a patch against the current catalog to apply later.

### Repeatable Task

> Update the ANDES Usage Atlas (<https://github.com/zilinzhuang/andes-usage>). Start by reading the latest README and `data/papers.json`. Search for newly published papers and earlier studies the atlas may have missed.
>
> For each paper, check the full text, figures, tables, or accompanying research code. Include a paper only when the evidence shows that the authors used ANDES in that study. Briefly describe in English what they used ANDES for. Link to the original source and give the section, page, figure, or code location where the use is documented.
>
> Check for duplicates by DOI, arXiv ID, and title. Merge each preprint and its published version into a single record. Verify institutional affiliations against those listed in the paper. Preserve the existing website template and data format.
>
> If you have write access to the repository, validate the data, commit the update, and verify that the changes appear on the live site. If you have read-only access, return a patch that applies to the current repository. Finish by listing the papers added, the records corrected, and any candidates for which the evidence was insufficient.

## Publishing

[Publish atlas](https://github.com/zilinzhuang/andes-usage/actions/workflows/pages.yml) validates and publishes the site after relevant changes reach `main`. The dates shown in the footer identify the most recent evidence review and the most recent completed search. There is no scheduled literature search.

For local preview, run the following commands from the repository and open `http://localhost:8000/`:

```sh
python scripts/build.py
python -m http.server 8000 --directory _site
```

The world basemap uses [Natural Earth](https://www.naturalearthdata.com/) 1:110m boundary data. The map uses [Leaflet](https://leafletjs.com/) under its [BSD license](assets/vendor/leaflet/LICENSE). The site serves the boundaries and map library locally.
