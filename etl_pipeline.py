"""
Olist E-Commerce ETL Pipeline
Extract 9 raw CSVs -> Transform (clean, derive features) -> Load into SQLite with indexes.

Run:  python etl_pipeline.py
Needs: data/raw/ folder containing the Olist CSV files from Kaggle.
"""
import os
import sqlite3
import pandas as pd

RAW = "data/raw"
DB = "olist.db"


def p(name):
    return os.path.join(RAW, name)


# ---------------- EXTRACT ----------------
def extract():
    print("[1/3] Extracting CSVs...")
    return {
        "orders": pd.read_csv(p("olist_orders_dataset.csv")),
        "customers": pd.read_csv(p("olist_customers_dataset.csv")),
        "order_items": pd.read_csv(p("olist_order_items_dataset.csv")),
        "payments": pd.read_csv(p("olist_order_payments_dataset.csv")),
        "reviews": pd.read_csv(p("olist_order_reviews_dataset.csv")),
        "products": pd.read_csv(p("olist_products_dataset.csv")),
        "sellers": pd.read_csv(p("olist_sellers_dataset.csv")),
        "geolocation": pd.read_csv(p("olist_geolocation_dataset.csv")),
        "category_translation": pd.read_csv(p("product_category_name_translation.csv")),
    }


# ---------------- TRANSFORM ----------------
def transform(t):
    print("[2/3] Transforming / cleaning...")

    # Orders: parse dates, derive delivery_days and is_late
    o = t["orders"].drop_duplicates("order_id").copy()
    date_cols = [
        "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]
    for c in date_cols:
        o[c] = pd.to_datetime(o[c], errors="coerce")
    o["delivery_days"] = (
        o["order_delivered_customer_date"] - o["order_purchase_timestamp"]
    ).dt.days
    o["is_late"] = (
        o["order_delivered_customer_date"] > o["order_estimated_delivery_date"]
    ).astype(int)
    t["orders"] = o

    # Customers / sellers: drop duplicates
    t["customers"] = t["customers"].drop_duplicates("customer_id")
    t["sellers"] = t["sellers"].drop_duplicates("seller_id")

    # Order items: parse date, drop duplicates
    oi = t["order_items"].drop_duplicates(["order_id", "order_item_id"]).copy()
    oi["shipping_limit_date"] = pd.to_datetime(oi["shipping_limit_date"], errors="coerce")
    t["order_items"] = oi

    # Products: translate category to English, fill missing
    pr = t["products"].drop_duplicates("product_id").merge(
        t["category_translation"], on="product_category_name", how="left"
    )
    pr["product_category_name_english"] = pr["product_category_name_english"].fillna("unknown")
    t["products"] = pr[["product_id", "product_category_name",
                        "product_category_name_english", "product_weight_g"]]

    # Reviews: keep one (latest) review per order
    rv = t["reviews"].copy()
    rv["review_answer_timestamp"] = pd.to_datetime(rv["review_answer_timestamp"], errors="coerce")
    rv = (rv.sort_values("review_answer_timestamp")
            .drop_duplicates("order_id", keep="last")[["review_id", "order_id", "review_score"]])
    t["reviews"] = rv

    # Geolocation: one row per zip prefix (raw file has ~1M duplicate rows)
    t["geolocation"] = (
        t["geolocation"].groupby("geolocation_zip_code_prefix", as_index=False)
        .agg(lat=("geolocation_lat", "mean"), lng=("geolocation_lng", "mean"),
             city=("geolocation_city", "first"), state=("geolocation_state", "first"))
    )

    t.pop("category_translation")
    return t


# ---------------- LOAD ----------------
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_items_order ON order_items(order_id)",
    "CREATE INDEX IF NOT EXISTS idx_items_product ON order_items(product_id)",
    "CREATE INDEX IF NOT EXISTS idx_items_seller ON order_items(seller_id)",
    "CREATE INDEX IF NOT EXISTS idx_reviews_order ON reviews(order_id)",
    "CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id)",
]


def load(t):
    print("[3/3] Loading into SQLite...")
    if os.path.exists(DB):
        os.remove(DB)
    con = sqlite3.connect(DB)
    for name, df in t.items():
        df.to_sql(name, con, index=False)
        print(f"   {name:<14} {len(df):>8,} rows")
    # NOTE: for the "before/after index" demo in analysis_queries.sql (query 8),
    # comment out the INDEXES loop, run the demo, then create the indexes.
    for stmt in INDEXES:
        con.execute(stmt)
    con.commit()
    con.close()
    print(f"Done. Database saved as {DB}")


if __name__ == "__main__":
    load(transform(extract()))
