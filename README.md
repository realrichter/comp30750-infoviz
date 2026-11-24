# Ireland's Export Rush

**How much of Ireland's export boom was one product going to one country?**

An interactive Vega-Lite dashboard of Ireland's monthly merchandise trade (CSO table TSM10,
Jan 2015 – Sep 2026), built for COMP30750 Information Visualisation.

## Run locally
The spec loads its data by URL, so serve the folder rather than opening the file directly:
```
python -m http.server
```
Then open http://localhost:8000.

## Files
```
index.html             dashboard page (loads dashboard.vl.json with vega-embed)
dashboard.vl.json      Vega-Lite specification
DESIGN.md              design document
process.py             data processing: CSO TSM10 JSON-stat -> data/monthly_trade.csv
data/monthly_trade.csv processed data: year, month, partner, goods, exports, imports (EUR million)
data/partner_rank.csv  top 20 partners by 2015-26 total trade (orders the heatmap rows)
data/partner_tiles.csv tile-map positions (code, column, row) for the 20 partners
data/raw/tsm10.json    raw CSO download used to build the processed data
```

## Data processing
Source: CSO PxStat API, `https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/TSM10/JSON-stat/2.0/en`.
Regenerate with `python process.py` (uses `data/raw/tsm10.json`, or downloads it if missing).

- € thousand → € million.
- 64 SITC divisions → 9 goods classes. "Other goods" is the residual of the CSO total, so monthly sums
  match the published figures (2025 exports: €257.1bn).
- Great Britain + Northern Ireland → United Kingdom. Partners outside the top 20, "EU country not
  specified" and "Other countries" → Rest of world.
- Rows where both values are zero are dropped (26,518 rows remain).
