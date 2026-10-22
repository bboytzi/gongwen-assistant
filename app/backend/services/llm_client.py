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
        "embedding_model": "text-embedding-v3",
        "embedding_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "zhipu": {
        "api_url": "https://open.bigmodel.cn/api/paas/v4",
        "chat_model": "glm-4-flash",
        "embedding_model": "embedding-3",
        "embedding_url": "https://open.bigmodel.cn/api/paas/v4",
    },
    # 腾讯云 TokenHub 国际站：对话与向量接口路径不同，必须分别指定
    "tokenhub": {
        "api_url": "https://tokenhub-intl.tencentcloudmaas.com/plan/v3",
        "chat_model": "deepseek/deepseek-flash",
        "embedding_model": "kinfra-text-embedding-0.6b",
        "embedding_url": "https://tokenhub-intl.tencentcloudmaas.com/v1",
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
    dim: int = 0


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
        embedding_api_key: Optional[str] = None,
    ):
        defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["custom"])
        self.provider = provider
        self.api_key = api_key
        self.chat_model = chat_model
        self.api_url = api_url or defaults["api_url"]
        self.embedding_model = embedding_model or defaults["embedding_model"]
        self.embedding_url = embedding_url or defaults["embedding_url"] or self.api_url
        # 向量接口可独立配置 Key：TokenHub 的 Token Plan Key 仅对 /plan/v3 有效，
        # 调用 /v1 按量计费接口需要另一个 Key
        self.embedding_api_key = embedding_api_key or api_key
        self.client = httpx.Client(timeout=120.0)

    # ------------------------------------------------------------ URL 拼接

    # 已知的 endpoint 尾段。用户可能在「API 地址」里直接粘贴了完整接口地址
    # （例如 https://xxx/v1/chat/completions），此时不能再追加一次。
    _CHAT_SUFFIXES = ("/chat/completions",)
    _EMBED_SUFFIXES = ("/embeddings", "/embedding")

    @classmethod
    def _endpoint(cls, base: str, path: str) -> str:
        """把 base URL 与 endpoint 路径拼成完整地址，容忍三种常见填法：

        1. base 只有版本前缀    https://api.deepseek.com/v1
                              -> https://api.deepseek.com/v1/chat/completions
        2. base 已是完整接口    https://x.com/v1/chat/completions
                              -> 原样返回（不重复追加）
        3. base 是另一种接口    https://x.com/v1/embeddings  且要 chat
                              -> https://x.com/v1/chat/completions（替换尾段）
        """
        url = (base or "").rstrip("/")
        if not url:
            raise ValueError("API 地址为空，请在设置中填写接口地址")

        all_suffixes = cls._CHAT_SUFFIXES + cls._EMBED_SUFFIXES
        for suffix in all_suffixes:
            if url.endswith(suffix):
                stem = url[: -len(suffix)]
                if suffix == f"/{path}":
                    return url
                return f"{stem}/{path}"

        return f"{url}/{path}"

    # ------------------------------------------------------------ API 调用

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> LLMResponse:
        url = self._endpoint(self.api_url, "chat/completions")
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
        if resp.status_code >= 400:
            raise RuntimeError(f"{resp.status_code} {url} — {resp.text[:300]}")
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
            raise ValueError(
                f"未配置 Embedding 模型（当前 provider={self.provider}）。"
                "请在设置中填写向量模型名称，例如 kinfra-text-embedding-0.6b 或 text-embedding-v2"
            )
        url = self._endpoint(self.embedding_url, "embeddings")
        payload = {
            "model": self.embedding_model,
            "input": text,
        }
        headers = {
            "Authorization": f"Bearer {self.embedding_api_key}",
            "Content-Type": "application/json",
        }
        t0 = time.time()
        resp = self.client.post(url, json=payload, headers=headers)
        latency = int((time.time() - t0) * 1000)
        if resp.status_code >= 400:
            hint = ""
            if resp.status_code == 401 and self.embedding_api_key == self.api_key:
                hint = (
                    "｜提示：该 Key 与对话接口共用。若对话正常而这里 401，"
                    "说明向量接口需要独立的 Key（如 TokenHub 的 Token Plan Key "
                    "只能调 /plan/v3，不能调 /v1 按量计费接口）"
                )
            raise RuntimeError(f"{resp.status_code} {url} — {resp.text[:300]}{hint}")
        data = resp.json()
        vector = data["data"][0]["embedding"]
        return EmbeddingResponse(
            vector=vector,
            model=data.get("model", self.embedding_model),
            tokens=data.get("usage", {}).get("total_tokens", 0),
            latency_ms=latency,
            dim=len(vector),
        )

    def test_connectivity(self) -> dict:
        """测试对话与向量两个接口的连通性。"""
        result = {
            "chat_ok": False,
            "embedding_ok": False,
            "chat_latency_ms": None,
            "embedding_latency_ms": None,
            "embedding_dim": None,
            "chat_error": None,
            "embedding_error": None,
            "resolved_chat_url": self._safe_endpoint(self.api_url, "chat/completions"),
            "resolved_embedding_url": self._safe_endpoint(self.embedding_url, "embeddings"),
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
                result["embedding_dim"] = r.dim
                if r.dim and r.dim != 1024:
                    result["embedding_error"] = (
                        f"模型返回 {r.dim} 维向量，但数据库向量列固定为 1024 维。"
                        "请换用 1024 维的 embedding 模型，否则只能使用关键词检索。"
                    )
            except Exception as e:
                result["embedding_error"] = str(e)
        else:
            result["embedding_error"] = "未配置 Embedding 模型"

        return result

    @classmethod
    def _safe_endpoint(cls, base: str, path: str) -> Optional[str]:
        """仅用于回显解析后的地址，出错时返回 None 而不抛异常。"""
        try:
            return cls._endpoint(base, path)
        except Exception:
            return None

    def close(self):
        self.client.close()
