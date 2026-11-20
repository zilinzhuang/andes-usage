import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import discover


class DiscoveryTests(unittest.TestCase):
    def test_anonymous_openalex_uses_basic_pages_within_reported_count(self):
        def fetch(path, *, page, per_page, **query):
            self.assertNotIn("cursor", query)
            self.assertEqual(per_page, 100)
            work = {"display_name": f"Work on page {page}", "id": f"https://openalex.org/W{page}"}
            return {"meta": {"count": 101}, "results": [work] * (100 if page == 1 else 1)}
        with patch.object(discover, "oa_request", side_effect=fetch) as mocked:
            records = discover.oa_results(filter="cites:W1")
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(len(records), 101)
        self.assertEqual(records[-1]["openalexId"], "W2")

    def test_crossref_finds_references_when_titles_and_abstracts_omit_software(self):
        relevant = {"DOI": "10.1111/ABC", "title": ["Testing a controller"], "published": {"date-parts": [[2024, 5]]},
                    "reference": [{"DOI": discover.SEED_DOIS[0].lower()}]}
        irrelevant = {"DOI": "10.1111/xyz", "title": ["Unrelated dynamics"]}
        response = json.dumps({"message": {"items": [relevant, irrelevant], "total-results": 2}}).encode()
        with patch.object(discover, "get", return_value=response) as mocked:
            records = discover.crossref_recent("2026-11-01")
        self.assertEqual(mocked.call_count, 4)
        self.assertTrue(all(r["doi"] == "10.1111/abc" and r["date"] == "2024-05" for r in records))
        self.assertEqual(len(records), 4)

    def test_verified_versions_excluded_and_editorial_decisions_remain(self):
        title = "A comprehensive application of symbolic power system models"
        verified = [{"title": title, "url": "https://arxiv.org/html/2401.11111v2"}]
        again = {"title": "A new title for the same preprint", "arxivId": "2401.11111"}
        excluded = {"title": "A background-only citation in a comparison of simulators",
                    "doi": "10.1234/x", "sources": ["OpenAlex citations"], "reviewState": "excluded"}
        candidate = {"title": "A different record with enough words to identify it", "doi": "10.1122/new"}
        sources = {"OpenAlex citations": [again, candidate], "arXiv metadata": [
            {**candidate, "arxivId": "2410.01234"}, {**excluded, "doi": "https://doi.org/10.1234/X"}]}
        queue = discover.update_queue([excluded], verified, sources, "2026-11-20")
        self.assertEqual(len(queue), 2)
        matched = next(r for r in queue if r["reviewState"] == "pending")
        self.assertEqual(matched["arxivId"], "2410.01234")
        self.assertEqual(matched["sources"], ["OpenAlex citations", "arXiv metadata"])
        self.assertEqual(excluded["reviewState"], "excluded")
        self.assertEqual(queue, discover.update_queue(queue, verified, sources, "2026-11-21"))

    def test_hint_from_body_excludes_abstract_and_reference(self):
        p = discover.BodyParagraphs()
        p.feed('<h2>Abstract</h2><p>We mention ANDES here.</p>'
               '<section id="S4"><h2>IV Numerical experiments</h2><div id="S4.p2">'
               '<p>A time-domain simulation was performed with <em>ANDES</em> on the benchmark.</p></div></section>'
               '<h2>References</h2><p>H. Cui. ANDES simulator.</p>')
        self.assertEqual(len(p.matches), 1)
        self.assertEqual(p.matches[0][2:], ("IV Numerical experiments", "S4.p2"))
        self.assertIn("with ANDES", p.matches[0][1])

    def test_source_failure_preserves_success_time_and_queue(self):
        with tempfile.TemporaryDirectory() as base:
            folder = Path(base) / "data"
            folder.mkdir()
            for filename, content in {
                "papers.json": {"papers": []}, "candidates.json": {"candidates": []},
                "status.json": {"lastSuccessfulSearch": "2025-01-01T00:00:00Z", "sources": {}},
            }.items():
                (folder / filename).write_text(json.dumps(content), encoding="utf-8")
            with (patch.object(discover, "ROOT", Path(base)), patch.object(discover, "collect_hints"),
                  patch.object(discover, "citing_works", side_effect=RuntimeError("limited")),
                  patch.object(discover, "crossref_recent", return_value=[]),
                  patch.object(discover, "software_mentions", return_value=[]),
                  patch.object(discover, "arxiv_mentions", return_value=[])):
                discover.main()
            status = discover.read(folder / "status.json")
            self.assertEqual(status["outcome"], "partial")
            self.assertEqual(status["lastSuccessfulSearch"], "2025-01-01T00:00:00Z")
            with (patch.object(discover, "ROOT", Path(base)),
                  patch.object(discover, "citing_works", side_effect=ValueError()),
                  patch.object(discover, "crossref_recent", side_effect=ValueError()),
                  patch.object(discover, "software_mentions", side_effect=ValueError()),
                  patch.object(discover, "arxiv_mentions", side_effect=ValueError())):
                with self.assertRaises(SystemExit):
                    discover.main()
            self.assertEqual(status, discover.read(folder / "status.json"))


if __name__ == "__main__":
    unittest.main()
