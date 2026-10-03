# Olist E-Commerce Data Pipeline & Customer Analytics

End-to-end data engineering and analytics project on the Brazilian Olist e-commerce dataset (~100K orders, 9 relational tables).

## Problem Statement
Olist's data lives in 9 raw CSV files. The goal is to build a clean, queryable SQL database and answer business questions about revenue, seller performance, delivery impact on reviews, customer retention and customer segments.

## Architecture
Kaggle CSVs -> Python (Pandas: clean, validate, derive features) -> SQLite -> Advanced SQL analytics -> RFM + KMeans segmentation

## Tech Stack
Python (Pandas, scikit-learn, matplotlib), SQL (CTEs, window functions), SQLite

## Project Structure
- generate_sample_data.py - synthetic data with the Olist schema (for an instant demo)
- etl_pipeline.py - extract, transform, load + indexes
- analysis_queries.sql - 8 advanced SQL queries
- run_queries.py - runs the queries, saves results, index speed-up demo
- rfm_segmentation.py - RFM scoring + KMeans clustering

## ETL Highlights
- Removed duplicates, parsed dates, handled missing delivery dates
- Translated product categories from Portuguese to English
- Derived delivery_days and is_late features
- Kept one review per order; collapsed geolocation to one row per zip prefix
- Created indexes on join keys

## SQL Analysis (analysis_queries.sql)
| # | Question | Concepts |
|---|---|---|
| 1 | Monthly revenue, running total, MoM growth | CTE, SUM OVER, LAG |
| 2 | Top 3 products per category | RANK, PARTITION BY |
| 3 | Cohort retention | Multi-CTE, FIRST_VALUE |
| 4 | Seller performance ranking | Conditional aggregation, RANK |
| 5 | Repeat vs one-time customers | Window over aggregate |
| 6 | Late delivery vs review score | Joins, derived flags |
| 7 | State revenue quartiles | NTILE |
| 8 | Index optimization | EXPLAIN QUERY PLAN |

## Key Insights
- Late deliveries (about 8% of delivered orders) lower the average review score from 4.29 to 2.57.
- SP, RJ and MG together generate about 63% of total revenue (SP alone is 38%).
- 97% of customers bought only once, so repeat purchase and retention are the biggest growth opportunity.
- Monthly revenue grew about 5.4x from Jan 2017 (R$112K) to Sep 2017 (R$607K).
- Adding an index on order_items(seller_id) cut a seller lookup query from 19.7 ms to 3.2 ms (84% faster).

## How to Run
1. pip install pandas scikit-learn matplotlib
2. Download the "Brazilian E-Commerce Public Dataset by Olist" from Kaggle and put the 9 CSVs in data/raw/
   (or run python generate_sample_data.py to use synthetic sample data)
3. python etl_pipeline.py
4. python run_queries.py
5. python rfm_segmentation.py

## Customer Segmentation (RFM)
Customers are scored 1-5 on Recency, Frequency and Monetary value and grouped into segments (Champions, Loyal, At Risk, Lost, New). KMeans clustering is applied on log-scaled RFM values as a second view. Note: 97% of customers have a single order, so frequency varies little and segments are driven mostly by recency and spend.
