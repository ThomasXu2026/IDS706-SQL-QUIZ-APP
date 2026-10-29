"""Gemini embeddings + Chroma retrieval + Gemini SQL generation."""

import json
import math
from dataclasses import dataclass

import chromadb
from google import genai
from google.genai import types

from database import validate_read_only_sql
from knowledge_base import KNOWLEDGE_DOCUMENTS


EMBEDDING_MODEL = "gemini-embedding-001"
DEFAULT_GENERATION_MODEL = "gemini-3.8-flash"
EMBEDDING_DIMENSIONS = 768


@dataclass(frozen=True)
class RetrievedDocument:
    title: str
    kind: str
    content: str
    distance: float
    question_id: int | None = None


@dataclass(frozen=True)
class SQLDraft:
    sql: str
    explanation: str
    retrieved: list[RetrievedDocument]


def _normalize(vector):
    # Gemini Embedding 001 needs manual normalization at reduced dimensions.
    magnitude = math.sqrt(sum(value * value for value in vector))
    return [value / magnitude for value in vector] if magnitude else vector


class RAGService:
    """Build and query an in-memory Chroma collection with Gemini embeddings."""

    def __init__(self, api_key: str, generation_model: str = DEFAULT_GENERATION_MODEL):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")
        self.client = genai.Client(api_key=api_key)
        self.generation_model = generation_model
        chroma = chromadb.EphemeralClient()
        self.collection = chroma.get_or_create_collection(
            name="online_store_sql_knowledge",
            metadata={"hnsw:space": "cosine"},
        )
        self._index_documents()

    def _embed(self, contents, task_type):
        response = self.client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=contents,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=EMBEDDING_DIMENSIONS,
            ),
        )
        return [_normalize(item.values) for item in response.embeddings]

    def _index_documents(self):
        # Streamlit caches the service, so the fixed knowledge base is embedded once
        # per app process rather than once per user interaction.
        if self.collection.count():
            return
        texts = [document["content"] for document in KNOWLEDGE_DOCUMENTS]
        embeddings = self._embed(texts, "RETRIEVAL_DOCUMENT")
        metadatas = [
            {
                "title": document["title"],
                "kind": document["kind"],
                "question_id": document.get("question_id", 0),
            }
            for document in KNOWLEDGE_DOCUMENTS
        ]
        self.collection.add(
            ids=[document["id"] for document in KNOWLEDGE_DOCUMENTS],
            documents=texts,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    def retrieve(self, question: str, limit: int = 6):
        if not question.strip():
            raise ValueError("Please enter a natural-language question.")
        query_embedding = self._embed([question], "RETRIEVAL_QUERY")[0]
        # Chroma performs the actual cosine nearest-neighbor search. Passing the
        # retrieved texts to Gemini later is what makes this a genuine RAG flow.
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(limit, self.collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        retrieved = []
        for content, metadata, distance in zip(
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        ):
            retrieved.append(
                RetrievedDocument(
                    title=metadata["title"],
                    kind=metadata["kind"],
                    content=content,
                    distance=float(distance),
                    question_id=metadata.get("question_id") or None,
                )
            )
        return retrieved

    def generate_sql(self, question: str, retrieved=None):
        retrieved = retrieved or self.retrieve(question)
        context = "\n\n".join(
            f"[{index}] {document.kind}: {document.title}\n{document.content}"
            for index, document in enumerate(retrieved, start=1)
        )
        prompt = f"""You are a PostgreSQL Text-to-SQL assistant for an online-store database.

Use only the retrieved context below. Return exactly one read-only SELECT query (a WITH
query is allowed). Never invent tables or columns. Never modify data. Use explicit aliases
and deterministic ordering when the request implies an order. Do not wrap SQL in Markdown.

Retrieved context:
{context}

User question:
{question}
"""
        # JSON Schema makes SQL and the human explanation machine-readable and
        # avoids brittle parsing of Markdown code fences.
        response = self.client.models.generate_content(
            model=self.generation_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_json_schema={
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string"},
                        "explanation": {"type": "string"},
                    },
                    "required": ["sql", "explanation"],
                    "additionalProperties": False,
                },
            ),
        )
        payload = json.loads(response.text)
        sql = validate_read_only_sql(payload["sql"])
        return SQLDraft(
            sql=sql,
            explanation=payload["explanation"],
            retrieved=retrieved,
        )


def suggested_question_id(retrieved):
    """Return the closest retrieved few-shot example, if one exists."""
    return next(
        (
            document.question_id
            for document in retrieved
            if document.kind == "few_shot" and document.question_id
        ),
        None,
    )
