import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
import psycopg
import redis
from fastapi import Depends, FastAPI, Header, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

FORCED_MODEL = "gpt-3.5-turbo"
SYSTEM_PROMPT_PATH = Path(os.getenv("SYSTEM_PROMPT_PATH", "/app/system_prompt.txt"))
API_KEY_FILE = Path(os.getenv("SERVER_API_KEY_FILE", "/data/api_key.txt"))
MEMORY_COLLECTION = os.getenv("QDRANT_COLLECTION", "memories")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
PG_DSN = os.getenv("POSTGRES_DSN", "postgresql://gpt:gpt@postgres:5432/gpt")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "memory")

app = FastAPI(title="CustomGPT Gateway", version="1.0.0")


class Message(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: List[Message]
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False
    max_tokens: Optional[int] = None
    user: Optional[str] = None


class CompletionRequest(BaseModel):
    model: Optional[str] = None
    prompt: Any
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    user: Optional[str] = None


class ResponsesRequest(BaseModel):
    model: Optional[str] = None
    input: Any
    temperature: Optional[float] = 0.7
    max_output_tokens: Optional[int] = Field(default=None, alias="max_output_tokens")
    user: Optional[str] = None


_cached_prompt = {"mtime": 0.0, "value": "You are a helpful assistant."}


def load_system_prompt() -> str:
    global _cached_prompt
    try:
        mtime = SYSTEM_PROMPT_PATH.stat().st_mtime
        if mtime != _cached_prompt["mtime"]:
            _cached_prompt = {"mtime": mtime, "value": SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()}
    except FileNotFoundError:
        pass
    return _cached_prompt["value"]


def ensure_api_key() -> str:
    env_key = os.getenv("SERVER_API_KEY")
    if env_key:
        return env_key
    API_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if API_KEY_FILE.exists():
        return API_KEY_FILE.read_text(encoding="utf-8").strip()
    key = f"sk-local-{uuid.uuid4().hex}{uuid.uuid4().hex[:16]}"
    API_KEY_FILE.write_text(key, encoding="utf-8")
    return key


SERVER_API_KEY = ensure_api_key()


def get_openai_client() -> OpenAI:
    kwargs: Dict[str, Any] = {"api_key": OPENAI_API_KEY}
    if OPENAI_BASE_URL:
        kwargs["base_url"] = OPENAI_BASE_URL
    return OpenAI(**kwargs)


def textify(content: Any) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False)


def embed_cheap(text: str, dims: int = 128) -> List[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    out = []
    for i in range(dims):
        b = digest[i % len(digest)]
        out.append(((b / 255.0) * 2.0) - 1.0)
    return out


def init_deps() -> Dict[str, Any]:
    qdr = QdrantClient(url=QDRANT_URL)
    try:
        qdr.get_collection(MEMORY_COLLECTION)
    except Exception:
        qdr.create_collection(
            collection_name=MEMORY_COLLECTION,
            vectors_config=qmodels.VectorParams(size=128, distance=qmodels.Distance.COSINE),
        )

    rds = redis.from_url(REDIS_URL, decode_responses=True)

    conn = psycopg.connect(PG_DSN)
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_events (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()

    s3 = boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    )
    try:
        s3.head_bucket(Bucket=MINIO_BUCKET)
    except Exception:
        s3.create_bucket(Bucket=MINIO_BUCKET)

    return {"qdrant": qdr, "redis": rds, "pg": conn, "s3": s3}


deps = init_deps()


def authorize(x_api_key: Optional[str] = Header(default=None)):
    if x_api_key != SERVER_API_KEY:
        raise HTTPException(status_code=401, detail={"error": {"message": "Invalid API key", "type": "invalid_request_error"}})


def store_memory(user_id: str, text: str):
    mem_id = str(uuid.uuid4())
    vector = embed_cheap(text)
    deps["qdrant"].upsert(
        collection_name=MEMORY_COLLECTION,
        points=[qmodels.PointStruct(id=mem_id, vector=vector, payload={"user_id": user_id, "text": text})],
    )
    deps["redis"].lpush(f"mem:{user_id}", text)
    deps["redis"].ltrim(f"mem:{user_id}", 0, 199)
    with deps["pg"].cursor() as cur:
        cur.execute("INSERT INTO memory_events (id, user_id, content) VALUES (%s, %s, %s)", (mem_id, user_id, text))
        deps["pg"].commit()
    deps["s3"].put_object(Bucket=MINIO_BUCKET, Key=f"{user_id}/{mem_id}.txt", Body=text.encode("utf-8"))


def retrieve_memory(user_id: str, query: str, k: int = 4) -> List[str]:
    vector = embed_cheap(query)
    hits = deps["qdrant"].search(
        collection_name=MEMORY_COLLECTION,
        query_vector=vector,
        query_filter=qmodels.Filter(
            must=[qmodels.FieldCondition(key="user_id", match=qmodels.MatchValue(value=user_id))]
        ),
        limit=k,
    )
    return [h.payload.get("text", "") for h in hits if h.payload]


def build_messages(req: ChatCompletionRequest) -> List[Dict[str, Any]]:
    user_id = req.user or "anon"
    user_text = "\n".join([textify(m.content) for m in req.messages if m.role == "user"])
    memories = retrieve_memory(user_id, user_text or "context")
    system_prompt = load_system_prompt()
    memory_block = "\n".join(f"- {m}" for m in memories)
    injected = f"{system_prompt}\n\nRetrieved memory:\n{memory_block}" if memories else system_prompt

    msgs = [{"role": "system", "content": injected}]
    msgs.extend([{"role": m.role, "content": textify(m.content)} for m in req.messages])
    return msgs


@app.get("/health")
def health():
    return {"status": "ok", "model": FORCED_MODEL}


@app.get("/v1/models", dependencies=[Depends(authorize)])
def models():
    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {
                "id": FORCED_MODEL,
                "object": "model",
                "created": now,
                "owned_by": "openai",
            }
        ],
    }


@app.post("/v1/chat/completions", dependencies=[Depends(authorize)])
def chat_completions(req: ChatCompletionRequest):
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail={"error": {"message": "OPENAI_API_KEY is not set", "type": "server_error"}})

    client = get_openai_client()
    final_messages = build_messages(req)

    result = client.chat.completions.create(
        model=FORCED_MODEL,
        messages=final_messages,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        stream=False,
    )

    user_id = req.user or "anon"
    for m in req.messages:
        if m.role == "user":
            store_memory(user_id, textify(m.content))

    return result.model_dump()


@app.post("/v1/completions", dependencies=[Depends(authorize)])
def completions(req: CompletionRequest):
    prompt_text = textify(req.prompt)
    chat_req = ChatCompletionRequest(
        messages=[Message(role="user", content=prompt_text)],
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        user=req.user,
    )
    chat_res = chat_completions(chat_req)
    text = chat_res["choices"][0]["message"]["content"]
    return {
        "id": chat_res["id"],
        "object": "text_completion",
        "created": chat_res["created"],
        "model": FORCED_MODEL,
        "choices": [
            {
                "text": text,
                "index": 0,
                "logprobs": None,
                "finish_reason": chat_res["choices"][0].get("finish_reason", "stop"),
            }
        ],
        "usage": chat_res.get("usage", {}),
    }


@app.post("/v1/responses", dependencies=[Depends(authorize)])
def responses(req: ResponsesRequest):
    input_text = textify(req.input)
    chat_req = ChatCompletionRequest(
        messages=[Message(role="user", content=input_text)],
        temperature=req.temperature,
        max_tokens=req.max_output_tokens,
        user=req.user,
    )
    chat_res = chat_completions(chat_req)
    content = chat_res["choices"][0]["message"]["content"]
    return {
        "id": f"resp_{uuid.uuid4().hex}",
        "object": "response",
        "created_at": int(time.time()),
        "model": FORCED_MODEL,
        "output": [
            {
                "id": f"msg_{uuid.uuid4().hex}",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": content, "annotations": []}],
            }
        ],
        "usage": chat_res.get("usage", {}),
    }
