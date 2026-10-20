
QUESTIONS = [
    {
        "title": "Q1 — Product Filtering",
        "points": 4,
        "description": (
            "List the names and prices of all products "
            "that cost more than $100. "
            "Sort by price from highest to lowest."
        ),
        "sql": """
SELECT product_name, price
FROM public.products
WHERE price > 100
ORDER BY price DESC;
""",
        "expected": [
            {"product_name": "Laptop", "price": 899},
            {"product_name": "Headphones", "price": 120}
        ]
    },

    {
        "title": "Q2 — Top 5 Products",
        "points": 4,
        "description": (
            "Find the five most expensive products. "
            "Display product_name and price, "
            "sorted by price descending."
        ),
        "sql": """
SELECT product_name, price
FROM public.products
ORDER BY price DESC
LIMIT 5;
""",
        "expected": [
            {"product_name": "Laptop", "price": 899},
            {"product_name": "Headphones", "price": 120},
            {"product_name": "Keyboard", "price": 75},
            {"product_name": "Mouse", "price": 35},
            {"product_name": "Notebook", "price": 25}
        ]
    },

    {
        "title": "Q3 — Orders by Customer",
        "points": 4,
        "description": (
            "Count the number of orders placed by each "
            "customer. Display customer_name and "
            "order_count. Include customers with zero "
            "orders. Sort by order_count descending, "
            "then customer_name ascending."
        ),
        "sql": """
SELECT c.customer_name,
       COUNT(o.order_id) AS order_count
FROM public.customers c
LEFT JOIN public.orders o
    ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.customer_name
ORDER BY order_count DESC, c.customer_name;
""",
        "expected": [
            {"customer_name": "Alice", "order_count": 3},
            {"customer_name": "Bob", "order_count": 3},
            {"customer_name": "David", "order_count": 2},
            {"customer_name": "Carla", "order_count": 1},
            {"customer_name": "Emma", "order_count": 1}
        ]
    },

    {
        "title": "Q4 — Frequent Customers",
        "points": 4,
        "description": (
            "Find customers who have placed more than "
            "two orders. Display customer_name and "
            "order_count. Sort by customer_name."
        ),
        "sql": """
SELECT c.customer_name,
       COUNT(o.order_id) AS order_count
FROM public.customers c
JOIN public.orders o
    ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.customer_name
HAVING COUNT(o.order_id) > 2
ORDER BY c.customer_name;
""",
        "expected": [
            {"customer_name": "Alice", "order_count": 3},
            {"customer_name": "Bob", "order_count": 3}
        ]
    },

    {
        "title": "Q5 — Sales by Product",
        "points": 4,
        "description": (
            "Calculate total sales revenue for each "
            "product using quantity * unit_price. "
            "Display product_name and total_sales. "
            "Sort by total_sales descending."
        ),
        "sql": """
SELECT p.product_name,
       SUM(oi.quantity * oi.unit_price) AS total_sales
FROM public.products p
JOIN public.order_items oi
    ON p.product_id = oi.product_id
GROUP BY p.product_id, p.product_name
ORDER BY total_sales DESC;
""",
        "expected": [
            {"product_name": "Laptop", "total_sales": 1798},
            {"product_name": "Headphones", "total_sales": 360},
            {"product_name": "Keyboard", "total_sales": 300},
            {"product_name": "Notebook", "total_sales": 175},
            {"product_name": "Mouse", "total_sales": 140},
            {"product_name": "Water Bottle", "total_sales": 54}
        ]
    }
]
