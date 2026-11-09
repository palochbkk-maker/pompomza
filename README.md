# Travian Artifact Planner

Static site: `index.html` + `config/` + `data/`. A daily GitHub Action refreshes `data/*.json` from each server's map.sql.

## Add a server
1. Add `{"id": "tsXX.x1.europe.travian.com", "label": "Europe XX"}` to `config/servers.json`.
2. (Optional) add its confederacies to `config/confederacies.json`.
3. Run the "Update map data" workflow once (Actions tab → Run workflow).

## Test locally
    python scripts/build_data.py --file map.sql --server ts21.x2.asia.travian.com
    python -m http.server 8000      # then open http://localhost:8000
