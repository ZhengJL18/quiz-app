"""RAG Engine — Chroma vector DB + DeepSeek Embedding + semantic search.

Each user gets their own Chroma collection: "user_{user_id}".
Documents are chunked by paragraph, embedded via DeepSeek Embedding API,
and stored in Chroma (SQLite backend, lightweight).

Search returns top-K chunks with metadata (source file, chunk index).
"""

import hashlib
from pathlib import Path
from typing import Optional

import chromadb
import httpx

CHROMA_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "chroma"
CHROMA_PATH.mkdir(parents=True, exist_ok=True)

_chroma_client: Optional[chromadb.PersistentClient] = None


def _get_chroma() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return _chroma_client


def _get_collection(user_id: int):
    client = _get_chroma()
    name = f"user_{user_id}"
    try:
        return client.get_collection(name)
    except Exception:
        return client.create_collection(name)


async def _embed_texts(texts: list[str], api_key: str) -> list[list[float]]:
    """Call DeepSeek Embedding API to get vectors."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.deepseek.com/v1/embeddings",
            json={
                "model": "deepseek-embedding",
                "input": texts,
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()
        return [d["embedding"] for d in data["data"]]


def chunk_markdown(content: str, chunk_size: int = 800, overlap: int = 100) -> list[dict]:
    """Split Markdown into overlapping chunks, respecting paragraph and formula boundaries.

    Returns list of {text, metadata}.
    """
    # Split by double newline (paragraphs)
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    chunks = []
    i = 0

    for para in paragraphs:
        # If paragraph is short, add as-is
        if len(para) <= chunk_size:
            chunks.append({"text": para, "chunk_index": i, "char_start": 0, "char_end": len(para)})
            i += 1
            continue

        # Long paragraph: split by sentences or fixed size
        sentences = para.replace("。", "。\n").replace("！", "！\n").replace("？", "？\n").split("\n")
        current = ""
        for sent in sentences:
            if len(current) + len(sent) <= chunk_size:
                current += sent
            else:
                if current.strip():
                    chunks.append({"text": current.strip(), "chunk_index": i, "char_start": 0, "char_end": len(current)})
                    i += 1
                current = sent
        if current.strip():
            chunks.append({"text": current.strip(), "chunk_index": i, "char_start": 0, "char_end": len(current)})
            i += 1

    return chunks


async def index_document(user_id: int, content: str, source_file: str, api_key: str) -> int:
    """Chunk, embed, and store a document in the user's Chroma collection.

    Returns number of chunks indexed.
    """
    chunks = chunk_markdown(content)
    if not chunks:
        return 0

    # Generate unique IDs
    doc_hash = hashlib.md5(source_file.encode()).hexdigest()[:8]
    ids = [f"{doc_hash}_chunk_{c['chunk_index']}" for c in chunks]
    texts = [c["text"] for c in chunks]
    metadatas = [
        {"source": source_file, "chunk_index": c["chunk_index"], "char_start": c["char_start"], "char_end": c["char_end"]}
        for c in chunks
    ]

    # Embed
    embeddings = await _embed_texts(texts, api_key)

    # Store
    collection = _get_collection(user_id)
    collection.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

    return len(chunks)


async def search_materials(user_id: int, query: str, api_key: str, top_k: int = 3) -> list[dict]:
    """Semantic search over user's indexed materials.

    Returns list of {text, source, score}.
    """
    try:
        collection = _get_collection(user_id)
        if collection.count() == 0:
            return []
    except Exception:
        return []

    # Embed query
    query_embedding = (await _embed_texts([query], api_key))[0]

    # Search
    results = collection.query(query_embeddings=[query_embedding], n_results=top_k)

    output = []
    if results.get("documents") and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            dist = results["distances"][0][i] if results.get("distances") else 1.0
            output.append({
                "text": doc[:500],
                "source": meta.get("source", "unknown"),
                "score": round(1.0 - min(dist, 1.0), 3),  # Convert distance to similarity
            })
    return output


def delete_user_index(user_id: int):
    """Delete a user's Chroma collection (e.g., on account deletion)."""
    client = _get_chroma()
    try:
        client.delete_collection(f"user_{user_id}")
    except Exception:
        pass
