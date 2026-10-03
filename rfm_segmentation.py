"""
RFM customer segmentation on the Olist database.
Run AFTER etl_pipeline.py:  python rfm_segmentation.py
Needs: pandas, scikit-learn, matplotlib
"""
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

con = sqlite3.connect("olist.db")

query = """
SELECT c.customer_unique_id,
       MAX(o.order_purchase_timestamp) AS last_order,
       COUNT(DISTINCT o.order_id) AS frequency,
       SUM(oi.price) AS monetary
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.order_status = 'delivered'
GROUP BY c.customer_unique_id
"""
df = pd.read_sql(query, con, parse_dates=["last_order"])

# Recency = days since last order, relative to the latest date in the data
snapshot = df["last_order"].max() + pd.Timedelta(days=1)
df["recency"] = (snapshot - df["last_order"]).dt.days

# Scores 1-5 (5 = best). rank(method="first") avoids qcut errors on ties.
df["R"] = pd.qcut(df["recency"].rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)
df["F"] = pd.qcut(df["frequency"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
df["M"] = pd.qcut(df["monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)


def segment(r):
    if r.R >= 4 and r.F >= 4 and r.M >= 4:
        return "Champions"
    if r.R >= 3 and r.F >= 3:
        return "Loyal"
    if r.R >= 4 and r.F <= 2:
        return "New / Recent"
    if r.R <= 2 and r.F >= 3:
        return "At Risk"
    if r.R <= 2 and r.F <= 2:
        return "Lost"
    return "Needs Attention"


df["segment"] = df.apply(segment, axis=1)

summary = (df.groupby("segment")
             .agg(customers=("customer_unique_id", "count"),
                  avg_recency=("recency", "mean"),
                  avg_frequency=("frequency", "mean"),
                  total_revenue=("monetary", "sum"))
             .round(1))
summary["revenue_share_pct"] = (100 * summary["total_revenue"] / summary["total_revenue"].sum()).round(1)
print(summary.sort_values("total_revenue", ascending=False))

# Optional: KMeans clustering on log-scaled RFM values
import numpy as np
X = StandardScaler().fit_transform(np.log1p(df[["recency", "frequency", "monetary"]]))
df["cluster"] = KMeans(n_clusters=4, random_state=42, n_init=10).fit_predict(X)
print("\nKMeans cluster profile:")
print(df.groupby("cluster")[["recency", "frequency", "monetary"]].mean().round(1))

# Chart for the README
summary["customers"].sort_values().plot(kind="barh", color="#4C78A8")
plt.title("Customers per RFM Segment")
plt.xlabel("Customers")
plt.tight_layout()
plt.savefig("rfm_segments.png", dpi=150)
print("\nSaved rfm_segments.png and segment summary above.")

df.to_sql("rfm_segments", con, if_exists="replace", index=False)
con.close()
