"""
indexer.py — Build ChromaDB + BM25 index from chunked data.
Deletes existing index, re-chunks, embeds, and persists.
"""
import os
import sys
import pickle
import shutil
import time

import chromadb
import ollama as ollama_client

from src.config import (
    DATA_DIR, VECTORSTORE_DIR, BM25_PATH, CHUNKS_PATH,
    OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL, EMBED_DIM, HAUI_DEBUG
)
from src.rag.chunking import chunk_all_files

# Try importing underthesea/rank_bm25
try:
    from underthesea import word_tokenize
except ImportError:
    print("[WARN] underthesea not installed, using simple tokenizer")
    def word_tokenize(text):
        return text.split()

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    print("[WARN] rank_bm25 not installed")
    BM25Okapi = None


def embed_text(text, client):
    """Embed a single text using BGE-M3 via Ollama."""
    text = text.strip()
    if len(text) > 2000:
        text = text[:2000]
    response = client.embeddings(model=OLLAMA_EMBED_MODEL, prompt=text)
    return response['embedding']


def build_index(data_dir=None):
    """Main indexing function: chunk → embed → store."""
    if data_dir is None:
        data_dir = DATA_DIR

    print("=" * 60)
    print("  HaUI RAG Chatbot — Indexer v2.2")
    print("=" * 60)

    # 1. Delete old index
    if os.path.exists(VECTORSTORE_DIR):
        print(f"\n[1/5] Xóa ChromaDB cũ: {VECTORSTORE_DIR}")
        shutil.rmtree(VECTORSTORE_DIR)
    os.makedirs(VECTORSTORE_DIR, exist_ok=True)

    if os.path.exists(BM25_PATH):
        os.remove(BM25_PATH)
    if os.path.exists(CHUNKS_PATH):
        os.remove(CHUNKS_PATH)

    # 2. Chunk all files
    print(f"\n[2/5] Chunking dữ liệu từ: {data_dir}")
    chunks = chunk_all_files(data_dir)
    print(f"      → Tạo được {len(chunks)} chunks")

    if not chunks:
        print("[ERROR] Không có chunk nào! Kiểm tra lại thư mục data.")
        return

    # 3. Embed + store to ChromaDB
    print(f"\n[3/5] Embedding với {OLLAMA_EMBED_MODEL} (Ollama: {OLLAMA_BASE_URL})")
    client = ollama_client.Client(host=OLLAMA_BASE_URL)

    chroma_client = chromadb.PersistentClient(path=VECTORSTORE_DIR)
    collection = chroma_client.get_or_create_collection(
        name="haui_chunks",
        metadata={"hnsw:space": "cosine"}
    )

    batch_size = 20
    total = len(chunks)
    for i in range(0, total, batch_size):
        batch = chunks[i:i + batch_size]
        ids = [c['id'] for c in batch]
        texts = [c['text'] for c in batch]
        embeddings = []

        for text in texts:
            try:
                emb = embed_text(text, client)
                embeddings.append(emb)
            except Exception as e:
                print(f"  [WARN] Embedding failed: {e}")
                embeddings.append([0.0] * EMBED_DIM)

        # Prepare metadata (flatten lists to strings for ChromaDB)
        metadatas = []
        for c in batch:
            meta = {}
            for k, v in c['metadata'].items():
                if isinstance(v, list):
                    meta[k] = ','.join(str(x) for x in v)
                elif v is None:
                    meta[k] = ''
                else:
                    meta[k] = str(v)
            metadatas.append(meta)

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )

        done = min(i + batch_size, total)
        print(f"      Embedded {done}/{total} chunks", end='\r')

    print(f"\n      ✓ ChromaDB: {collection.count()} documents stored")

    # 4. Build BM25 index
    print(f"\n[4/5] Building BM25 index...")
    if BM25Okapi:
        tokenized = []
        for chunk in chunks:
            tokens = word_tokenize(chunk['text'])
            meta_tokens = [
                chunk['metadata'].get('ma_nganh', ''),
                chunk['metadata'].get('ten_nganh', ''),
                str(chunk['metadata'].get('nam_moi_nhat', ''))
            ]
            tokens.extend([t for t in meta_tokens if t])
            tokenized.append(tokens)

        bm25 = BM25Okapi(tokenized)
        with open(BM25_PATH, 'wb') as f:
            pickle.dump(bm25, f)
        print(f"      ✓ BM25 index saved: {BM25_PATH}")
    else:
        print("      ✗ Skipped (rank_bm25 not installed)")

    # 5. Save chunks for runtime
    print(f"\n[5/5] Saving chunks metadata...")
    with open(CHUNKS_PATH, 'wb') as f:
        pickle.dump(chunks, f)
    print(f"      ✓ Chunks saved: {CHUNKS_PATH}")

    # Summary
    print("\n" + "=" * 60)
    print("  ✓ Indexing hoàn tất!")
    print(f"    Chunks: {len(chunks)}")
    print(f"    ChromaDB: {VECTORSTORE_DIR}")
    print(f"    BM25: {BM25_PATH}")
    print("=" * 60)

    return chunks


if __name__ == '__main__':
    build_index()
