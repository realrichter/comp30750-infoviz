"""Data processing for the Ireland export-boom dashboard.

Source: CSO table TSM10 - Value of Merchandise Trade, monthly,
        by SITC commodity division (66 groups) x partner country (49), in EUR thousand.
        https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/TSM10/JSON-stat/2.0/en

Transformations (all documented in README.md / DESIGN.md):
  1. JSON-stat cube -> tidy rows (month, partner, commodity, exports, imports).
  2. EUR thousand -> EUR million.
  3. 64 SITC divisions -> 9 readable commodity groups (pharma 54 and organic chemicals 51 kept separate).
     The "Other" group is the residual (total - named groups) so every month adds up to the CSO total.
  4. Great Britain + Northern Ireland -> United Kingdom; "EU country not specified" + "Other countries"
     + every partner outside the top 20 (by 2015-2026 total trade) -> "Rest of world".
  5. Rows where both exports and imports round to 0 are dropped.

Run:  python process.py            (uses data/raw/tsm10.json if present, otherwise downloads it)
Out:  data/monthly_trade.csv, data/partner_rank.csv
"""
import csv
import json
import os
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw", "tsm10.json")
URL = "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/TSM10/JSON-stat/2.0/en"
TOP_N = 20

# SITC division code -> commodity group shown in the dashboard
GROUPS = [
    ("Medicines & pharma (54)", ["54"]),
    ("Organic chemicals (51)", ["51"]),
    ("Other chemicals (52-59)", ["52", "53", "55", "56", "57", "58", "59"]),
    ("Computers & electronics (75-77)", ["75", "76", "77"]),
    ("Aircraft & vehicles (78-79)", ["78", "79"]),
    ("Other machinery (71-74)", ["71", "72", "73", "74"]),
    ("Medical devices & instruments (87-89)", ["87", "88", "89"]),
    ("Food, drink & animals (00-12)", ["00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "11", "12"]),
]
OTHER = "Other goods (residual)"
DIV2GROUP = {code: name for name, codes in GROUPS for code in codes}
MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"])}
PARTNER_MERGE = {"Great Britain": "United Kingdom", "Northern Ireland": "United Kingdom",
                 "USA": "United States", "EU country not specified": "Rest of world",
                 "Other countries": "Rest of world"}


def load():
    if not os.path.exists(RAW):
        os.makedirs(os.path.dirname(RAW), exist_ok=True)
        urllib.request.urlretrieve(URL, RAW)
    with open(RAW, encoding="utf-8") as f:
        return json.load(f)


def main():
    d = load()
    ids, size, val = d["id"], d["size"], d["value"]
    cats = [list(d["dimension"][k]["category"]["index"]) for k in ids]
    labs = [d["dimension"][k]["category"].get("label", {}) for k in ids]
    stat_lab = [labs[0][c] for c in cats[0]]
    s_exp, s_imp = stat_lab.index("Value of Exports"), stat_lab.index("Value of Imports")

    def code_of(label):  # "Organic chemicals (51)" -> "51"
        return label.rsplit("(", 1)[-1].rstrip(")").strip() if "(" in label else None

    com_codes = [code_of(labs[2][c]) for c in cats[2]]
    total_idx = [i for i, c in enumerate(cats[2]) if labs[2][c].startswith("Total")][0]
    partners = [PARTNER_MERGE.get(labs[3][c], labs[3][c]) for c in cats[3]]

    def v(s, m, c, p):
        x = val[((s * size[1] + m) * size[2] + c) * size[3] + p]
        return (x or 0) / 1000.0  # EUR thousand -> EUR million

    # cell[(year, month, partner, group)] = [exp, imp]
    cell = defaultdict(lambda: [0.0, 0.0])
    for mi, mcode in enumerate(cats[1]):
        year_s, month_s = labs[1][mcode].split()
        y, mo = int(year_s), MONTHS[month_s]
        for pi, pname in enumerate(partners):
            named = [0.0, 0.0]
            for ci, code in enumerate(com_codes):
                g = DIV2GROUP.get(code)
                if g is None:
                    continue
                e, i = v(s_exp, mi, ci, pi), v(s_imp, mi, ci, pi)
                cell[(y, mo, pname, g)][0] += e
                cell[(y, mo, pname, g)][1] += i
                named[0] += e
                named[1] += i
            te, ti = v(s_exp, mi, total_idx, pi), v(s_imp, mi, total_idx, pi)
            cell[(y, mo, pname, OTHER)][0] += te - named[0]
            cell[(y, mo, pname, OTHER)][1] += ti - named[1]

    # rank partners by total trade over the whole period; fold the tail into Rest of world
    tot = defaultdict(float)
    for (y, mo, p, g), (e, i) in cell.items():
        tot[p] += e + i
    ranked = [p for p in sorted(tot, key=tot.get, reverse=True) if p != "Rest of world"]
    keep = set(ranked[:TOP_N])
    final = defaultdict(lambda: [0.0, 0.0])
    for (y, mo, p, g), (e, i) in cell.items():
        k = (y, mo, p if p in keep else "Rest of world", g)
        final[k][0] += e
        final[k][1] += i

    rows = []
    for (y, mo, p, g), (e, i) in sorted(final.items()):
        e, i = round(e, 1), round(i, 1)
        if abs(e) < 0.05 and abs(i) < 0.05:
            continue
        rows.append({"y": y, "mo": mo, "p": p, "c": g, "e": e, "i": i})

    out = os.path.join(HERE, "data")
    with open(os.path.join(out, "monthly_trade.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["year", "month", "partner", "goods", "exports", "imports"])  # values in EUR million
        for r in rows:
            w.writerow([r["y"], r["mo"], r["p"], r["c"], r["e"], r["i"]])
    with open(os.path.join(out, "partner_rank.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["partner", "rank", "total_trade"])
        for r, p in enumerate(ranked[:TOP_N], 1):
            w.writerow([p, r, round(tot[p], 1)])
    print(f"{len(rows)} rows; months {rows[0]['y']}-{rows[0]['mo']:02d} .. {rows[-1]['y']}; "
          f"top partners: {ranked[:TOP_N]}")


if __name__ == "__main__":
    main()
