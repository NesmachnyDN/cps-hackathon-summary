#!/usr/bin/env python3
from __future__ import annotations

import base64
import errno
import json
import os
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener

HOST = os.environ.get("APP_HOST", "127.0.0.1")
PORT = int(os.environ.get("APP_PORT", "8000"))
ROOT = Path(__file__).resolve().parent
INDEX_FILE = ROOT / "static" / "index.html"
PROVIDER_TIMEOUT_SECONDS = 30
_PROVIDER_READINESS = {"state": "NOT_RUN", "message": "Live-проверка ещё не выполнялась."}
_DETECTOR_READINESS = {"state": "NOT_RUN", "message": "Автодетектор ещё не запускался."}
DETECTOR_CATEGORIES = {"ORG", "SYSTEM", "PROJECT", "PERSON", "SECRET"}
MAX_REQUEST_BYTES = 3_500_000
MAX_FILE_BYTES = 2_000_000
MAX_EXTRACTED_CHARS = 200_000
SUPPORTED_FILE_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".docx", ".pdf"}
CORPUS_PATH = Path(os.environ.get("NORMATIVE_CORPUS_PATH", str(ROOT / "demo" / "normative_corpus.json")))
PROMPTS_PATH = Path(os.environ.get("NORMATIVE_PROMPTS_PATH", str(ROOT / "prompts.json")))
POLICY_RULES = [
    {"content": "Обычный текст", "action": "ALLOW"},
    {"content": "ORG / SYSTEM / PROJECT / PERSON / внутренние идентификаторы", "action": "PSEUDONYMIZE"},
    {"content": "Email / телефон", "action": "MASK"},
    {"content": "Credentials / private keys", "action": "BLOCK"},
]

EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w-])")
PHONE_RE = re.compile(r"(?<!\d)(?:\+7|8)[\s-]?(?:\(?\d{3}\)?)[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}(?!\d)")
PERSON_CONTEXT_RE = re.compile(
    r"(?:Бизнес-владелец|Технический владелец|Ответственный|Ответственная)\s*:\s*"
    r"([А-ЯЁ][а-яё-]{1,30}\s+[А-ЯЁ][а-яё-]{1,30})"
)
CONTEXT_ENTITY_PATTERNS = (
    ("ORG", re.compile(r"\b(?:Компания|компания|компании|компанию)\s+([А-ЯЁA-Z][\w.-]+(?:\s+[А-ЯЁA-Z][\w.-]+)?)")),
    ("SYSTEM", re.compile(r"\b(?:[Сс]истема|[Сс]истемы|[Сс]истему|[Кк]онтур|[Кк]онтуре)\s+([А-ЯЁA-Z][\w.-]+(?:\s+[А-ЯЁA-Z][\w.-]+)?)")),
    ("PROJECT", re.compile(r"\b(?:[Пп]роект|[Пп]роекта|[Пп]роектом|[Пп]роекту)\s+([А-ЯЁA-Z][\w.-]+)")),
)
TECHNICAL_ID_RE = re.compile(r"\b(?:INC|DB|VPN)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")
ALLOWED_CATEGORIES = {"ORG", "SYSTEM", "PROJECT", "PERSON", "SECRET", "EMAIL", "PHONE"}
CREDENTIAL_PATTERNS = [
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.IGNORECASE)),
    (
        "ASSIGNED_CREDENTIAL",
        re.compile(
            r"\b(?:api[_ -]?key|token|password|пароль|secret|секрет)\s*[:=]\s*[^\s,;]{6,}",
            re.IGNORECASE,
        ),
    ),
    (
        "AUTHORIZATION",
        re.compile(r"\bAuthorization\s*:\s*Bearer\s+[^\s]{8,}", re.IGNORECASE),
    ),
]


@dataclass(frozen=True)
class Entity:
    value: str
    category: str
    token: str

    def public_dict(self) -> dict[str, str]:
        return {"value": self.value, "category": self.category, "token": self.token}


@dataclass(frozen=True)
class ProviderConfig:
    profile: str
    base_url: str
    model: str
    api_key: str | None
    network: str

    @property
    def configured(self) -> bool:
        if self.profile == "GROQ_TEMP_48H_TUN":
            return bool(self.api_key)
        return bool(self.base_url and self.model)


class ProviderError(RuntimeError):
    pass


class PolicyBlockedError(RuntimeError):
    def __init__(self, message: str, policy: dict[str, object]):
        super().__init__(message)
        self.policy = policy


def _normalize_terms(raw_terms: Iterable[dict[str, object]]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw_terms:
        value = str(item.get("value", "")).strip()
        category = str(item.get("category", "SECRET")).strip().upper()
        if not value:
            continue
        if category not in ALLOWED_CATEGORIES:
            category = "SECRET"
        key = (value, category)
        if key not in seen:
            seen.add(key)
            result.append(key)
    result.sort(key=lambda pair: len(pair[0]), reverse=True)
    return result


def deterministic_person_candidates(text: str) -> list[str]:
    """Extract person names only from explicit role-labelled phrases.

    This is intentionally conservative: a generic two-capitalized-words regex would
    misclassify product/system names such as "Платформа Вега" as people.
    """
    result: list[str] = []
    seen: set[str] = set()
    for match in PERSON_CONTEXT_RE.finditer(text):
        value = match.group(1)
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def deterministic_sensitive_candidates(text: str) -> list[dict[str, str]]:
    """Conservative local hints that supplement and correct detector output.

    The rules only use explicit linguistic labels or technical-ID prefixes, so they
    improve demo/runtime stability without trying to replace the detector with NER.
    """
    by_value: dict[str, str] = {}
    for value in deterministic_person_candidates(text):
        by_value[value] = "PERSON"
    for category, pattern in CONTEXT_ENTITY_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(1).strip(" \t\r\n.,;:()[]{}")
            if value:
                by_value[value] = category
    for match in TECHNICAL_ID_RE.finditer(text):
        by_value[match.group(0)] = "SECRET"
    return [{"value": value, "category": category} for value, category in by_value.items()]


def pseudonymize(text: str, raw_terms: Iterable[dict[str, object]]) -> tuple[str, list[Entity], dict[str, str]]:
    if not isinstance(text, str):
        raise ValueError("text must be a string")

    counters: defaultdict[str, int] = defaultdict(int)
    value_to_entity: dict[tuple[str, str], Entity] = {}
    token_to_value: dict[str, str] = {}
    result = text

    def replace_value(value: str, category: str, source: str) -> str:
        key = (value, category)
        entity = value_to_entity.get(key)
        if entity is None:
            counters[category] += 1
            token = (
                f"[[{category}_MASKED_{counters[category]:03d}]]"
                if category in {"EMAIL", "PHONE"}
                else f"[[{category}_{counters[category]:03d}]]"
            )
            entity = Entity(value=value, category=category, token=token)
            value_to_entity[key] = entity
            token_to_value[token] = value
        return source.replace(value, entity.token)

    for value, category in _normalize_terms(raw_terms):
        if value in result:
            result = replace_value(value, category, result)

    for value in deterministic_person_candidates(result):
        result = replace_value(value, "PERSON", result)

    for category, pattern in (("EMAIL", EMAIL_RE), ("PHONE", PHONE_RE)):
        values: list[str] = []
        seen_values: set[str] = set()
        for match in pattern.finditer(result):
            value = match.group(0)
            if value not in seen_values:
                seen_values.add(value)
                values.append(value)
        for value in values:
            result = replace_value(value, category, result)

    entities = list(value_to_entity.values())
    ensure_no_leak(result, entities)
    return result, entities, token_to_value


def ensure_no_leak(candidate: str, entities: Iterable[Entity]) -> None:
    leaked = [entity.value for entity in entities if entity.value and entity.value in candidate]
    if leaked:
        raise ValueError(f"Leak check failed for {len(leaked)} protected value(s)")


def restore(text: str, token_to_value: dict[str, str]) -> str:
    restored = text
    for token in sorted(token_to_value, key=len, reverse=True):
        restored = restored.replace(token, token_to_value[token])
    return restored


def policy_action_for_category(category: str) -> str:
    return "MASK" if category in {"EMAIL", "PHONE"} else "PSEUDONYMIZE"


def detect_blocking_credentials(text: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    seen: set[str] = set()
    for kind, pattern in CREDENTIAL_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(0)
            if value not in seen:
                seen.add(value)
                findings.append({"kind": kind, "value": value})
    return findings


def apply_policy(
    text: str,
    raw_terms: Iterable[dict[str, object]],
) -> tuple[str, list[Entity], dict[str, str], dict[str, object]]:
    outbound, entities, token_to_value = pseudonymize(text, raw_terms)
    blocked = detect_blocking_credentials(text)

    for index, finding in enumerate(blocked, start=1):
        outbound = outbound.replace(
            finding["value"],
            f"[[CREDENTIAL_BLOCKED_{index:03d}]]",
        )

    ensure_no_leak(outbound, entities)
    if any(finding["value"] in outbound for finding in blocked):
        raise ValueError("Policy redaction failed for blocked credential")

    entity_findings = [
        {
            "category": entity.category,
            "action": policy_action_for_category(entity.category),
            "token": entity.token,
        }
        for entity in entities
    ]
    block_findings = [
        {"category": "CREDENTIAL", "action": "BLOCK", "kind": finding["kind"]}
        for finding in blocked
    ]
    counts = {
        "PSEUDONYMIZE": sum(
            1 for item in entity_findings if item["action"] == "PSEUDONYMIZE"
        ),
        "MASK": sum(1 for item in entity_findings if item["action"] == "MASK"),
        "BLOCK": len(block_findings),
    }
    policy = {
        "decision": "BLOCK" if blocked else "ALLOW",
        "allowed": not blocked,
        "counts": counts,
        "findings": entity_findings + block_findings,
        "rules": POLICY_RULES,
        "reason": (
            "Обнаружены credentials, которые запрещено передавать во внешний AI."
            if blocked
            else "Запрос соответствует политике после применения защитных преобразований."
        ),
    }
    return outbound, entities, token_to_value, policy


def _decode_text_bytes(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            return data.decode("cp1251")
        except UnicodeDecodeError as exc:
            raise ValueError("file encoding is not supported") from exc


def _extract_docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > MAX_FILE_BYTES * 4:
                raise ValueError("DOCX document.xml is too large")
            xml = archive.read(info)
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ValueError("invalid DOCX file") from exc

    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise ValueError("invalid DOCX XML") from exc

    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs: list[str] = []
    for paragraph in root.iter(ns + "p"):
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == ns + "t" and node.text:
                parts.append(node.text)
            elif node.tag == ns + "tab":
                parts.append("\t")
            elif node.tag == ns + "br":
                parts.append("\n")
        value = "".join(parts).strip()
        if value:
            paragraphs.append(value)
    return "\n".join(paragraphs)


def _extract_pdf_text(data: bytes) -> str:
    """Extract PDF text locally. pypdf is optional at import time for simple launch."""
    if not data.startswith(b"%PDF-") or b"%%EOF" not in data:
        raise ValueError("invalid or unsupported PDF file")
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ValueError("PDF support requires pypdf; run pip install -r requirements.txt") from exc
    try:
        reader = PdfReader(BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:  # pypdf has a broad set of parse exceptions
        raise ValueError("invalid or unsupported PDF file") from exc


def extract_uploaded_text(filename: str, data: bytes) -> dict[str, object]:
    safe_name = Path(filename or "").name
    extension = Path(safe_name).suffix.lower()
    if extension not in SUPPORTED_FILE_EXTENSIONS:
        raise ValueError("unsupported file type; use TXT, MD, CSV, JSON, DOCX or PDF")
    if not data:
        raise ValueError("file is empty")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("file is too large")

    if extension == ".docx":
        text = _extract_docx_text(data)
    elif extension == ".pdf":
        text = _extract_pdf_text(data)
    else:
        text = _decode_text_bytes(data)
    text = text.strip()
    if not text:
        raise ValueError("file contains no extractable text")
    if len(text) > MAX_EXTRACTED_CHARS:
        raise ValueError("extracted text is too large")
    return {
        "name": safe_name,
        "extension": extension,
        "sizeBytes": len(data),
        "characters": len(text),
        "text": text,
    }


def import_file_payload(payload: dict[str, object]) -> dict[str, object]:
    filename = str(payload.get("name", "")).strip()
    encoded = str(payload.get("contentBase64", "")).strip()
    if not filename or not encoded:
        raise ValueError("file name and content are required")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid base64 file content") from exc
    file_info = extract_uploaded_text(filename, data)
    text = file_info.pop("text")
    return {"file": file_info, "text": text}


def normalize_chat_url(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    if not base:
        return ""
    if base.endswith("/v1/chat/completions"):
        return base
    if base.endswith("/v1"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def groq_provider_config() -> ProviderConfig:
    return ProviderConfig(
        profile="GROQ_TEMP_48H_TUN",
        base_url="https://api.groq.com/openai/v1",
        model="openai/gpt-oss-120b",
        api_key=os.environ.get("GROQ_API_KEY", "").strip() or None,
        network="SYSTEM_TUNNEL",
    )


def cps_provider_config() -> ProviderConfig:
    return ProviderConfig(
        profile="CPS_INTERNAL_OPENAI_COMPAT",
        base_url=os.environ.get("CPS_LLM_BASE_URL", "").strip(),
        model=os.environ.get("CPS_LLM_MODEL", "").strip(),
        api_key=os.environ.get("CPS_LLM_API_KEY", "").strip() or None,
        network="INTERNAL",
    )


def active_detector_config() -> ProviderConfig:
    profile = os.environ.get("LLM_PROFILE", "groq").strip().lower()
    return cps_provider_config() if profile == "cps" else groq_provider_config()


def active_provider_config() -> ProviderConfig:
    """Backward-compatible alias for the configured detector profile."""
    return active_detector_config()


def external_provider_config() -> ProviderConfig:
    # Corporate mode must never depend on public Groq. Safe outbound is copied manually.
    if active_detector_config().profile == "CPS_INTERNAL_OPENAI_COMPAT":
        return ProviderConfig(
            profile="EXTERNAL_MANUAL_COPY",
            base_url="",
            model="",
            api_key=None,
            network="MANUAL_COPY",
        )
    return groq_provider_config()


def _status_payload(config: ProviderConfig, readiness: dict[str, str], message: str) -> dict[str, object]:
    return {
        "profile": config.profile,
        "baseUrl": config.base_url or None,
        "chatUrl": normalize_chat_url(config.base_url) or None,
        "model": config.model or None,
        "configured": config.configured,
        "network": config.network,
        "authConfigured": bool(config.api_key),
        "readiness": readiness["state"],
        "message": message if readiness["state"] == "NOT_RUN" else readiness["message"],
    }


def detector_status() -> dict[str, object]:
    config = active_detector_config()
    if config.profile == "GROQ_TEMP_48H_TUN":
        message = (
            "Демо-автодетектор готов через Groq. Используйте только синтетические данные; "
            "в корпоративном контуре исходный текст должен обрабатываться внутренней LLM."
            if config.configured
            else "Автодетектор недоступен: GROQ_API_KEY не задан. Ручное заполнение mapping работает."
        )
    else:
        message = (
            "Автодетектор готов: исходный текст обрабатывается внутренней OpenAI-compatible LLM."
            if config.configured
            else "Автодетектор недоступен: CPS_LLM_BASE_URL/CPS_LLM_MODEL не заданы. Ручное заполнение mapping работает."
        )
    return _status_payload(config, _DETECTOR_READINESS, message)


def provider_status() -> dict[str, object]:
    config = external_provider_config()
    if config.profile == "EXTERNAL_MANUAL_COPY":
        return {
            "profile": config.profile,
            "baseUrl": None,
            "chatUrl": None,
            "model": None,
            "configured": False,
            "network": config.network,
            "authConfigured": False,
            "readiness": "MANUAL",
            "message": (
                "Внешняя LLM отключена для корпоративного профиля. Это штатный режим: "
                "сформируйте безопасный payload и скопируйте его вручную."
            ),
        }
    message = (
        "Groq готов для демонстрационного round-trip; live-проверка ещё не выполнялась."
        if config.configured
        else "Внешняя LLM недоступна. Анонимизация работает; безопасный payload можно скопировать вручную."
    )
    return _status_payload(config, _PROVIDER_READINESS, message)


PROCESSOR_SYSTEM_PROMPT = (
    "Обработай запрос пользователя. Сохраняй защитные маркеры вида [[TYPE_001]] "
    "и [[TYPE_MASKED_001]] без изменений, чтобы доверенный шлюз мог восстановить "
    "разрешённые значения локально."
)

DETECTOR_SYSTEM_PROMPT = (
    "Ты локальный детектор чувствительных сущностей. Верни ТОЛЬКО JSON-массив без Markdown. "
    'Формат каждого элемента: {"value":"ТОЧНЫЙ короткий фрагмент","category":"ORG|SYSTEM|PROJECT|PERSON|SECRET"}. '
    "Категории: ORG — компания/организация; SYSTEM — система, приложение или платформа; "
    "PROJECT — проект/программа; PERSON — только ФИО человека; SECRET — номер инцидента, "
    "сервер, инфраструктурный идентификатор или другой внутренний код. "
    "Не включай заголовки разделов, роли и соседние слова. value должен быть одной сущностью, "
    "не содержать перевод строки и дословно встречаться в исходном тексте. "
    "Email и телефоны не включай: шлюз находит их детерминированно. Не выдумывай значения. "
    "Пример: компания Альтаир Энерго => ORG; система ДокФлоу-X => SYSTEM; "
    "проект Миграция-42 => PROJECT; Мария Орлова => PERSON; DB-PROD-01 => SECRET."
)


def build_chat_request(
    user_text: str,
    model: str | None = None,
    system_prompt: str = PROCESSOR_SYSTEM_PROMPT,
) -> dict[str, object]:
    resolved_model = model or active_detector_config().model or "openai/gpt-oss-120b"
    return {
        "model": resolved_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
        # Bound generation for predictable hackathon latency; prompts request concise answers.
        "max_tokens": 240,
    }


def groq_proxy_url() -> str | None:
    explicit = os.environ.get("GROQ_PROXY_URL", "").strip()
    if explicit.lower() in {"direct", "off", "none"}:
        return None
    return (
        explicit
        or os.environ.get("HTTPS_PROXY", "").strip()
        or os.environ.get("https_proxy", "").strip()
        or None
    )


def _provider_opener(config: ProviderConfig):
    if config.profile == "GROQ_TEMP_48H_TUN":
        proxy = groq_proxy_url()
        if proxy:
            return build_opener(ProxyHandler({"http": proxy, "https": proxy}))
        return build_opener()
    return build_opener()


def provider_timeout_seconds(config: ProviderConfig) -> int:
    if config.profile != "CPS_INTERNAL_OPENAI_COMPAT":
        return PROVIDER_TIMEOUT_SECONDS
    raw = os.environ.get("CPS_LLM_TIMEOUT_SECONDS", "90").strip()
    try:
        value = int(raw)
    except ValueError:
        return 90
    return min(max(value, 10), 300)


def call_provider(
    user_text: str,
    config: ProviderConfig | None = None,
    timeout: int = PROVIDER_TIMEOUT_SECONDS,
    opener=None,
    system_prompt: str = PROCESSOR_SYSTEM_PROMPT,
) -> str:
    config = config or active_detector_config()
    if not config.configured:
        raise ProviderError("Provider runtime configuration is incomplete")
    chat_url = normalize_chat_url(config.base_url)
    if not chat_url:
        raise ProviderError("Provider endpoint is not configured")

    payload = build_chat_request(user_text, config.model, system_prompt)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "SecureLLMGateway/0.1",
    }
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    request = Request(chat_url, data=body, headers=headers, method="POST")
    client = opener or _provider_opener(config)

    try:
        with client.open(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = ""
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
            error_data = json.loads(error_body)
            detail = str(error_data.get("error", {}).get("message", "")).strip()
        except (AttributeError, json.JSONDecodeError, TypeError, ValueError):
            detail = ""
        if config.api_key and detail:
            detail = detail.replace(config.api_key, "[REDACTED]")
        detail = re.sub(r"\s+", " ", detail)[:240]
        suffix = f" — {detail}" if detail else ""
        raise ProviderError(f"Provider HTTP error: {exc.code}{suffix}") from exc
    except URLError as exc:
        raise ProviderError("Provider transport error") from exc
    except TimeoutError as exc:
        raise ProviderError("Provider request timed out") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderError("Provider returned invalid JSON") from exc
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("Provider response has unexpected shape") from exc
    if not isinstance(content, str) or not content.strip():
        raise ProviderError("Provider returned empty content")
    return content


def parse_detection_response(content: str, source_text: str) -> list[dict[str, str]]:
    raw = content.strip()
    fence = chr(96) * 3
    if raw.startswith(fence):
        lines = raw.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith(fence):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    start = raw.find("[")
    end = raw.rfind("]")
    if start < 0 or end < start:
        raise ValueError("Detector response does not contain a JSON array")
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("Detector response contains invalid JSON") from exc
    if not isinstance(data, list):
        raise ValueError("Detector response must be a JSON array")

    result: list[dict[str, str]] = []
    seen_values: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        value = str(item.get("value", "")).strip()
        category = str(item.get("category", "SECRET")).strip().upper()
        if (
            not value
            or value not in source_text
            or value in seen_values
            or "\n" in value
            or "\r" in value
            or "\t" in value
            or len(value) > 120
        ):
            continue
        if category in {"EMAIL", "PHONE"} or EMAIL_RE.fullmatch(value) or PHONE_RE.fullmatch(value):
            continue
        if category not in DETECTOR_CATEGORIES:
            category = "SECRET"
        seen_values.add(value)
        result.append({"value": value, "category": category})
    return result


def detect_sensitive_terms(text: str, detector_call=None) -> dict[str, object]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must not be empty")
    config = active_detector_config()
    if detector_call is None and not config.configured:
        raise ProviderError("Detector runtime configuration is incomplete")
    try:
        response = (
            detector_call(text)
            if detector_call is not None
            else call_provider(
                text,
                config=config,
                timeout=provider_timeout_seconds(config),
                system_prompt=DETECTOR_SYSTEM_PROMPT,
            )
        )
        terms = parse_detection_response(response, text)
        positions = {str(item.get("value", "")): index for index, item in enumerate(terms)}
        for candidate in deterministic_sensitive_candidates(text):
            value = candidate["value"]
            if value in positions:
                terms[positions[value]] = candidate
            else:
                positions[value] = len(terms)
                terms.append(candidate)
    except (ProviderError, ValueError) as exc:
        _DETECTOR_READINESS.update(state="FAIL", message=f"Автодетектор: FAIL — {exc}")
        if isinstance(exc, ProviderError):
            raise
        raise ProviderError(str(exc)) from exc
    _DETECTOR_READINESS.update(
        state="PASS",
        message=f"Автодетектор: PASS — предложено {len(terms)} чувствительных значений.",
    )
    return {"terms": terms, "count": len(terms), "detector": detector_status()}


def process_payload(payload: dict[str, object], provider_call=None) -> dict[str, object]:
    text = str(payload.get("text", ""))
    raw_terms = payload.get("terms", [])
    if not isinstance(raw_terms, list):
        raise ValueError("terms must be a list")
    outbound, entities, token_to_value, policy = apply_policy(text, raw_terms)
    if not policy["allowed"]:
        raise PolicyBlockedError(
            "Security policy blocked external processing",
            policy,
        )
    if provider_call is None:
        config = external_provider_config()
        if not config.configured:
            raise ProviderError("External provider unavailable; copy the safe outbound payload manually")
        provider_text = call_provider(outbound, config=config)
    else:
        provider_text = provider_call(outbound)
    restored = restore(provider_text, token_to_value)
    return {
        "original": text,
        "entities": [entity.public_dict() for entity in entities],
        "outbound": outbound,
        "providerResponse": provider_text,
        "restoredResponse": restored,
        "protectedCount": len(entities),
        "policy": policy,
    }


def run_provider_preflight(provider_call=None) -> dict[str, object]:
    probe = "Верни строку точно в таком виде: OK [[ORG_001]]"
    try:
        if provider_call is None:
            config = external_provider_config()
            if not config.configured:
                raise ProviderError("External provider unavailable; manual-copy mode is active")
            response = call_provider(probe, config=config)
        else:
            response = provider_call(probe)
        if "[[ORG_001]]" not in response:
            raise ProviderError("Provider preflight did not preserve pseudonym marker")
    except ProviderError as exc:
        _PROVIDER_READINESS.update(state="FAIL", message=f"Live-проверка провайдера: FAIL — {exc}")
        raise
    _PROVIDER_READINESS.update(state="PASS", message="Live-проверка провайдера: PASS. Реальный вызов доступен.")
    return {"response": response, "provider": provider_status()}


def analyze_payload(payload: dict[str, object]) -> dict[str, object]:
    text = str(payload.get("text", ""))
    raw_terms = payload.get("terms", [])
    if not isinstance(raw_terms, list):
        raise ValueError("terms must be a list")
    outbound, entities, token_to_value, policy = apply_policy(text, raw_terms)
    local_restore = restore(outbound, token_to_value)
    external = external_provider_config()
    return {
        "original": text,
        "entities": [entity.public_dict() for entity in entities],
        "outbound": outbound,
        "localRestoreCheck": local_restore,
        "protectedCount": len(entities),
        "detector": detector_status(),
        "provider": provider_status(),
        "manualCopyRequired": not external.configured,
        "copyAllowed": bool(policy["allowed"]),
        "policy": policy,
        "providerRequestPreview": (
            build_chat_request(outbound, external.model)
            if external.configured and policy["allowed"]
            else None
        ),
    }


def load_prompts() -> dict[str, str]:
    """Editable product wording, intentionally stored outside Python code."""
    defaults = {
        "query_system": "Ответь только по приведённым нормативным фрагментам. Не добавляй фактов.",
        "summary_system": "Сделай краткое структурированное резюме только по тексту документа. Не выдумывай фактов.",
        "expansion_system": "Верни до пяти русских поисковых слов через запятую, без пояснений.",
    }
    try:
        loaded = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            return {key: str(loaded.get(key, value)) for key, value in defaults.items()}
    except (OSError, json.JSONDecodeError):
        pass
    return defaults


def load_corpus() -> list[dict[str, object]]:
    try:
        data = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"normative corpus is unavailable: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError("normative corpus must be a JSON array")
    return [item for item in data if isinstance(item, dict) and item.get("title") and item.get("text")]


def _tokens(text: str) -> set[str]:
    return {word for word in re.findall(r"[A-Za-zА-Яа-яЁё0-9-]{3,}", text.lower()) if word not in {"что", "как", "для", "или", "это", "при", "все", "the", "and"}}


def _current_documents(corpus: list[dict[str, object]]) -> list[dict[str, object]]:
    """Only infer currentness within one document family; never infer priority."""
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in corpus:
        grouped[str(item.get("document_id") or item.get("title"))].append(item)
    result: list[dict[str, object]] = []
    for versions in grouped.values():
        explicit = [x for x in versions if str(x.get("status", "")).lower() == "current"]
        if explicit:
            result.extend(explicit)
            continue
        dated = [x for x in versions if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(x.get("effective_date", "")))]
        if dated:
            result.append(max(dated, key=lambda x: str(x["effective_date"])))
        else:
            result.extend(versions)  # Ambiguous metadata: do not silently discard versions.
    return result


def _clauses(item: dict[str, object]) -> list[str]:
    raw = item.get("clauses")
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return [line.strip() for line in str(item.get("text", "")).splitlines() if line.strip()]


def retrieve_clauses(question: str, corpus: list[dict[str, object]] | None = None, limit: int = 5) -> dict[str, object]:
    if not question.strip():
        raise ValueError("question must not be empty")
    corpus = corpus if corpus is not None else load_corpus()
    query_words = _tokens(question)
    scored: list[tuple[int, dict[str, object], str]] = []
    for item in _current_documents(corpus):
        for clause in _clauses(item):
            words = _tokens(clause)
            score = len(query_words & words)
            if score:
                scored.append((score, item, clause))
    scored.sort(key=lambda row: (-row[0], str(row[1].get("title")), row[2]))
    results = [
        {"quote": clause, "score": score, "document": item["title"], "version": item.get("version", "не указана"),
         "effectiveDate": item.get("effective_date"), "priority": item.get("priority"),
         "priorityRank": item.get("priority_rank"), "documentId": item.get("document_id")}
        for score, item, clause in scored[:limit]
    ]
    return {"results": results, "retrieval": "offline_deterministic"}


def detect_conflicts(results: list[dict[str, object]]) -> dict[str, object]:
    prohibitions = [r for r in results if re.search(r"\b(?:запрещ\w*|нельзя|не\s+допуска\w*)", str(r["quote"]), re.I)]
    permissions = [r for r in results if re.search(r"\b(?:разреш\w*|допуска\w*|можно|вправе|имеет\s+право|может)\b", str(r["quote"]), re.I)]
    pairs = [
        {"prohibition": a, "permission": b}
        for a in prohibitions for b in permissions
        if a["documentId"] != b["documentId"] or a["version"] != b["version"]
    ]
    priorities = [x.get("priority") for x in results if x.get("priority") not in (None, "")]
    ranked_pairs = []
    for pair in pairs:
        ranked = []
        for source in (pair["prohibition"], pair["permission"]):
            rank = source.get("priorityRank")
            # A winning rule is allowed only for explicit numeric metadata.
            if isinstance(rank, bool) or not isinstance(rank, (int, float)):
                ranked = []
                break
            ranked.append((rank, source))
        if ranked and ranked[0][0] != ranked[1][0]:
            winning_rank, winning_source = min(ranked, key=lambda item: item[0])
            ranked_pairs.append({"pair": pair, "winner": winning_source, "priorityRank": winning_rank})
    # Do not use retrieval order to choose between separate contradictions that
    # have different explicitly ranked winners.
    winner_keys = {
        (str(entry["winner"].get("documentId")), str(entry["winner"].get("version")), entry["priorityRank"])
        for entry in ranked_pairs
    }
    winner = ranked_pairs[0]["winner"] if len(winner_keys) == 1 else None
    if winner:
        priority_message = f"Побеждает источник «{winner['document']}», версия {winner['version']}: explicit priority_rank={winner['priorityRank']}."
    elif pairs and priorities:
        priority_message = "Заданные метаданные приоритета: " + "; ".join(sorted({str(x) for x in priorities})) + ". Для выбора источника нет единого победителя по разным явным числовым priority_rank: система не предполагает приоритет."
    elif pairs:
        priority_message = "Приоритет между документами не указан: система его не предполагает."
    else:
        priority_message = ("Явных противоречий среди найденных фрагментов нет. Заданные метаданные приоритета: " + "; ".join(sorted({str(x) for x in priorities}))) if priorities else "Противоречий в найденных источниках нет."
    return {
        "detected": bool(pairs), "pairs": pairs,
        "priority": "; ".join(sorted({str(x) for x in priorities})) if priorities else None,
        "winner": winner,
        "priorityMessage": priority_message,
    }


def _optional_llm(prompt: str, system: str) -> str | None:
    config = active_detector_config()
    if not config.configured:
        return None
    outbound, _, mapping, policy = apply_policy(prompt, [])
    if not policy["allowed"]:
        return None
    try:
        return restore(call_provider(outbound, config=config, timeout=provider_timeout_seconds(config), system_prompt=system), mapping)
    except ProviderError:
        return None


def answer_normative_question(payload: dict[str, object]) -> dict[str, object]:
    question = str(payload.get("question", "")).strip()
    if not question:
        raise ValueError("question must not be empty")
    prompts = load_prompts()

    # Agentic-lite retrieval: use the fast local search first and invoke semantic
    # expansion only when lexical evidence is weak. This keeps the demo responsive.
    found = retrieve_clauses(question)
    results = found["results"]
    required_score = 1 if len(_tokens(question)) <= 2 else 2
    strong = bool(results and int(results[0].get("score", 0)) >= required_score)
    expanded = None
    if not strong:
        expanded = _optional_llm(question, prompts["expansion_system"])
        if expanded:
            found = retrieve_clauses(question + " " + expanded)
            results = found["results"]
            strong = bool(results and int(results[0].get("score", 0)) >= required_score)

    if not strong:
        return {
            "answer": "В предоставленных документах это не урегулировано. Рекомендуем обратиться к HR-партнёру.",
            "evidence": [],
            "conflicts": detect_conflicts([]),
            "mode": "offline_fallback",
            "expandedQuery": expanded,
        }

    conflict = detect_conflicts(results)
    evidence = "\n".join(f"[{r['document']}, версия {r['version']}] {r['quote']}" for r in results)
    priority_context = conflict["priorityMessage"] if conflict["detected"] else "Явного конфликта найденных норм нет."
    llm = _optional_llm(
        "Вопрос сотрудника: " + question
        + "\n\nНормативные фрагменты:\n" + evidence
        + "\n\nПроверка конфликта и приоритета: " + str(priority_context)
        + "\n\nОтветь максимум тремя короткими предложениями. Начни с «Да», «Нет» или «Зависит». "
          "Объясни решение простым языком и не добавляй фактов вне приведённых фрагментов.",
        prompts["query_system"],
    )
    plain = llm or "Офлайн-режим: " + " ".join(str(r["quote"]) for r in results[:2])
    return {
        "answer": plain,
        "evidence": results,
        "conflicts": conflict,
        "mode": "llm_grounded" if llm else "offline_fallback",
        "expandedQuery": expanded,
    }


def _summary_fields(text: str) -> dict[str, object]:
    lines = [x.strip(" -•\t") for x in text.splitlines() if x.strip()]
    choose = lambda patterns: [line for line in lines if any(re.search(p, line, re.I) for p in patterns)][:5]
    return {"topic": lines[0] if lines else "Не определена", "audience": choose([r"сотрудник", r"работник", r"руководител", r"hr", r"отдел"]),
            "requirements": choose([r"обязан", r"должен", r"требует"]), "prohibitions": choose([r"запрещ", r"нельзя", r"не допускается"]),
            "rights": choose([r"вправе", r"имеет право", r"может"])}


def summarize_document(payload: dict[str, object]) -> dict[str, object]:
    text = str(payload.get("text", "")).strip()
    if not text:
        raise ValueError("document text must not be empty")
    meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    current = _summary_fields(text)
    previous_text = str(payload.get("previousText", "")).strip()
    corpus = load_corpus()

    # A file uploaded from the governed corpus should not require the user to know
    # internal IDs. Exact text matching binds it to version metadata locally.
    normalized_text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    matched = next(
        (
            item for item in corpus
            if "\n".join(line.strip() for line in str(item.get("text", "")).splitlines() if line.strip()) == normalized_text
        ),
        None,
    )
    if matched:
        meta = matched

    if not previous_text and meta.get("document_id"):
        versions = [x for x in corpus if str(x.get("document_id")) == str(meta["document_id"]) and str(x.get("text")) != text]
        older = [x for x in versions if str(x.get("effective_date", "")) < str(meta.get("effective_date", "9999-99-99"))]
        if older:
            previous_text = str(max(older, key=lambda x: str(x.get("effective_date", ""))).get("text", ""))
    old_lines = set(_clauses({"text": previous_text}))
    new_lines = set(_clauses({"text": text}))
    current["changes_vs_previous"] = {"added": sorted(new_lines - old_lines), "removed": sorted(old_lines - new_lines), "available": bool(previous_text)}
    prompts = load_prompts()
    llm = _optional_llm("Документ:\n" + text + "\n\nВерни JSON с ключами topic, audience, requirements, prohibitions, rights.", prompts["summary_system"])
    # Deterministic structure is authoritative; model output is advisory text only.
    return {"summary": current, "narrative": llm, "mode": "llm_grounded" if llm else "offline_fallback"}


class Handler(BaseHTTPRequestHandler):
    server_version = "SecureLLMGateway/0.1"

    def log_message(self, format: str, *args: object) -> None:
        # Avoid logging request bodies or sensitive values. Keep only route/status metadata.
        super().log_message(format, *args)

    def _json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            body = INDEX_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/status":
            self._json(
                200,
                {
                    "detector": detector_status(),
                    "provider": provider_status(),
                    "mode": (
                        "CORPORATE"
                        if active_detector_config().profile == "CPS_INTERNAL_OPENAI_COMPAT"
                        else "DEMO"
                    ),
                    "fileIntake": {
                        "supportedExtensions": sorted(SUPPORTED_FILE_EXTENSIONS),
                        "maxBytes": MAX_FILE_BYTES,
                    },
                    "policy": {"rules": POLICY_RULES},
                },
            )
            return
        if path == "/api/corpus":
            corpus = load_corpus()
            self._json(200, {"documents": [{key: item.get(key) for key in ("document_id", "title", "version", "effective_date", "status", "priority", "priority_rank", "text")} for item in corpus]})
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/preflight":
                self._json(200, run_provider_preflight())
                return
            if path not in {"/api/file", "/api/detect", "/api/analyze", "/api/process", "/api/normative/question", "/api/normative/summary"}:
                self._json(404, {"error": "not_found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON object expected")
            if path == "/api/file":
                self._json(200, import_file_payload(payload))
            elif path == "/api/detect":
                self._json(200, detect_sensitive_terms(str(payload.get("text", ""))))
            elif path == "/api/analyze":
                self._json(200, analyze_payload(payload))
            elif path == "/api/normative/question":
                self._json(200, answer_normative_question(payload))
            elif path == "/api/normative/summary":
                self._json(200, summarize_document(payload))
            else:
                result = process_payload(payload)
                _PROVIDER_READINESS.update(state="PASS", message="Live-вызов провайдера: PASS. Реальный ответ получен.")
                self._json(200, result)
        except PolicyBlockedError as exc:
            self._json(
                403,
                {
                    "error": "policy_blocked",
                    "message": str(exc),
                    "policy": exc.policy,
                },
            )
        except ProviderError as exc:
            if path == "/api/detect":
                _DETECTOR_READINESS.update(state="FAIL", message=f"Автодетектор: FAIL — {exc}")
            else:
                _PROVIDER_READINESS.update(state="FAIL", message=f"Live-вызов провайдера: FAIL — {exc}")
            self._json(502, {"error": "provider_error", "message": str(exc)})
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"error": "invalid_request", "message": str(exc)})


def _create_server() -> tuple[ThreadingHTTPServer, int]:
    explicit_port = "APP_PORT" in os.environ
    candidates = [PORT] if explicit_port else list(range(PORT, PORT + 11))
    for port in candidates:
        try:
            return ThreadingHTTPServer((HOST, port), Handler), port
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE and not explicit_port:
                continue
            raise
    raise OSError(errno.EADDRINUSE, f"No free port in range {PORT}-{PORT + 10}")


def main() -> None:
    if not INDEX_FILE.exists():
        raise SystemExit(f"Missing UI asset: {INDEX_FILE}")
    server, bound_port = _create_server()
    print(f"Secure LLM Gateway: http://{HOST}:{bound_port}")
    if bound_port != PORT:
        print(f"Port {PORT} is busy; selected {bound_port}.")
    detector = detector_status()
    external = provider_status()
    print(f"Detector profile: {detector['profile']} ({'configured' if detector['configured'] else 'not configured'})")
    print(f"External processing: {external['profile']} ({'configured' if external['configured'] else 'manual copy'})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
