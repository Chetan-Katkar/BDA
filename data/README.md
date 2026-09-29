# Dataset Guide

This folder documents the data used by the recommendation pipeline in
[`../src/recommendation.py`](../src/recommendation.py).

---

## 1. What is committed here

| File | Size | Committed? | Purpose |
|------|------|-----------|---------|
| `sample_transactions.csv` | ~100 KB | ✅ Yes | Tiny reproducible demo file so the project runs immediately after cloning |
| Full real-world datasets | 45 MB – 1.5 GB | ❌ No | Too large for a coursework repository — download links are below |

> **Important and honest framing:** `sample_transactions.csv` is a small
> **synthetic** file that was generated to imitate the structure of the UCI
> *Online Retail II* export (same eight columns, same kinds of messy rows).
> It exists so that `python src/recommendation.py` works out of the box with no
> download step. It is **not** real customer data, and results produced from it
> are a demonstration of the method, not a measurement of real shopper
> behaviour. To produce meaningful results, point the script at one of the real
> datasets below.

### Schema of `sample_transactions.csv`

| Column | Type | Description |
|--------|------|-------------|
| `InvoiceNo` | string | Order id. A leading `C` marks a cancellation/credit note. |
| `StockCode` | string | Product code — this is the **item** in the recommender. |
| `Description` | string | Human-readable product name. |
| `Quantity` | integer | Units purchased on this line. Negative = return. |
| `InvoiceDate` | timestamp | When the order was placed. |
| `UnitPrice` | double | Price per unit. |
| `CustomerID` | integer | Customer id — this is the **user** in the recommender. May be blank. |
| `Country` | string | Customer's country. |

Contents: **1,152 transaction lines**, **80 customers**, **40 products**, plus
five deliberately invalid rows (a return, a missing customer id, a zero price,
a zero quantity and a `POST` postage line) so that the cleaning stage in the
pipeline visibly has something to remove.

---

## 2. Recommended real dataset — UCI Online Retail II

The closest real-world match to the demo schema, and the recommended dataset
for reproducing this project at a realistic scale.

- **Official page:** <https://archive.ics.uci.edu/dataset/502/online+retail+ii>
- **Direct download:** <https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip>
- **Content:** all transactions of a UK-based, non-store online gift retailer
  between **01/12/2009 and 09/12/2011** — roughly one million transaction lines
  covering several thousand products and customers.
- **Format:** a single `.xlsx` workbook with two sheets
  (`Year 2009-2010` and `Year 2010-2011`).
- **Licence:** Creative Commons Attribution 4.0 (CC BY 4.0).

### How to download and use it

```bash
# 1. Download and unzip into this folder
cd data
curl -LO https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip
unzip online+retail+ii.zip

# 2. Convert the Excel workbook to CSV (the pipeline reads CSV)
pip install pandas openpyxl
python - <<'PY'
import pandas as pd
sheets = pd.read_excel("online_retail_II.xlsx", sheet_name=None)
pd.concat(sheets.values(), ignore_index=True).to_csv(
    "online_retail_II.csv", index=False)
print("written online_retail_II.csv")
PY
```

```bash
# 3. Run the pipeline against it (from the project root)
python src/recommendation.py --data data/online_retail_II.csv --top-n 10
```

The script automatically renames this file's `Invoice`, `Price` and
`Customer ID` columns to `InvoiceNo`, `UnitPrice` and `CustomerID`, so no
manual editing is required.

> On a laptop, expect the full file to take a few minutes. If memory is tight,
> raise the driver memory in `create_spark_session()` or run on a subset.

### Older two-year-shorter version

The original **Online Retail** dataset (541,909 rows, Dec 2010 – Dec 2011) is
also available and works with the same script:
<https://archive.ics.uci.edu/dataset/352/online+retail>

---

## 3. Alternative — Retailrocket recommender system dataset

A genuine clickstream dataset from a live e-commerce site, useful if you want
**view / add-to-cart / purchase** signals rather than just purchases.

- **Page:** <https://www.kaggle.com/datasets/retailrocket/ecommerce-dataset>
- **Content:** 2,756,101 events (2,664,312 views, 69,332 add-to-carts,
  22,457 transactions) from 1,407,580 unique visitors over 4.5 months.
- **Files:** `events.csv`, `item_properties.csv`, `category_tree.csv`.
- **`events.csv` columns:** `timestamp`, `visitorid`, `event`, `itemid`,
  `transactionid`.
- **Note:** all ids are hashed for confidentiality, so product names are not
  available. A Kaggle account is required to download.

Because the column names differ, map them before running:
`visitorid → CustomerID`, `itemid → StockCode`, and derive `Quantity` as a
weight per event type (for example view = 1, add-to-cart = 3, purchase = 5).

---

## 4. Alternative — MovieLens (explicit ratings)

If you want to test the **ALS algorithm itself** with genuine explicit 1–5
ratings rather than derived implicit scores, MovieLens is the standard
benchmark. The ALS method is identical; only the meaning of "item" changes
from a product to a film.

- **Page:** <https://grouplens.org/datasets/movielens/>
- **Small version (100,000 ratings, ~1 MB):**
  <https://files.grouplens.org/datasets/movielens/ml-latest-small.zip>
- **Large version (25 million ratings):**
  <https://files.grouplens.org/datasets/movielens/ml-25m.zip>

---

## 5. Note on committing data

Real datasets are intentionally **not** committed to this repository. The
`.gitignore` excludes `data/*.csv`, `data/*.xlsx` and `data/*.parquet` while
explicitly keeping `sample_transactions.csv`, so any file you download here
stays out of version control automatically.
