"""
Runs every query in analysis_queries.sql against olist.db, prints the results,
saves each result as results/qN.csv, and demos the index speed-up (Q8).

Run:  python run_queries.py
"""
import os
import re
import sqlite3
import time
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)

con = sqlite3.connect("olist.db")
os.makedirs("results", exist_ok=True)

sql = open("analysis_queries.sql", encoding="utf-8").read()
n = 0
# pair each "-- Qn. title" header with the SQL that follows it
for m in re.finditer(r"-- (Q\d+)\. ([^\n]+)\n(.*?)(?=\n-- ={10,}\n-- Q\d+\.|\Z)", sql, re.S):
    qid, title, rest = m.group(1), m.group(2), m.group(3)
    if qid == "Q8":
        continue
    # keep only the statement (drop comment-only lines)
    stmt = "\n".join(l for l in rest.splitlines() if not l.strip().startswith("--")).strip()
    stmt = stmt.rstrip(";")
    if not stmt:
        continue
    df = pd.read_sql(stmt, con)
    df.to_csv(f"results/{qid.lower()}.csv", index=False)
    n += 1
    print("=" * 90)
    print(f"{qid}: {title}   ({len(df)} rows)")
    print("=" * 90)
    print(df.head(12).to_string(index=False))
    print()

# ---------------- Q8: index demo ----------------
print("=" * 90)
print("Q8: Index optimization demo")
print("=" * 90)
seller = con.execute("SELECT seller_id FROM order_items GROUP BY seller_id ORDER BY COUNT(*) DESC LIMIT 1").fetchone()[0]
test_q = ("SELECT s.seller_id, COUNT(*), SUM(price) FROM order_items s "
          "WHERE s.seller_id = ? GROUP BY s.seller_id")


def timed(reps=300):
    t = time.perf_counter()
    for _ in range(reps):
        con.execute(test_q, (seller,)).fetchall()
    return (time.perf_counter() - t) / reps * 1000


con.execute("DROP INDEX IF EXISTS idx_items_seller")
print("Plan BEFORE index:", con.execute("EXPLAIN QUERY PLAN " + test_q, (seller,)).fetchall()[0][-1])
before = timed()
con.execute("CREATE INDEX idx_items_seller ON order_items(seller_id)")
print("Plan AFTER index: ", con.execute("EXPLAIN QUERY PLAN " + test_q, (seller,)).fetchall()[0][-1])
after = timed()
print(f"\nAvg query time before: {before:.3f} ms | after: {after:.3f} ms | "
      f"speed-up: {before / after:.1f}x ({100 * (1 - after / before):.0f}% faster)")
con.commit()
con.close()
print(f"\nFinished {n} queries. CSV results saved in results/")
