"""Goi model qua nha cung cap, khong phu thuoc thu vien ngoai.

Dung ``urllib`` cua thu vien chuan de khong them dependency. Xem
``docs/SECURITY.md`` muc 3 va 5:

- API key chi nam trong header ``Authorization``, khong bao gio trong URL hay
  query string (URL bi ghi vao log cua proxy).
- Timeout cung, khong treo pet.
- Thong bao loi **khong** chua key hay noi dung request.
- Mat mang -> tra ve loi, khong nem exception ra ngoai.

Kien truc: ``Provider`` la giao dien chung; ``GroqProvider`` va ``GeminiProvider``
la hien thuc cu the. Them nha cung cap moi = them mot class, khong sua cho khac.
"""

import json
import urllib.error
import urllib.request

# Timeout cung: model cham thi bo, khong treo pet.
REQUEST_TIMEOUT_SECONDS = 20

# Gioi han cau ra de khong ton tien va khong lam bong bong thoai qua dai.
DEFAULT_MAX_TOKENS = 200


class ProviderError(Exception):
    """Loi khi goi model.

    ``kind`` la ma ngan gon, dung de hien cho nguoi dung. Message **khong**
    duoc chua API key hay noi dung prompt.
    """

    def __init__(self, kind, detail=""):
        self.kind = kind
        self.detail = detail
        super().__init__(f"{kind}: {detail}" if detail else kind)


class Provider:
    """Giao dien chung."""

    name = "base"

    def __init__(self, api_key, model):
        self.api_key = api_key
        self.model = model

    def complete(self, system_prompt, user_content, max_tokens=DEFAULT_MAX_TOKENS):
        """Tra ve chuoi tra loi cua model. Nem ``ProviderError`` khi loi."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Dung chung
    # ------------------------------------------------------------------
    def _post_json(self, url, headers, payload):
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        for key, value in headers.items():
            request.add_header(key, value)

        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            # Khong doc nguyen body loi vao message: co the chua echo prompt.
            if exc.code == 401:
                raise ProviderError("auth", "API key sai hoặc đã hết hạn") from None
            if exc.code == 429:
                raise ProviderError("rate_limit", "nhà cung cấp giới hạn tốc độ") from None
            if exc.code >= 500:
                raise ProviderError("server", f"lỗi phía nhà cung cấp (HTTP {exc.code})") from None
            raise ProviderError("http", f"HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ProviderError("network", "không kết nối được") from None

        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ProviderError("bad_response", "phản hồi không phải JSON") from None


class GroqProvider(Provider):
    """Groq - API tuong thich OpenAI."""

    name = "groq"
    ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
    DEFAULT_MODEL = "llama-3.1-8b-instant"

    def complete(self, system_prompt, user_content, max_tokens=DEFAULT_MAX_TOKENS):
        payload = {
            "model": self.model or self.DEFAULT_MODEL,
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }
        data = self._post_json(
            self.ENDPOINT,
            {"Authorization": f"Bearer {self.api_key}"},
            payload,
        )
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ProviderError("bad_response", "thiếu trường choices") from None


class GeminiProvider(Provider):
    """Google Gemini."""

    name = "gemini"
    ENDPOINT = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "{model}:generateContent"
    )
    DEFAULT_MODEL = "gemini-1.5-flash"

    def complete(self, system_prompt, user_content, max_tokens=DEFAULT_MAX_TOKENS):
        model = self.model or self.DEFAULT_MODEL
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
        }
        data = self._post_json(
            self.ENDPOINT.format(model=model),
            # Gemini dung header rieng, van la header chu khong phai query param.
            {"x-goog-api-key": self.api_key},
            payload,
        )
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            raise ProviderError("bad_response", "thiếu trường candidates") from None


PROVIDERS = {
    "groq": GroqProvider,
    "gemini": GeminiProvider,
}


def build_provider(name, api_key, model=""):
    """Tao provider theo ten. Ten la thi lui ve Groq."""
    cls = PROVIDERS.get((name or "").strip().lower(), GroqProvider)
    return cls(api_key, model)
