"""Optional local dense vector search using FastEmbed/ONNX. No document leaves the machine.

Models download from Hugging Face on first use unless already cached.
This prototype computes cosine similarity in Python; not a production-scale vector index.
"""
import math
import os
from functools import lru_cache

MODEL_NAME = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-small-en-v1.5')

@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=MODEL_NAME, cache_dir=os.getenv('EMBEDDING_CACHE', '/app/models'))

def embed_texts(texts):
    if not texts:
        return []
    return [item.tolist() for item in _model().embed(texts)]

def cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    denom=math.sqrt(sum(x*x for x in a))*math.sqrt(sum(x*x for x in b))
    return sum(x*y for x,y in zip(a,b))/denom if denom else 0.0
