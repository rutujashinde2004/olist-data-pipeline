"""
Generates SAMPLE (synthetic) data with the exact same file names and columns as the
real Olist Kaggle dataset, so the whole pipeline runs end to end without a download.

Run:  python generate_sample_data.py
NOTE: Numbers from this data are NOT real. For real insights, replace the CSVs in
data/raw/ with the real Olist files from Kaggle (same file names) and re-run.
"""
import os
import uuid
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
OUT = "data/raw"
os.makedirs(OUT, exist_ok=True)

N_CUSTOMERS = 8000
N_ORDERS = 12000
N_SELLERS = 150
N_PRODUCTS = 1500


def ids(n):
    return [uuid.uuid4().hex for _ in range(n)]


states = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF", "GO", "PE"]
state_p = np.array([40, 13, 12, 6, 6, 4, 4, 3, 3, 3], dtype=float)
state_p /= state_p.sum()
cities = {"SP": "sao paulo", "RJ": "rio de janeiro", "MG": "belo horizonte", "RS": "porto alegre",
          "PR": "curitiba", "SC": "florianopolis", "BA": "salvador", "DF": "brasilia",
          "GO": "goiania", "PE": "recife"}

# ---- customers (customer_id is per order, customer_unique_id is the real person)
unique_ids = ids(N_CUSTOMERS)
# some people order more often (repeat customers)
person_weights = rng.pareto(3.0, N_CUSTOMERS) + 1
person_weights /= person_weights.sum()
order_person = rng.choice(N_CUSTOMERS, N_ORDERS, p=person_weights)
# make sure every person ordered at least once for first N_CUSTOMERS orders
order_person[:N_CUSTOMERS] = np.arange(N_CUSTOMERS)
rng.shuffle(order_person)
person_state = rng.choice(states, N_CUSTOMERS, p=state_p)
person_zip = rng.integers(1000, 99999, N_CUSTOMERS)

customer_ids = ids(N_ORDERS)
customers = pd.DataFrame({
    "customer_id": customer_ids,
    "customer_unique_id": [unique_ids[i] for i in order_person],
    "customer_zip_code_prefix": [person_zip[i] for i in order_person],
    "customer_city": [cities[person_state[i]] for i in order_person],
    "customer_state": [person_state[i] for i in order_person],
})

# ---- sellers
seller_ids = ids(N_SELLERS)
seller_state = rng.choice(states, N_SELLERS, p=state_p)
seller_quality = rng.normal(0, 1, N_SELLERS)  # hidden quality, drives lateness + reviews
sellers = pd.DataFrame({
    "seller_id": seller_ids,
    "seller_zip_code_prefix": rng.integers(1000, 99999, N_SELLERS),
    "seller_city": [cities[s] for s in seller_state],
    "seller_state": seller_state,
})

# ---- products
cats_pt = ["beleza_saude", "cama_mesa_banho", "esporte_lazer", "informatica_acessorios",
           "moveis_decoracao", "utilidades_domesticas", "relogios_presentes", "telefonia",
           "brinquedos", "automotivo", "livros_tecnicos", "perfumaria"]
cats_en = ["health_beauty", "bed_bath_table", "sports_leisure", "computers_accessories",
           "furniture_decor", "housewares", "watches_gifts", "telephony",
           "toys", "auto", "technical_books", "perfumery"]
product_ids = ids(N_PRODUCTS)
products = pd.DataFrame({
    "product_id": product_ids,
    "product_category_name": rng.choice(cats_pt, N_PRODUCTS),
    "product_name_lenght": rng.integers(20, 70, N_PRODUCTS),
    "product_description_lenght": rng.integers(100, 2000, N_PRODUCTS),
    "product_photos_qty": rng.integers(1, 8, N_PRODUCTS),
    "product_weight_g": rng.integers(100, 8000, N_PRODUCTS),
    "product_length_cm": rng.integers(10, 80, N_PRODUCTS),
    "product_height_cm": rng.integers(5, 50, N_PRODUCTS),
    "product_width_cm": rng.integers(10, 60, N_PRODUCTS),
})
# a few missing categories, like the real data
products.loc[rng.choice(N_PRODUCTS, 25, replace=False), "product_category_name"] = np.nan
product_price = np.round(rng.lognormal(4.2, 0.9, N_PRODUCTS) + 5, 2)

translation = pd.DataFrame({"product_category_name": cats_pt, "product_category_name_english": cats_en})

# ---- orders
start = pd.Timestamp("2017-01-01")
days = (rng.beta(2.0, 1.4, N_ORDERS) * 640).astype(int)  # growth over time
purchase = start + pd.to_timedelta(days, unit="D") + pd.to_timedelta(rng.integers(0, 86400, N_ORDERS), unit="s")
status = rng.choice(["delivered", "shipped", "canceled", "processing", "unavailable"],
                    N_ORDERS, p=[0.965, 0.012, 0.012, 0.006, 0.005])

# each order has 1-3 items from sellers
n_items = rng.choice([1, 2, 3], N_ORDERS, p=[0.80, 0.15, 0.05])
order_ids = ids(N_ORDERS)
order_seller_idx = rng.integers(0, N_SELLERS, N_ORDERS)  # primary seller per order

est_days = rng.integers(12, 40, N_ORDERS)
late_prob = 1 / (1 + np.exp(-(-2.6 + 0.8 * seller_quality[order_seller_idx])))
is_late_flag = rng.random(N_ORDERS) < late_prob
actual_days = np.where(is_late_flag, est_days + rng.integers(1, 15, N_ORDERS),
                       np.maximum(3, est_days - rng.integers(1, 12, N_ORDERS)))
approved = purchase + pd.to_timedelta(rng.integers(600, 40000, N_ORDERS), unit="s")
carrier = approved + pd.to_timedelta(rng.integers(1, 4, N_ORDERS), unit="D")
delivered = purchase + pd.to_timedelta(actual_days, unit="D")

orders = pd.DataFrame({
    "order_id": order_ids,
    "customer_id": customer_ids,
    "order_status": status,
    "order_purchase_timestamp": purchase.strftime("%Y-%m-%d %H:%M:%S"),
    "order_approved_at": approved.strftime("%Y-%m-%d %H:%M:%S"),
    "order_delivered_carrier_date": carrier.strftime("%Y-%m-%d %H:%M:%S"),
    "order_delivered_customer_date": delivered.strftime("%Y-%m-%d %H:%M:%S"),
    "order_estimated_delivery_date": (purchase + pd.to_timedelta(est_days, unit="D")).strftime("%Y-%m-%d %H:%M:%S"),
})
not_delivered = orders["order_status"] != "delivered"
orders.loc[not_delivered, "order_delivered_customer_date"] = np.nan
orders.loc[orders["order_status"].isin(["canceled", "unavailable", "processing"]),
           "order_delivered_carrier_date"] = np.nan

# ---- order_items
rows = []
for i in range(N_ORDERS):
    for k in range(1, n_items[i] + 1):
        pidx = rng.integers(0, N_PRODUCTS)
        sidx = order_seller_idx[i] if rng.random() < 0.9 else rng.integers(0, N_SELLERS)
        price = product_price[pidx]
        rows.append((order_ids[i], k, product_ids[pidx], seller_ids[sidx],
                     (carrier[i] + pd.Timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
                     price, round(float(rng.uniform(7, 40)), 2)))
order_items = pd.DataFrame(rows, columns=["order_id", "order_item_id", "product_id", "seller_id",
                                          "shipping_limit_date", "price", "freight_value"])

# ---- payments
tot = order_items.groupby("order_id")[["price", "freight_value"]].sum().sum(axis=1)
payments = pd.DataFrame({
    "order_id": order_ids,
    "payment_sequential": 1,
    "payment_type": rng.choice(["credit_card", "boleto", "voucher", "debit_card"], N_ORDERS,
                               p=[0.74, 0.19, 0.05, 0.02]),
    "payment_installments": rng.choice([1, 2, 3, 4, 6, 10], N_ORDERS, p=[0.5, 0.12, 0.1, 0.08, 0.1, 0.1]),
    "payment_value": np.round([tot[o] for o in order_ids], 2),
})

# ---- reviews: late delivery and bad sellers lower the score
base = 4.5 - 2.0 * is_late_flag - 0.3 * (-seller_quality[order_seller_idx]).clip(0, None) \
       + rng.normal(0, 0.9, N_ORDERS)
score = np.clip(np.round(base), 1, 5).astype(int)
has_review = rng.random(N_ORDERS) < 0.98
rev_idx = np.where(has_review)[0]
reviews = pd.DataFrame({
    "review_id": ids(len(rev_idx)),
    "order_id": [order_ids[i] for i in rev_idx],
    "review_score": score[rev_idx],
    "review_comment_title": np.nan,
    "review_comment_message": np.nan,
    "review_creation_date": (delivered[rev_idx] + pd.Timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
    "review_answer_timestamp": (delivered[rev_idx] + pd.Timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"),
})
# add a few duplicate reviews per order to mimic real data messiness
dup = reviews.sample(200, random_state=1).copy()
dup["review_id"] = ids(len(dup))
reviews = pd.concat([reviews, dup], ignore_index=True)

# ---- geolocation (with duplicates, like real data)
zips = np.unique(np.concatenate([customers["customer_zip_code_prefix"], sellers["seller_zip_code_prefix"]]))
geo = pd.DataFrame({
    "geolocation_zip_code_prefix": np.repeat(zips, 3),
    "geolocation_lat": rng.uniform(-30, -3, len(zips) * 3),
    "geolocation_lng": rng.uniform(-60, -35, len(zips) * 3),
    "geolocation_city": "sao paulo",
    "geolocation_state": "SP",
})

files = {
    "olist_customers_dataset.csv": customers,
    "olist_sellers_dataset.csv": sellers,
    "olist_products_dataset.csv": products,
    "product_category_name_translation.csv": translation,
    "olist_orders_dataset.csv": orders,
    "olist_order_items_dataset.csv": order_items,
    "olist_order_payments_dataset.csv": payments,
    "olist_order_reviews_dataset.csv": reviews,
    "olist_geolocation_dataset.csv": geo,
}
for name, df in files.items():
    df.to_csv(os.path.join(OUT, name), index=False)
    print(f"{name:<45}{len(df):>8,} rows")
print("\nSample data written to data/raw/ (synthetic, not real Olist data).")
