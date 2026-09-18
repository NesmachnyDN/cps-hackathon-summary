import base64
import json
import os
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

from app import (
    Entity,
    PolicyBlockedError,
    ProviderConfig,
    ProviderError,
    active_detector_config,
    active_provider_config,
    analyze_payload,
    analyze_document_tone,
    apply_policy,
    build_chat_request,
    call_provider,
    detect_sensitive_terms,
    deterministic_person_candidates,
    deterministic_sensitive_candidates,
    ensure_no_leak,
    external_provider_config,
    groq_proxy_url,
    extract_uploaded_text,
    import_file_payload,
    ingest_normative_document,
    load_corpus,
    load_prompts,
    normalize_chat_url,
    parse_detection_response,
    process_payload,
    provider_timeout_seconds,
    pseudonymize,
    restore,
    answer_normative_question,
    detect_conflicts,
    retrieve_clauses,
    summarize_document,
    _optional_llm_with_trace,
    _current_documents,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class CapturingOpener:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.request = None
        self.timeout = None

    def open(self, request, timeout=None):
        self.request = request
        self.timeout = timeout
        if self.error:
            raise self.error
        return FakeResponse(self.payload)


class PseudonymizationTests(unittest.TestCase):
    def test_explicit_terms_are_replaced_and_repeated_value_is_stable(self):
        text = "СеверГаз использует ДокФлоу-X. СеверГаз развивает ДокФлоу-X."
        outbound, entities, mapping = pseudonymize(
            text,
            [
                {"value": "СеверГаз", "category": "ORG"},
                {"value": "ДокФлоу-X", "category": "SYSTEM"},
            ],
        )
        self.assertNotIn("СеверГаз", outbound)
        self.assertNotIn("ДокФлоу-X", outbound)
        self.assertEqual(outbound.count("[[ORG_001]]"), 2)
        self.assertEqual(outbound.count("[[SYSTEM_001]]"), 2)
        self.assertEqual(len(entities), 2)
        self.assertEqual(restore(outbound, mapping), text)

    def test_distinct_values_get_distinct_tokens(self):
        outbound, entities, _ = pseudonymize(
            "Проект Альфа зависит от проекта Бета",
            [
                {"value": "Альфа", "category": "PROJECT"},
                {"value": "Бета", "category": "PROJECT"},
            ],
        )
        self.assertIn("[[PROJECT_001]]", outbound)
        self.assertIn("[[PROJECT_002]]", outbound)
        self.assertEqual({e.token for e in entities}, {"[[PROJECT_001]]", "[[PROJECT_002]]"})

    def test_demo_fixture_protects_person_surface_form(self):
        text = "Ответ направь Ивану Петрову на ivan.petrov@example.org."
        outbound, entities, mapping = pseudonymize(
            text,
            [{"value": "Ивану Петрову", "category": "PERSON"}],
        )
        self.assertNotIn("Ивану Петрову", outbound)
        self.assertIn("[[PERSON_001]]", outbound)
        self.assertEqual({e.category for e in entities}, {"PERSON", "EMAIL"})
        self.assertEqual(restore(outbound, mapping), text)

    def test_person_names_are_detected_deterministically(self):
        text = "Бизнес-владелец: Мария Орлова. Технический владелец: Сергей Волков."
        outbound, entities, mapping = pseudonymize(text, [])
        self.assertNotIn("Мария Орлова", outbound)
        self.assertNotIn("Сергей Волков", outbound)
        self.assertEqual([e.category for e in entities], ["PERSON", "PERSON"])
        self.assertEqual(restore(outbound, mapping), text)

    def test_deterministic_sensitive_candidates_use_explicit_context(self):
        source = (
            "Компания Альтаир Энерго переносит систему ДокФлоу-X в контур Платформа Вега. "
            "Интеграция с проектом Миграция-42. Инцидент INC-78421 на DB-PROD-01."
        )
        found = {item["value"]: item["category"] for item in deterministic_sensitive_candidates(source)}
        self.assertEqual(found["Альтаир Энерго"], "ORG")
        self.assertEqual(found["ДокФлоу-X"], "SYSTEM")
        self.assertEqual(found["Платформа Вега"], "SYSTEM")
        self.assertEqual(found["Миграция-42"], "PROJECT")
        self.assertEqual(found["INC-78421"], "SECRET")
        self.assertEqual(found["DB-PROD-01"], "SECRET")

    def test_detector_rejects_multiline_spans_and_corrects_categories(self):
        source = (
            "Контекст\nКомпания Альтаир Энерго переносит систему ДокФлоу-X "
            "в проект Миграция-42."
        )
        response = json.dumps(
            [
                {"value": "Контекст\nКомпания", "category": "PERSON"},
                {"value": "Альтаир Энерго", "category": "PERSON"},
                {"value": "ДокФлоу-X", "category": "PERSON"},
                {"value": "Миграция-42", "category": "SECRET"},
            ],
            ensure_ascii=False,
        )
        result = detect_sensitive_terms(source, detector_call=lambda text: response)
        found = {item["value"]: item["category"] for item in result["terms"]}
        self.assertNotIn("Контекст\nКомпания", found)
        self.assertEqual(found["Альтаир Энерго"], "ORG")
        self.assertEqual(found["ДокФлоу-X"], "SYSTEM")
        self.assertEqual(found["Миграция-42"], "PROJECT")

    def test_detector_supplements_missing_person_names(self):
        source = "Компания Альтаир Энерго. Ответственный: Мария Орлова. Платформа Вега доступна."
        result = detect_sensitive_terms(
            source,
            detector_call=lambda text: '[{"value":"Альтаир Энерго","category":"ORG"}]',
        )
        self.assertIn({"value": "Мария Орлова", "category": "PERSON"}, result["terms"])
        self.assertNotIn({"value": "Альтаир Энерго", "category": "PERSON"}, result["terms"])
        self.assertNotIn({"value": "Платформа Вега", "category": "PERSON"}, result["terms"])

    def test_email_and_phone_are_detected_automatically(self):
        text = "Пиши на user@example.org или +7 913 555-12-34."
        outbound, entities, mapping = pseudonymize(text, [])
        self.assertNotIn("user@example.org", outbound)
        self.assertNotIn("+7 913 555-12-34", outbound)
        self.assertEqual({e.category for e in entities}, {"EMAIL", "PHONE"})
        self.assertEqual(restore(outbound, mapping), text)

    def test_restore_keeps_unknown_tokens(self):
        restored = restore(
            "Ответ для [[ORG_001]] и [[UNKNOWN_999]]",
            {"[[ORG_001]]": "СеверГаз"},
        )
        self.assertEqual(restored, "Ответ для СеверГаз и [[UNKNOWN_999]]")

    def test_leak_check_fails_closed(self):
        entities = [Entity("СеверГаз", "ORG", "[[ORG_001]]")]
        with self.assertRaisesRegex(ValueError, "Leak check failed"):
            ensure_no_leak("Небезопасный текст СеверГаз", entities)

    def test_provider_request_contains_only_pseudonymized_text(self):
        request = build_chat_request("Риски для [[ORG_001]]")
        serialized = str(request)
        self.assertIn("[[ORG_001]]", serialized)
        self.assertNotIn("СеверГаз", serialized)
        self.assertEqual(request["model"], "openai/gpt-oss-120b")
        self.assertFalse(request["stream"])
        self.assertEqual(request["max_tokens"], 240)
        self.assertEqual(build_chat_request("x", max_tokens=1200)["max_tokens"], 1200)

    def test_analyze_payload_returns_local_restore_check(self):
        payload = analyze_payload(
            {
                "text": "СеверГаз: owner@example.org",
                "terms": [{"value": "СеверГаз", "category": "ORG"}],
            }
        )
        self.assertEqual(payload["localRestoreCheck"], "СеверГаз: owner@example.org")
        self.assertNotIn("СеверГаз", payload["outbound"])
        self.assertNotIn("owner@example.org", payload["outbound"])
        self.assertEqual(payload["protectedCount"], 2)

    def test_invalid_terms_shape_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "terms must be a list"):
            analyze_payload({"text": "x", "terms": "not-a-list"})

    def test_chat_url_normalization(self):
        self.assertEqual(
            normalize_chat_url("https://example.test"),
            "https://example.test/v1/chat/completions",
        )
        self.assertEqual(
            normalize_chat_url("https://example.test/v1"),
            "https://example.test/v1/chat/completions",
        )

    def test_call_provider_sends_only_pseudonymized_content(self):
        opener = CapturingOpener({"choices": [{"message": {"content": "Ответ [[ORG_001]]"}}]})
        config = ProviderConfig(
            profile="GROQ_TEMP_48H_TUN",
            base_url="https://example.test/v1",
            model="openai/gpt-oss-120b",
            api_key="test-key",
            network="SYSTEM_TUNNEL",
        )
        result = call_provider("Риски для [[ORG_001]]", config=config, opener=opener, timeout=7)
        body = opener.request.data.decode("utf-8")
        payload = json.loads(body)
        self.assertEqual(result, "Ответ [[ORG_001]]")
        self.assertIn("[[ORG_001]]", body)
        self.assertNotIn("СеверГаз", body)
        self.assertEqual(payload["max_completion_tokens"], 240)
        self.assertEqual(payload["reasoning_effort"], "low")
        self.assertNotIn("max_tokens", payload)
        self.assertEqual(opener.timeout, 7)
        self.assertEqual(opener.request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(opener.request.get_header("User-agent"), "SecureLLMGateway/0.1")
        self.assertEqual(opener.request.get_header("Accept"), "application/json")

    def test_internal_detector_gets_extended_configurable_timeout(self):
        config = ProviderConfig(
            profile="CPS_INTERNAL_OPENAI_COMPAT",
            base_url="http://internal.example/v1",
            model="internal-model",
            api_key=None,
            network="INTERNAL",
        )
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(provider_timeout_seconds(config), 90)
        with patch.dict(os.environ, {"CPS_LLM_TIMEOUT_SECONDS": "120"}, clear=True):
            self.assertEqual(provider_timeout_seconds(config), 120)
        with patch.dict(os.environ, {"CPS_LLM_TIMEOUT_SECONDS": "broken"}, clear=True):
            self.assertEqual(provider_timeout_seconds(config), 90)

    def test_process_payload_restores_known_tokens_and_keeps_unknown(self):
        payload = process_payload(
            {
                "text": "СеверГаз анализирует риски",
                "terms": [{"value": "СеверГаз", "category": "ORG"}],
            },
            provider_call=lambda outbound: "Ответ для [[ORG_001]] и [[UNKNOWN_999]]",
        )
        self.assertNotIn("СеверГаз", payload["outbound"])
        self.assertEqual(payload["providerResponse"], "Ответ для [[ORG_001]] и [[UNKNOWN_999]]")
        self.assertEqual(payload["restoredResponse"], "Ответ для СеверГаз и [[UNKNOWN_999]]")

    def test_invalid_provider_shape_is_explicit_error(self):
        opener = CapturingOpener({"unexpected": True})
        config = ProviderConfig("CPS_INTERNAL_OPENAI_COMPAT", "https://example.test", "model", None, "INTERNAL")
        with self.assertRaisesRegex(ProviderError, "unexpected shape"):
            call_provider("[[ORG_001]]", config=config, opener=opener)
        self.assertIsNone(opener.request.get_header("Authorization"))

    def test_http_error_surfaces_sanitized_provider_message(self):
        key = "temporary-secret-key"
        error_body = json.dumps({"error": {"message": f"Model blocked for key {key}"}}).encode("utf-8")
        error = HTTPError("https://example.test", 403, "Forbidden", {}, BytesIO(error_body))
        opener = CapturingOpener(error=error)
        config = ProviderConfig("GROQ_TEMP_48H_TUN", "https://example.test/v1", "model", key, "SYSTEM_TUNNEL")
        with self.assertRaises(ProviderError) as ctx:
            call_provider("[[ORG_001]]", config=config, opener=opener)
        message = str(ctx.exception)
        self.assertIn("403", message)
        self.assertIn("Model blocked", message)
        self.assertIn("[REDACTED]", message)
        self.assertNotIn(key, message)

    def test_cps_profile_requires_runtime_url_and_model_without_inventing_them(self):
        env = {
            "LLM_PROFILE": "cps",
            "CPS_LLM_BASE_URL": "https://internal.example",
            "CPS_LLM_MODEL": "internal-model",
        }
        with patch.dict(os.environ, env, clear=True):
            config = active_provider_config()
            request = build_chat_request("[[ORG_001]]")
        self.assertEqual(config.profile, "CPS_INTERNAL_OPENAI_COMPAT")
        self.assertEqual(config.network, "INTERNAL")
        self.assertTrue(config.configured)
        self.assertIsNone(config.api_key)
        self.assertEqual(request["model"], "internal-model")

    def test_cps_transport_uses_runtime_endpoint_without_fake_auth(self):
        opener = CapturingOpener({"choices": [{"message": {"content": "Ответ [[ORG_001]]"}}]})
        config = ProviderConfig(
            profile="CPS_INTERNAL_OPENAI_COMPAT",
            base_url="https://internal.example/service",
            model="internal-model",
            api_key=None,
            network="INTERNAL",
        )
        result = call_provider("[[ORG_001]]", config=config, opener=opener)
        self.assertEqual(result, "Ответ [[ORG_001]]")
        self.assertEqual(
            opener.request.full_url,
            "https://internal.example/service/v1/chat/completions",
        )
        self.assertIsNone(opener.request.get_header("Authorization"))
        body = json.loads(opener.request.data.decode("utf-8"))
        self.assertEqual(body["model"], "internal-model")
        self.assertEqual(body["messages"][-1]["content"], "[[ORG_001]]")
        self.assertNotIn("api.groq.com", opener.request.full_url)


    def test_policy_allows_transformed_content_and_counts_actions(self):
        result = analyze_payload(
            {
                "text": "СеверГаз: owner@example.org, +7 913 555-12-34.",
                "terms": [{"value": "СеверГаз", "category": "ORG"}],
            }
        )
        self.assertEqual(result["policy"]["decision"], "ALLOW")
        self.assertTrue(result["copyAllowed"])
        self.assertEqual(result["policy"]["counts"]["PSEUDONYMIZE"], 1)
        self.assertEqual(result["policy"]["counts"]["MASK"], 2)
        self.assertEqual(result["policy"]["counts"]["BLOCK"], 0)

    def test_policy_blocks_credential_before_provider_call(self):
        called = []
        payload = {
            "text": "СеверГаз. password=DEMO_ONLY_CREDENTIAL_2026",
            "terms": [{"value": "СеверГаз", "category": "ORG"}],
        }
        preview = analyze_payload(payload)
        self.assertEqual(preview["policy"]["decision"], "BLOCK")
        self.assertFalse(preview["copyAllowed"])
        self.assertNotIn("DEMO_ONLY_CREDENTIAL_2026", preview["outbound"])
        self.assertEqual(preview["policy"]["counts"]["BLOCK"], 1)
        with self.assertRaises(PolicyBlockedError):
            process_payload(
                payload,
                provider_call=lambda outbound: called.append(outbound) or "never",
            )
        self.assertEqual(called, [])

    def test_plain_text_file_is_extracted_locally(self):
        result = extract_uploaded_text(
            "incident.txt",
            "ДокФлоу-X и СеверГаз".encode("utf-8"),
        )
        self.assertEqual(result["extension"], ".txt")
        self.assertIn("ДокФлоу-X", result["text"])
        self.assertGreater(result["characters"], 0)

    def test_docx_text_is_extracted_without_external_dependencies(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Инцидент INC-78421</w:t></w:r></w:p>
    <w:p><w:r><w:t>Система ДокФлоу-X</w:t></w:r></w:p>
  </w:body>
</w:document>"""
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", xml)
        result = extract_uploaded_text("incident.docx", buffer.getvalue())
        self.assertEqual(result["extension"], ".docx")
        self.assertIn("Инцидент INC-78421", result["text"])
        self.assertIn("Система ДокФлоу-X", result["text"])

    def test_file_payload_decodes_base64_and_does_not_persist(self):
        encoded = base64.b64encode("Проект Миграция-42".encode("utf-8")).decode()
        result = import_file_payload(
            {"name": "request.md", "contentBase64": encoded}
        )
        self.assertEqual(result["file"]["name"], "request.md")
        self.assertEqual(result["text"], "Проект Миграция-42")

    def test_unsupported_file_type_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported file type"):
            extract_uploaded_text("scan.xlsx", b"not a spreadsheet")

    def test_invalid_pdf_is_reported_as_pdf_parse_error(self):
        with self.assertRaisesRegex(ValueError, "invalid or unsupported PDF"):
            extract_uploaded_text("scan.pdf", b"%PDF-demo")

    def test_groq_proxy_prefers_explicit_setting(self):
        env = {
            "GROQ_PROXY_URL": "http://127.0.0.1:10809",
            "HTTPS_PROXY": "http://fallback.example:3128",
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(groq_proxy_url(), "http://127.0.0.1:10809")

    def test_groq_proxy_can_be_disabled_explicitly(self):
        with patch.dict(os.environ, {"GROQ_PROXY_URL": "direct"}, clear=True):
            self.assertIsNone(groq_proxy_url())

    def test_corporate_profile_uses_cps_detector_and_disables_external_groq(self):
        env = {
            "LLM_PROFILE": "cps",
            "CPS_LLM_BASE_URL": "https://internal.example",
            "CPS_LLM_MODEL": "internal-model",
            "GROQ_API_KEY": "should-not-be-used",
        }
        with patch.dict(os.environ, env, clear=True):
            detector = active_detector_config()
            external = external_provider_config()
        self.assertEqual(detector.profile, "CPS_INTERNAL_OPENAI_COMPAT")
        self.assertEqual(detector.base_url, "https://internal.example")
        self.assertTrue(detector.configured)
        self.assertEqual(external.profile, "EXTERNAL_MANUAL_COPY")
        self.assertFalse(external.configured)
        self.assertIsNone(external.api_key)
        self.assertNotIn("groq", external.base_url.lower())
        with patch.dict(os.environ, env, clear=True):
            preview = analyze_payload(
                {
                    "text": "СеверГаз: owner@example.org",
                    "terms": [{"value": "СеверГаз", "category": "ORG"}],
                }
            )
        self.assertTrue(preview["manualCopyRequired"])
        self.assertIsNone(preview["providerRequestPreview"])

    def test_detection_parser_keeps_only_exact_source_values(self):
        source = "Альтаир Энерго использует DB-PROD-01. Email maria.orlova@example.org."
        response = """```json
[
  {"value":"Альтаир Энерго","category":"ORG"},
  {"value":"DB-PROD-01","category":"INFRA"},
  {"value":"Не существует","category":"SECRET"},
  {"value":"maria.orlova@example.org","category":"SECRET"}
]
```"""
        terms = parse_detection_response(response, source)
        self.assertEqual(
            terms,
            [
                {"value": "Альтаир Энерго", "category": "ORG"},
                {"value": "DB-PROD-01", "category": "SECRET"},
            ],
        )

    def test_auto_detector_returns_mapping_suggestions(self):
        source = "Система ДокФлоу-X связана с проектом Миграция-42."
        result = detect_sensitive_terms(
            source,
            detector_call=lambda text: json.dumps(
                [
                    {"value": "ДокФлоу-X", "category": "SYSTEM"},
                    {"value": "Миграция-42", "category": "PROJECT"},
                ],
                ensure_ascii=False,
            ),
        )
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["terms"][0]["value"], "ДокФлоу-X")
        self.assertEqual(result["terms"][1]["category"], "PROJECT")

    def test_corporate_provider_status_is_manual_not_failure(self):
        env = {
            "LLM_PROFILE": "cps",
            "CPS_LLM_BASE_URL": "https://internal.example",
            "CPS_LLM_MODEL": "internal-model",
        }
        with patch.dict(os.environ, env, clear=True):
            from app import provider_status
            status = provider_status()
        self.assertEqual(status["profile"], "EXTERNAL_MANUAL_COPY")
        self.assertEqual(status["readiness"], "MANUAL")
        self.assertFalse(status["configured"])

    def test_corporate_mode_process_requires_manual_copy_not_groq(self):
        env = {
            "LLM_PROFILE": "cps",
            "CPS_LLM_BASE_URL": "https://internal.example",
            "CPS_LLM_MODEL": "internal-model",
            "GROQ_API_KEY": "should-not-be-used",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ProviderError, "copy the safe outbound"):
                process_payload(
                    {
                        "text": "СеверГаз анализирует риски",
                        "terms": [{"value": "СеверГаз", "category": "ORG"}],
                    }
                )


class NormativeMvpTests(unittest.TestCase):
    def test_retrieval_uses_current_version_only(self):
        corpus = [
            {"document_id": "a", "title": "Правило", "version": "1", "effective_date": "2025-01-01", "status": "archived", "text": "Удалённая работа разрешена один день."},
            {"document_id": "a", "title": "Правило", "version": "2", "effective_date": "2026-01-01", "status": "current", "text": "Удалённая работа разрешена два дня."},
        ]
        result = retrieve_clauses("разрешена удалённая работа", corpus)
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["version"], "2")

    def test_retrieval_distinguishes_similar_roles_with_inflection(self):
        corpus = [
            {
                "document_id": "lead",
                "title": "ДИ — Ведущий специалист",
                "version": "2025",
                "status": "current",
                "position": "Ведущий специалист",
                "department": "Подбор персонала",
                "clauses": [{
                    "quote": "На должность ведущего специалиста назначается лицо со стажем не менее 1 года.",
                    "search_text": "Ведущий специалист Подбор персонала Общие положения На должность ведущего специалиста назначается лицо со стажем не менее 1 года.",
                    "section": "Общие положения",
                }],
                "text": "На должность ведущего специалиста назначается лицо со стажем не менее 1 года.",
            },
            {
                "document_id": "chief",
                "title": "ДИ — Главный специалист",
                "version": "2025",
                "status": "current",
                "position": "Главный специалист",
                "department": "Подбор персонала",
                "clauses": [{
                    "quote": "На должность главного специалиста назначается лицо со стажем не менее 5 лет.",
                    "search_text": "Главный специалист Подбор персонала Общие положения На должность главного специалиста назначается лицо со стажем не менее 5 лет.",
                    "section": "Общие положения",
                }],
                "text": "На должность главного специалиста назначается лицо со стажем не менее 5 лет.",
            },
        ]
        result = retrieve_clauses("Какой стаж нужен ведущему специалисту?", corpus)
        self.assertEqual(result["results"][0]["documentId"], "lead")
        self.assertIn("1 года", result["results"][0]["quote"])

    def test_conflict_reports_numeric_priority_winner(self):
        results = [
            {"quote": "Удалённая работа запрещена.", "documentId": "a", "version": "1", "priority": "уровень 1", "priorityRank": 1, "document": "ИБ"},
            {"quote": "Работник вправе работать дистанционно.", "documentId": "b", "version": "2", "priority": "уровень 2", "priorityRank": 2, "document": "Удалённая работа"},
        ]
        conflict = detect_conflicts(results)
        self.assertTrue(conflict["detected"])
        self.assertEqual(conflict["winner"]["documentId"], "a")

    def test_conflict_never_invents_absent_priority(self):
        conflict = detect_conflicts([
            {"quote": "Работа запрещена.", "documentId": "a", "version": "1", "priority": None},
            {"quote": "Работа разрешена.", "documentId": "b", "version": "1", "priority": None},
        ])
        self.assertTrue(conflict["detected"])
        self.assertIsNone(conflict["priority"])
        self.assertIsNone(conflict["winner"])
        self.assertIn("не предполагает", conflict["priorityMessage"])

    def test_explicit_current_overrides_newer_archived_version(self):
        corpus = [
            {"document_id": "a", "title": "Правило", "version": "1", "effective_date": "2026-12-01", "status": "archived", "text": "old"},
            {"document_id": "a", "title": "Правило", "version": "2", "effective_date": "2026-01-01", "status": "current", "text": "current"},
        ]
        self.assertEqual(_current_documents(corpus)[0]["version"], "2")

    def test_prompts_remain_in_external_json_file(self):
        self.assertIn("только", load_prompts()["query_system"].lower())
        self.assertTrue(os.path.exists("prompts.json"))

    def test_no_answer_recommends_hr(self):
        result = answer_normative_question({"question": "Как заказать корпоративный автобус на Марс?"})
        self.assertEqual(result["evidence"], [])
        self.assertEqual(result["mode"], "not_regulated")
        self.assertIn("не урегулировано", result["answer"])
        self.assertIn("HR", result["answer"])

    def test_unanchored_incidental_match_does_not_trigger_llm_expansion(self):
        corpus = [{
            "document_id": "role",
            "title": "Должностная инструкция",
            "version": "2025",
            "status": "current",
            "clauses": ["На период командировки обязанности исполняет замещающее лицо."],
            "text": "На период командировки обязанности исполняет замещающее лицо.",
        }]
        with patch("app.load_corpus", return_value=corpus), patch("app._optional_llm") as llm:
            result = answer_normative_question({
                "question": "Как оплачивается командировка в субботу и воскресенье?"
            })
        self.assertEqual(result["mode"], "not_regulated")
        self.assertEqual(result["evidence"], [])
        llm.assert_not_called()

    def test_summary_contains_fields_and_version_diff(self):
        result = summarize_document({
            "text": "Положение\nРаботник обязан согласовать отпуск.\nРаботник вправе выбрать дату.",
            "previousText": "Положение\nРаботник обязан согласовать отпуск.",
        })
        summary = result["summary"]
        self.assertIn("topic", summary)
        self.assertIn("Работник обязан", summary["requirements"][0])
        self.assertTrue(summary["changes_vs_previous"]["available"])
        self.assertIn("Работник вправе выбрать дату.", summary["changes_vs_previous"]["added"])

    def test_summary_uses_valid_grounded_ai_structure(self):
        ai = json.dumps({
            "topic": "Правила отпуска",
            "audience": ["Работники"],
            "requirements": ["Согласовать отпуск"],
            "prohibitions": ["Нет"],
            "rights": ["Выбрать дату"],
        }, ensure_ascii=False)
        with patch("app._optional_llm", return_value=ai):
            result = summarize_document({
                "text": "Положение\nРаботник обязан согласовать отпуск.\nРаботник вправе выбрать дату."
            })
        self.assertEqual(result["mode"], "llm_grounded")
        self.assertEqual(result["summary"]["topic"], "Правила отпуска")
        self.assertEqual(result["summary"]["requirements"], ["Согласовать отпуск"])

    def test_uploaded_demo_document_auto_binds_to_previous_version(self):
        text = Path("demo/remote-work-v2.txt").read_text(encoding="utf-8")
        result = summarize_document({"text": text, "metadata": {"document_id": "remote-work-v2.txt"}})
        changes = result["summary"]["changes_vs_previous"]
        self.assertTrue(changes["available"])
        self.assertTrue(any("двух дней" in item for item in changes["added"]))

class DemoHardeningTests(unittest.TestCase):
    def test_protected_llm_trace_masks_outbound_and_restores_response(self):
        config = ProviderConfig(
            profile="GROQ_TEMP_48H_TUN",
            base_url="https://api.example.test/openai/v1",
            model="demo-model",
            api_key="test-only",
            network="SYSTEM_TUNNEL",
        )
        prompt = (
            "Компания СеверГаз использует систему ДокФлоу-X и проект Миграция-42. "
            "Контакт demo.user@example.org."
        )
        provider_response = (
            "Ответ для [[ORG_001]], [[SYSTEM_001]], [[PROJECT_001]], "
            "[[EMAIL_MASKED_001]]."
        )
        with patch("app.active_detector_config", return_value=config), patch(
            "app.call_provider", return_value=provider_response
        ):
            result, trace = _optional_llm_with_trace(
                prompt, "system", protected_mode=True, stage="demo"
            )
        self.assertEqual(trace["status"], "PASS")
        self.assertNotIn("СеверГаз", trace["outboundPrompt"])
        self.assertNotIn("ДокФлоу-X", trace["outboundPrompt"])
        self.assertNotIn("demo.user@example.org", trace["outboundPrompt"])
        self.assertNotIn("СеверГаз", json.dumps(trace["providerRequest"], ensure_ascii=False))
        self.assertIn("СеверГаз", json.dumps(trace["entities"], ensure_ascii=False))
        self.assertIn("СеверГаз", result)
        self.assertIn("ДокФлоу-X", result)
        self.assertIn("demo.user@example.org", result)

    def test_unavailable_provider_still_exposes_safe_outbound_preview(self):
        config = ProviderConfig(
            profile="GROQ_TEMP_48H_TUN",
            base_url="https://api.example.test/openai/v1",
            model="demo-model",
            api_key=None,
            network="SYSTEM_TUNNEL",
        )
        with patch("app.active_detector_config", return_value=config), patch(
            "app.call_provider"
        ) as provider:
            result, trace = _optional_llm_with_trace(
                "Компания СеверГаз. Контакт demo.user@example.org.",
                "system",
                protected_mode=True,
            )
        self.assertIsNone(result)
        self.assertEqual(trace["status"], "PROVIDER_UNAVAILABLE")
        self.assertNotIn("СеверГаз", trace["outboundPrompt"])
        self.assertIsNotNone(trace["providerRequest"])
        provider.assert_not_called()

    def test_unprotected_mode_still_blocks_credentials(self):
        config = ProviderConfig(
            profile="GROQ_TEMP_48H_TUN",
            base_url="https://api.example.test/openai/v1",
            model="demo-model",
            api_key="test-only",
            network="SYSTEM_TUNNEL",
        )
        with patch("app.active_detector_config", return_value=config), patch(
            "app.call_provider"
        ) as provider:
            result, trace = _optional_llm_with_trace(
                "password=DEMO_ONLY_CREDENTIAL_2026",
                "system",
                protected_mode=False,
            )
        self.assertIsNone(result)
        self.assertEqual(trace["status"], "BLOCKED")
        provider.assert_not_called()

    def test_uploaded_normative_document_persists_and_joins_corpus(self):
        with TemporaryDirectory(dir=Path.cwd()) as tmp:
            root = Path(tmp)
            base = root / "base.json"
            extra = root / "uploaded.json"
            uploads = root / "files"
            base.write_text(json.dumps([{
                "document_id": "base", "title": "Базовый документ",
                "version": "1", "status": "current", "text": "Базовая норма."
            }], ensure_ascii=False), encoding="utf-8")
            encoded = base64.b64encode(
                "Положение о доступе\nРаботник обязан согласовать доступ к системе.".encode("utf-8")
            ).decode()
            with patch("app.CORPUS_PATH", base), patch(
                "app.UPLOADED_CORPUS_PATH", extra
            ), patch("app.KNOWLEDGE_UPLOAD_DIR", uploads):
                result = ingest_normative_document({
                    "name": "access-policy.txt", "contentBase64": encoded
                })
                corpus = load_corpus()
            self.assertTrue((uploads / "access-policy.txt").exists())
            self.assertEqual(result["corpusSize"], 2)
            self.assertEqual(len(corpus), 2)
            self.assertEqual(corpus[-1]["source_file"], "access-policy.txt")

    def test_custom_protection_policy_changes_outbound_and_restores_locally(self):
        original = (
            "Компания СеверГаз использует систему ДокФлоу-X. "
            "Контакт demo.user@example.org."
        )
        result = analyze_payload(
            {
                "text": original,
                "terms": [],
                "protectionPolicy": {"ORG": "ALLOW", "SYSTEM": "PSEUDONYMIZE", "EMAIL": "MASK"},
            }
        )
        self.assertIn("СеверГаз", result["outbound"])
        self.assertNotIn("ДокФлоу-X", result["outbound"])
        self.assertNotIn("demo.user@example.org", result["outbound"])
        self.assertEqual(result["localRestoreCheck"], original)
        self.assertEqual(result["policy"]["actions"]["ORG"], "ALLOW")
        detected = {(x["category"], x["action"]) for x in result["detectedTerms"]}
        self.assertIn(("ORG", "ALLOW"), detected)
        self.assertIn(("SYSTEM", "PSEUDONYMIZE"), detected)
        self.assertIn(("EMAIL", "MASK"), detected)

    def test_credentials_policy_cannot_be_weakened(self):
        with self.assertRaises(ValueError):
            analyze_payload(
                {
                    "text": "password=DEMO_ONLY_CREDENTIAL_2026",
                    "terms": [],
                    "protectionPolicy": {"CREDENTIAL": "ALLOW"},
                }
            )

    def test_summary_forwards_selected_protection_policy(self):
        with patch("app._optional_llm", return_value=None) as llm:
            summarize_document(
                {
                    "text": "Положение\nКомпания СеверГаз обязана согласовать доступ.",
                    "protectionPolicy": {"ORG": "ALLOW"},
                }
            )
        self.assertEqual(llm.call_args.kwargs["protection_policy"]["ORG"], "ALLOW")
        self.assertEqual(llm.call_args.kwargs["protection_policy"]["CREDENTIAL"], "BLOCK")

    def test_privacy_ui_exposes_real_policy_preview(self):
        html = Path("static/index.html").read_text(encoding="utf-8")
        self.assertIn('data-panel="privacy"', html)
        self.assertIn('id="previewPrivacy"', html)
        self.assertIn('data-policy="ORG"', html)
        self.assertIn('data-policy="EMAIL"', html)
        self.assertIn("Безопасные данные для внешнего AI", html)
        self.assertIn("/api/analyze", html)

    def test_demo_ui_contains_protected_mode_ingest_and_seven_questions(self):
        html = Path("static/index.html").read_text(encoding="utf-8")
        self.assertIn('id="protectedMode"', html)
        self.assertIn("/api/normative/ingest", html)
        demo_select = html.split('<select id="demoQuestion">', 1)[1].split("</select>", 1)[0]
        self.assertEqual(demo_select.count("<option"), 8)


class ToneMapTests(unittest.TestCase):
    def test_complex_directive_fragment_scores_worse_than_plain_fragment(self):
        plain = (
            "Сотрудник подаёт заявление руководителю. "
            "Руководитель отвечает в течение трёх рабочих дней."
        )
        complex_fragment = (
            "В соответствии с настоящим положением работник обязан в установленном "
            "порядке осуществлять предоставление вышеуказанных сведений посредством "
            "корпоративной системы; при этом не допускается направление информации "
            "иным способом, а также необходимо обеспечить предварительное согласование."
        )
        result = analyze_document_tone({"text": plain + "\n\n" + complex_fragment})
        self.assertEqual(result["summary"]["fragmentCount"], 2)
        first, second = result["fragments"]
        self.assertGreater(second["complexity"], first["complexity"])
        self.assertTrue(second["rewriteRecommended"])
        self.assertIn(second["tone"], {"Директивный", "Жёсткий"})
        self.assertTrue(result["recommendations"])

    def test_tone_map_rejects_empty_document(self):
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            analyze_document_tone({"text": "  "})

    def test_supportive_fragment_keeps_consistent_overall_tone(self):
        result = analyze_document_tone(
            {"text": "Сотрудник может обратиться за помощью к наставнику при необходимости."}
        )
        self.assertEqual(result["fragments"][0]["tone"], "Поддерживающий")
        self.assertEqual(result["summary"]["tone"], "Поддерживающий")

    def test_tone_map_ui_is_isolated_in_own_tab(self):
        html = Path("static/index.html").read_text(encoding="utf-8")
        self.assertIn('data-panel="tone"', html)
        self.assertIn('id="toneCorpusSelect"', html)
        self.assertIn('id="toneFile"', html)
        self.assertIn('id="complexityStrip"', html)
        self.assertIn('id="toneStrip"', html)
        self.assertIn("/api/normative/tone-map", html)


if __name__ == "__main__":
    unittest.main()
