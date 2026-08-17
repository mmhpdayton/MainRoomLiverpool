# Main Room Liverpool

A Liverpool FC matchday dashboard built for a group chat: full fixtures/results, U.S. broadcast information, Premier League and Champions League tables, Liverpool weather, and curated news.

## Data refresh
A GitHub Actions workflow runs hourly and refreshes `site-data.json` using public sports endpoints and curated news feeds. Confirmed U.S. TV assignments can be overridden in `site-data.json` and are preserved by the updater when the upstream feed has no channel.

## GitHub Pages
Serve the repository root from GitHub Pages. The site is static and requires no server.