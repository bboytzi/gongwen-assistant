"""LLM provider abstraction supporting DeepSeek, Qwen, Zhipu, and custom OpenAI-compatible endpoints."""

import httpx
import time
from typing import Optional
from dataclasses import dataclass


PROVIDER_DEFAULTS = {
    "deepseek": {
        "api_url": "https://api.deepseek.com/v1",
        "chat_model": "deepseek-chat",
        "embedding_model": "",
        "embedding_url": "",
    },
    "qwen": {
        "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "chat_model": "qwen-plus",
        "embedding_model": "text-embedding-v2",
        "embedding_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "zhipu": {
        "api_url": "https://open.bigmodel.cn/api/paas/v4",
        "chat_model": "glm-4-flash",
        "embedding_model": "embedding-3",
        "embedding_url": "https://open.bigmodel.cn/api/paas/v4",
    },
    "custom": {
        "api_url": "",
        "chat_model": "",
        "embedding_model": "",
        "embedding_url": "",
    },
}


@dataclass
class LLMResponse:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0


@dataclass
class EmbeddingResponse:
    vector: list[float]
    model: str = ""
    tokens: int = 0
    latency_ms: int = 0


class LLMClient:
    """Unified client for chat completions and embeddings via OpenAI-compatible APIs."""

    def __init__(
        self,
        provider: str,
        api_key: str,
        chat_model: str,
        api_url: Optional[str] = None,
        embedding_model: Optional[str] = None,
        embedding_url: Optional[str] = None,
    ):
        defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["custom"])
        self.provider = provider
        self.api_key = api_key
        self.chat_model = chat_model
        self.api_url = api_url or defaults["api_url"]
        self.embedding_model = embedding_model or defaults["embedding_model"]
        self.embedding_url = embedding_url or defaults["embedding_url"] or self.api_url
        self.client = httpx.Client(timeout=120.0)

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> LLMResponse:
        url = f"{self.api_url}/chat/completions"
        payload = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        t0 = time.time()
        resp = self.client.post(url, json=payload, headers=headers)
        latency = int((time.time() - t0) * 1000)
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]["message"]
        usage = data.get("usage", {})
        return LLMResponse(
            content=choice["content"],
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=latency,
        )

    def embed(self, text: str) -> EmbeddingResponse:
        if not self.embedding_model:
            raise ValueError(f"Provider {self.provider} has no embedding model configured")
        url = f"{self.embedding_url}/embeddings"
        payload = {
            "model": self.embedding_model,
            "input": text,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        t0 = time.time()
        resp = self.client.post(url, json=payload, headers=headers)
        latency = int((time.time() - t0) * 1000)
        resp.raise_for_status()
        data = resp.json()
        return EmbeddingResponse(
            vector=data["data"][0]["embedding"],
            model=data.get("model", self.embedding_model),
            tokens=data.get("usage", {}).get("total_tokens", 0),
            latency_ms=latency,
        )

    def test_connectivity(self) -> dict:
        """Test both chat and embedding endpoints."""
        result = {
            "chat_ok": False,
            "embedding_ok": False,
            "chat_latency_ms": None,
            "embedding_latency_ms": None,
            "chat_error": None,
            "embedding_error": None,
        }
        # Test chat
        try:
            r = self.chat(
                [{"role": "user", "content": "Hello, respond with 'OK'."}],
                max_tokens=10,
            )
            result["chat_ok"] = True
            result["chat_latency_ms"] = r.latency_ms
        except Exception as e:
            result["chat_error"] = str(e)

        # Test embedding
        if self.embedding_model:
            try:
                r = self.embed("test")
                result["embedding_ok"] = True
                result["embedding_latency_ms"] = r.latency_ms
            except Exception as e:
                result["embedding_error"] = str(e)
        else:
            result["embedding_error"] = "No embedding model configured"

        return result

    def close(self):
        self.client.close()
