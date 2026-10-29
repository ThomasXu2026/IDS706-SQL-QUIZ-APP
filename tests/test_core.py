from decimal import Decimal

import pytest

from database import check_result, validate_read_only_sql
from knowledge_base import KNOWLEDGE_DOCUMENTS


def test_select_and_cte_are_allowed():
    assert validate_read_only_sql("SELECT 1") == "SELECT 1"
    assert validate_read_only_sql("WITH x AS (SELECT 1) SELECT * FROM x")


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM public.products",
        "UPDATE public.products SET price = 0",
        "DROP TABLE public.products",
        "SELECT 1; SELECT 2",
        "",
    ],
)
def test_non_read_only_or_multiple_statements_are_rejected(query):
    with pytest.raises(ValueError):
        validate_read_only_sql(query)


def test_result_comparison_normalizes_numeric_types():
    question = {"expected": [{"total": 3}]}
    assert check_result(question, ["total"], [(Decimal("3.0"),)], False)


def test_knowledge_base_contains_all_three_rag_evidence_types():
    kinds = {document["kind"] for document in KNOWLEDGE_DOCUMENTS}
    assert kinds == {"schema", "business_semantics", "few_shot"}
    assert sum(doc["kind"] == "few_shot" for doc in KNOWLEDGE_DOCUMENTS) == 5
