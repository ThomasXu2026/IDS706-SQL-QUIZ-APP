"""Retrieval documents for the online-store Text-to-SQL assistant."""

from questions import QUESTIONS


SCHEMA_DOCUMENTS = [
    {
        "id": "schema-customers",
        "kind": "schema",
        "title": "customers table",
        "content": (
            "PostgreSQL table public.customers. Primary key: customer_id. "
            "customer_name is the display name used in reports. Join to "
            "public.orders with customers.customer_id = orders.customer_id."
        ),
    },
    {
        "id": "schema-products",
        "kind": "schema",
        "title": "products table",
        "content": (
            "PostgreSQL table public.products. Primary key: product_id. "
            "Available reporting columns include product_name and price. Join "
            "to public.order_items with products.product_id = order_items.product_id."
        ),
    },
    {
        "id": "schema-orders",
        "kind": "schema",
        "title": "orders table",
        "content": (
            "PostgreSQL table public.orders. Primary key: order_id. customer_id "
            "references public.customers.customer_id. Join order line items using "
            "orders.order_id = order_items.order_id."
        ),
    },
    {
        "id": "schema-order-items",
        "kind": "schema",
        "title": "order_items table",
        "content": (
            "PostgreSQL table public.order_items. Each row is an order line. "
            "order_id references orders, product_id references products, quantity "
            "is units sold, and unit_price is the price charged per unit."
        ),
    },
]


SEMANTIC_DOCUMENTS = [
    {
        "id": "semantic-sales",
        "kind": "business_semantics",
        "title": "Sales revenue definition",
        "content": (
            "Business metric total_sales means SUM(order_items.quantity * "
            "order_items.unit_price), grouped at the requested grain. Do not use "
            "products.price for historical sales revenue."
        ),
    },
    {
        "id": "semantic-order-count",
        "kind": "business_semantics",
        "title": "Order count and zero-order customers",
        "content": (
            "Order count means COUNT(orders.order_id). When the question says to "
            "include customers with zero orders, start from customers and LEFT JOIN "
            "orders; COUNT(*) would incorrectly count the outer-join placeholder."
        ),
    },
    {
        "id": "semantic-output",
        "kind": "business_semantics",
        "title": "Output contract",
        "content": (
            "Use exactly the column names requested by the question. Add explicit "
            "ORDER BY clauses whenever ranking or deterministic order is requested. "
            "Qualify all application tables with the public schema."
        ),
    },
]


def _few_shot_documents():
    documents = []
    for question_id, question in enumerate(QUESTIONS, start=1):
        documents.append(
            {
                "id": f"example-q{question_id}",
                "kind": "few_shot",
                "title": question["title"],
                "question_id": question_id,
                "content": (
                    f"Natural-language request: {question['description']}\n"
                    f"Correct PostgreSQL:\n{question['sql'].strip()}"
                ),
            }
        )
    return documents


KNOWLEDGE_DOCUMENTS = SCHEMA_DOCUMENTS + SEMANTIC_DOCUMENTS + _few_shot_documents()
