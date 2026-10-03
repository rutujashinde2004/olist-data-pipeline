-- Olist analytics queries (SQLite syntax; works on SQLite 3.25+ for window functions)
-- Run in DB Browser for SQLite, or:  sqlite3 olist.db < analysis_queries.sql

-- =====================================================================
-- Q1. Monthly revenue, running total and month-over-month growth
-- Concepts: CTE, SUM() OVER, LAG()
-- =====================================================================
WITH monthly AS (
    SELECT strftime('%Y-%m', o.order_purchase_timestamp) AS month,
           ROUND(SUM(oi.price), 2) AS revenue
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY 1
)
SELECT month,
       revenue,
       ROUND(SUM(revenue) OVER (ORDER BY month), 2) AS running_total,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
             / LAG(revenue) OVER (ORDER BY month), 1) AS mom_growth_pct
FROM monthly
ORDER BY month;

-- =====================================================================
-- Q2. Top 3 products per category by revenue
-- Concepts: CTE, RANK() with PARTITION BY
-- =====================================================================
WITH product_rev AS (
    SELECT p.product_category_name_english AS category,
           p.product_id,
           ROUND(SUM(oi.price), 2) AS revenue
    FROM order_items oi
    JOIN products p ON oi.product_id = p.product_id
    GROUP BY 1, 2
),
ranked AS (
    SELECT *, RANK() OVER (PARTITION BY category ORDER BY revenue DESC) AS rnk
    FROM product_rev
)
SELECT category, product_id, revenue, rnk
FROM ranked
WHERE rnk <= 3
ORDER BY category, rnk;

-- =====================================================================
-- Q3. Cohort retention (by first-purchase month)
-- Concepts: multiple CTEs, date arithmetic, FIRST_VALUE over aggregate
-- =====================================================================
WITH cust_orders AS (
    SELECT c.customer_unique_id,
           strftime('%Y-%m', o.order_purchase_timestamp) AS order_month
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
),
first_order AS (
    SELECT customer_unique_id, MIN(order_month) AS cohort_month
    FROM cust_orders
    GROUP BY 1
),
activity AS (
    SELECT f.cohort_month,
           co.customer_unique_id,
           (CAST(substr(co.order_month, 1, 4) AS INT) - CAST(substr(f.cohort_month, 1, 4) AS INT)) * 12
         + (CAST(substr(co.order_month, 6, 2) AS INT) - CAST(substr(f.cohort_month, 6, 2) AS INT)) AS month_number
    FROM cust_orders co
    JOIN first_order f USING (customer_unique_id)
)
SELECT cohort_month,
       month_number,
       COUNT(DISTINCT customer_unique_id) AS active_customers,
       ROUND(100.0 * COUNT(DISTINCT customer_unique_id)
             / FIRST_VALUE(COUNT(DISTINCT customer_unique_id))
               OVER (PARTITION BY cohort_month ORDER BY month_number), 2) AS retention_pct
FROM activity
WHERE month_number BETWEEN 0 AND 6
GROUP BY cohort_month, month_number
ORDER BY cohort_month, month_number;

-- =====================================================================
-- Q4. Seller performance ranking (min 30 orders)
-- Concepts: CTE, conditional aggregation, RANK()
-- =====================================================================
WITH seller_orders AS (
    SELECT DISTINCT oi.seller_id, o.order_id, o.is_late, r.review_score
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.order_id
    LEFT JOIN reviews r ON r.order_id = o.order_id
    WHERE o.order_status = 'delivered'
)
SELECT seller_id,
       COUNT(*) AS orders,
       ROUND(AVG(review_score), 2) AS avg_review,
       ROUND(100.0 * SUM(is_late) / COUNT(*), 1) AS late_pct,
       RANK() OVER (ORDER BY AVG(review_score) DESC) AS review_rank
FROM seller_orders
GROUP BY seller_id
HAVING COUNT(*) >= 30
ORDER BY review_rank
LIMIT 20;

-- =====================================================================
-- Q5. Repeat vs one-time customers
-- Concepts: nested aggregation, CASE
-- =====================================================================
WITH cust AS (
    SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS n_orders
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
    GROUP BY 1
)
SELECT CASE WHEN n_orders = 1 THEN 'One-time' ELSE 'Repeat' END AS customer_type,
       COUNT(*) AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM cust
GROUP BY 1;

-- =====================================================================
-- Q6. Impact of late delivery on review score
-- Concepts: joins, GROUP BY on derived flag
-- =====================================================================
SELECT CASE WHEN o.is_late = 1 THEN 'Late' ELSE 'On time' END AS delivery_status,
       COUNT(*) AS orders,
       ROUND(AVG(r.review_score), 2) AS avg_review_score
FROM orders o
JOIN reviews r ON o.order_id = r.order_id
WHERE o.order_status = 'delivered'
GROUP BY 1;

-- =====================================================================
-- Q7. Revenue by customer state with NTILE quartiles
-- Concepts: NTILE(), window over aggregate
-- =====================================================================
WITH state_rev AS (
    SELECT c.customer_state AS state, ROUND(SUM(oi.price), 2) AS revenue
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY 1
)
SELECT state, revenue,
       NTILE(4) OVER (ORDER BY revenue DESC) AS revenue_quartile,
       ROUND(100.0 * revenue / SUM(revenue) OVER (), 2) AS pct_of_total
FROM state_rev
ORDER BY revenue DESC;

-- =====================================================================
-- Q8. Index optimization demo (run these ONE BY ONE and note the plans)
-- Tip: to see a real "before", skip index creation in etl_pipeline.py first.
-- =====================================================================
-- Before:
-- EXPLAIN QUERY PLAN SELECT * FROM order_items WHERE seller_id = '4a3ca9315b744ce9f8e9374361493884';
--   -> expect: SCAN order_items (full table scan)
-- CREATE INDEX idx_items_seller ON order_items(seller_id);
-- After:
-- EXPLAIN QUERY PLAN SELECT * FROM order_items WHERE seller_id = '4a3ca9315b744ce9f8e9374361493884';
--   -> expect: SEARCH order_items USING INDEX idx_items_seller
