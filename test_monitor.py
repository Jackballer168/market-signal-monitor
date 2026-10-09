import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from monitor import canonical_url, merge, parse_gdelt, parse_rss, render, run


class MonitorTests(unittest.TestCase):
    def test_gdelt_and_rss_parsing(self):
        data = {"articles": [{"url": "https://example.com/story?utm_source=a", "title": "Market rises", "domain": "example.com", "seendate": "20261009T120000Z"}]}
        article = parse_gdelt(json.dumps(data).encode(), "Markets")[0]
        self.assertEqual(article["url"], "https://example.com/story")
        self.assertEqual(article["published"], "2026-10-09T12:00:00+00:00")
        rss = b"<rss><channel><item><title>Rate decision</title><link>https://fed.example/rates</link><pubDate>Fri, 09 Oct 2026 12:00:00 GMT</pubDate></item></channel></rss>"
        self.assertEqual(parse_rss(rss, "Fed", "Economy")[0]["published"], "2026-10-09T12:00:00+00:00")

    def test_dedupe_and_escape(self):
        item = {"title": "<script>alert(1)</script>", "url": "https://example.com/a", "source": "News", "published": "2026-10-09T12:00:00+00:00", "category": "Markets"}
        self.assertEqual(len(merge([item], [{**item, "url": "https://example.com/a?utm_medium=x"}], 10)), 1)
        page = render([item], "2026-10-09", [], ["Markets"])
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertEqual(canonical_url("javascript:alert(1)"), "")

    def test_end_to_end_with_mock_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            config.write_text(json.dumps({"categories": {"Markets": "stocks"}, "feeds": [], "lookback": "24h", "max_records_per_category": 10, "max_archive_items": 100}))
            payload = json.dumps({"articles": [{"url": "https://example.com/a", "title": "Stocks rise", "domain": "example.com", "seendate": "20261009T120000Z"}]}).encode()
            with patch("monitor.fetch", return_value=payload):
                self.assertEqual(run(config, root / "docs", root / "data/articles.json"), 0)
            self.assertIn("Stocks rise", (root / "docs/index.html").read_text())
            self.assertEqual(len(json.loads((root / "docs/stories.json").read_text())["stories"]), 1)
            self.assertEqual(len(json.loads((root / "data/articles.json").read_text())), 1)


if __name__ == "__main__":
    unittest.main()
