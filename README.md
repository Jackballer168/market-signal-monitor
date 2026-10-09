# Market Signal Monitor

A small, no-key news discovery tool for markets, business, politics, and the economy. It collects recent article links from the [GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) and official RSS feeds, removes repeat URLs, keeps a rolling archive, and builds a searchable static dashboard. Headlines link to the original publisher; the tool does not copy full articles or make investment recommendations.

## Run locally

Requires Python 3.10+ and an internet connection. No packages or API keys are needed.

```bash
python monitor.py
python -m http.server 8000 --directory docs
```

Open `http://localhost:8000` to browse the dashboard. `docs/stories.json` is also available for your own analysis or integrations. The archive lives in `data/articles.json`. Run `python -m unittest discover -s tests` to check parsing, deduplication, and HTML escaping.

## Put it on GitHub

1. Create an empty GitHub repository and push this directory to its default branch.
2. In **Settings → Actions → General → Workflow permissions**, allow **Read and write permissions** if your repository does not already allow it.
3. In **Actions**, run **Refresh news** once. The workflow also runs about every six hours (scheduled runs can be delayed).
4. To publish the dashboard, choose **Settings → Pages → Build and deployment → Deploy from a branch**, select the default branch and `/docs` folder. The dashboard will appear at your repository's GitHub Pages URL. The repository and Pages site are public if you use a public repository.

The scheduled workflow commits refreshed results. If branch protection blocks the bot's push, adjust that rule or run the tool outside Actions and commit the output yourself.

## Customize

Edit `config.json` to change the GDELT queries, categories, RSS feeds, lookback window, and archive size. GDELT query syntax supports exact phrases, Boolean `OR`, language and domain filters. The default searches use English-language results from a global index. The official Federal Reserve monetary policy feed adds direct policy releases. To use another RSS feed, add its URL, source name, and category under `feeds`.

This is a headline discovery feed, not a complete crawl of the internet or a live quote terminal. GDELT coverage, indexing times, relevance, publisher availability, and API response may vary. A failed source is noted on the dashboard and the previous archive stays visible. Verify market-moving claims against the linked publication and primary releases before relying on them.
