from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

MAX_ANALYZED_CHARS = 200_000

BUREAUCRATIC_MARKERS = (
    "в соответствии с", "в целях", "в части", "в случае",
    "осуществляется", "осуществление", "посредством", "настоящ*",
    "вышеуказан*", "нижеследующ*", "подлежит",
    "в установленном порядке", "при наличии",
)
DIRECTIVE_MARKERS = (
    "должен", "должна", "должны", "обязан", "обязана", "обязаны",
    "необходимо", "требуется", "следует", "подлежит",
)
PROHIBITION_MARKERS = (
    "запрещ*", "не допуска*",
    "не вправе", "не должен", "не должна", "не должны",
)
SUPPORTIVE_MARKERS = (
    "может", "могут", "вправе", "имеет право",
    "рекомендуется", "при необходимости", "поддерж*", "помощ*",
)


def _bounded_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _marker_hits(lowered: str, markers: Iterable[str]) -> list[str]:
    hits: list[str] = []
    for marker in markers:
        if marker.endswith("*"):
            stem = marker[:-1]
            pattern = rf"(?<![\w-]){re.escape(stem)}[\w-]*"
            label = stem
        else:
            pattern = rf"(?<![\w-]){re.escape(marker)}(?![\w-])"
            label = marker
        hits.extend([label] * len(re.findall(pattern, lowered)))
    return hits


def _tone_blocks(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [
        part.strip()
        for part in re.split(r"\n\s*\n+", normalized)
        if part.strip()
    ]
    if len(paragraphs) <= 2:
        line_parts = [
            line.strip()
            for line in normalized.splitlines()
            if len(line.strip()) >= 30
        ]
        if len(line_parts) > len(paragraphs):
            paragraphs = line_parts
    if not paragraphs:
        paragraphs = [normalized.strip()]
    blocks: list[str] = []
    for paragraph in paragraphs:
        compact = re.sub(r"[ \t]+", " ", paragraph).strip()
        if len(compact) < 25:
            continue
        if len(compact) <= 900:
            blocks.append(compact)
            continue
        sentences = [
            part.strip()
            for part in re.split(r"(?<=[.!?])\s+", compact)
            if part.strip()
        ]
        current: list[str] = []
        current_len = 0
        for sentence in sentences:
            if current and current_len + len(sentence) > 760:
                blocks.append(" ".join(current))
                current = []
                current_len = 0
            current.append(sentence)
            current_len += len(sentence) + 1
        if current:
            blocks.append(" ".join(current))

    if len(blocks) > 80:
        merged: list[str] = []
        stride = max(2, (len(blocks) + 59) // 60)
        for index in range(0, len(blocks), stride):
            merged.append(" ".join(blocks[index:index + stride]))
        blocks = merged
    return blocks


def _tone_fragment(text: str, index: int) -> dict[str, object]:
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9-]+", text)
    word_count = max(1, len(words))
    sentence_parts = [
        part for part in re.split(r"[.!?]+(?:\s+|$)", text)
        if part.strip()
    ]
    sentence_count = max(1, len(sentence_parts))
    avg_sentence_words = word_count / sentence_count
    long_words = [word for word in words if len(word) >= 12]
    long_ratio = len(long_words) / word_count
    lowered = text.lower()

    bureaucracy = _marker_hits(lowered, BUREAUCRATIC_MARKERS)
    directives = _marker_hits(lowered, DIRECTIVE_MARKERS)
    prohibitions = _marker_hits(lowered, PROHIBITION_MARKERS)
    supportive = _marker_hits(lowered, SUPPORTIVE_MARKERS)
    passive_count = sum(
        1
        for word in words
        if re.search(
            r"(?:ется|ются|ировано|ирована|ированы|ируемый|яемый|аемый)$",
            word.lower(),
        )
    )
    dense_punctuation = text.count(";") + text.count("(") + text.count(")")

    complexity = _bounded_score(
        10
        + min(36, max(0.0, avg_sentence_words - 8) * 2.25)
        + min(18, long_ratio * 90)
        + min(20, len(bureaucracy) * 4.5)
        + min(8, passive_count * 2)
        + min(8, dense_punctuation * 1.25)
        + min(8, max(0, word_count - 75) / 10)
    )
    pressure = _bounded_score(
        8
        + min(52, len(directives) * 11 + len(prohibitions) * 18)
        + min(
            18,
            max(0, len(directives) + len(prohibitions) - len(supportive)) * 5,
        )
    )
    if complexity >= 76:
        difficulty, severity = "Очень сложно", "critical"
    elif complexity >= 58:
        difficulty, severity = "Сложно", "high"
    elif complexity >= 38:
        difficulty, severity = "Умеренно", "medium"
    else:
        difficulty, severity = "Понятно", "low"

    if pressure >= 31:
        tone = "Жёсткий"
    elif pressure >= 24:
        tone = "Директивный"
    elif supportive and pressure < 24:
        tone = "Поддерживающий"
    else:
        tone = "Нейтральный"

    reasons: list[str] = []
    issue_codes: list[str] = []
    suggestions: list[str] = []
    if avg_sentence_words >= 22:
        reasons.append(
            f"Длинные предложения: в среднем {avg_sentence_words:.0f} слов."
        )
        issue_codes.append("long_sentences")
        suggestions.append(
            "Разбить длинные предложения: одна мысль или требование — одно предложение."
        )
    if long_ratio >= 0.16:
        reasons.append(
            f"Много длинных слов: {round(long_ratio * 100)}% слов содержат 12+ символов."
        )
        issue_codes.append("long_words")
        suggestions.append(
            "Заменить сложные отглагольные существительные и редкие термины "
            "на более прямые формулировки."
        )
    if bureaucracy:
        examples = ", ".join(dict.fromkeys(bureaucracy[:3]))
        reasons.append(f"Канцелярские конструкции: {examples}.")
        issue_codes.append("bureaucracy")
        suggestions.append(
            "Упростить канцелярские обороты: писать через действие, исполнителя и результат."
        )
    if passive_count >= 2:
        reasons.append(f"Безличные/пассивные конструкции: {passive_count}.")
        issue_codes.append("passive")
        suggestions.append(
            "По возможности назвать исполнителя и использовать активный залог."
        )
    if dense_punctuation >= 5:
        reasons.append(
            "Плотная синтаксическая конструкция: много скобок и точек с запятой."
        )
        issue_codes.append("dense_syntax")
        suggestions.append(
            "Вынести условия и исключения в отдельные пункты или маркированный список."
        )
    if len(directives) + len(prohibitions) >= 2:
        reasons.append(
            f"Высокая директивность: {len(directives)} обязательств "
            f"и {len(prohibitions)} запретов."
        )
        issue_codes.append("directive")
        suggestions.append(
            "Сгруппировать обязанности и запреты, рядом кратко пояснить цель требования."
        )
    if word_count >= 110:
        reasons.append(f"Крупный текстовый блок: {word_count} слов.")
        issue_codes.append("large_block")
        suggestions.append(
            "Разделить блок подзаголовками или короткими смысловыми пунктами."
        )
    if not reasons:
        reasons.append(
            "Фрагмент читается относительно легко: критичных факторов сложности не обнаружено."
        )
    if not suggestions:
        suggestions.append("Сохранять текущую структуру и прямой порядок слов.")

    return {
        "index": index,
        "text": text,
        "complexity": complexity,
        "clarity": 100 - complexity,
        "difficulty": difficulty,
        "severity": severity,
        "tone": tone,
        "pressure": pressure,
        "wordCount": word_count,
        "sentenceCount": sentence_count,
        "avgSentenceWords": round(avg_sentence_words, 1),
        "reasons": reasons[:4],
        "suggestions": suggestions[:3],
        "issueCodes": issue_codes,
        "rewriteRecommended": complexity >= 58 or pressure >= 31,
    }


def analyze_document_tone(payload: dict[str, object]) -> dict[str, object]:
    text = str(payload.get("text", "")).strip()
    if not text:
        raise ValueError("document text must not be empty")
    if len(text) > MAX_ANALYZED_CHARS:
        raise ValueError("document text is too large")

    blocks = _tone_blocks(text)
    if not blocks:
        raise ValueError("document contains no analyzable text fragments")
    fragments = [
        _tone_fragment(block, index + 1)
        for index, block in enumerate(blocks)
    ]
    total_words = sum(int(item["wordCount"]) for item in fragments) or 1
    average_complexity = _bounded_score(
        sum(
            int(item["complexity"]) * int(item["wordCount"])
            for item in fragments
        ) / total_words
    )
    average_pressure = _bounded_score(
        sum(
            int(item["pressure"]) * int(item["wordCount"])
            for item in fragments
        ) / total_words
    )
    difficult = [
        item for item in fragments if int(item["complexity"]) >= 58
    ]
    very_difficult = [
        item for item in fragments if int(item["complexity"]) >= 76
    ]
    rewrite = [item for item in fragments if bool(item["rewriteRecommended"])]

    issue_counts: defaultdict[str, int] = defaultdict(int)
    for item in fragments:
        for code in item["issueCodes"]:
            issue_counts[str(code)] += 1
    issue_advice = {
        "long_sentences": "Сократить длинные предложения и оставить по одной мысли в каждом.",
        "bureaucracy": "Заменить канцелярские обороты на прямые глаголы и понятные действия.",
        "directive": "Разделить обязанности, запреты и пояснение цели требования.",
        "long_words": "Упростить терминологию там, где точность от этого не страдает.",
        "passive": "Чаще указывать конкретного исполнителя действия.",
        "dense_syntax": "Вынести условия и исключения в отдельные пункты.",
        "large_block": "Добавить подзаголовки и короткие смысловые блоки.",
    }
    recommendations = [
        issue_advice[code]
        for code, _ in sorted(
            issue_counts.items(),
            key=lambda pair: (-pair[1], pair[0]),
        )
        if code in issue_advice
    ][:4]
    if not recommendations:
        recommendations = [
            "Сохранить текущую структуру; документ не содержит выраженных зон сложности."
        ]

    if average_complexity >= 58 or len(difficult) / len(fragments) >= 0.35:
        verdict = "Нужна редакторская адаптация"
    elif average_complexity >= 38 or difficult:
        verdict = "Есть зоны для упрощения"
    else:
        verdict = "Документ в целом понятный"

    tone_counts: defaultdict[str, int] = defaultdict(int)
    for item in fragments:
        tone_counts[str(item["tone"])] += 1
    supportive_share = tone_counts["Поддерживающий"] / len(fragments)
    if average_pressure >= 31:
        overall_tone = "Жёсткий"
    elif average_pressure >= 24:
        overall_tone = "Директивный"
    elif (
        supportive_share >= 0.33
        and tone_counts["Поддерживающий"]
        > tone_counts["Директивный"] + tone_counts["Жёсткий"]
    ):
        overall_tone = "Поддерживающий"
    else:
        overall_tone = "Нейтральный"

    meta = (
        payload.get("metadata")
        if isinstance(payload.get("metadata"), dict)
        else {}
    )
    top_fragments = sorted(
        fragments,
        key=lambda item: (
            int(item["complexity"]),
            int(item["pressure"]),
        ),
        reverse=True,
    )[:5]
    return {
        "source": {
            "documentId": meta.get("document_id"),
            "title": (
                meta.get("title")
                or meta.get("document_id")
                or "Загруженный документ"
            ),
            "version": meta.get("version"),
        },
        "summary": {
            "verdict": verdict,
            "clarityIndex": 100 - average_complexity,
            "complexity": average_complexity,
            "tone": overall_tone,
            "pressure": average_pressure,
            "fragmentCount": len(fragments),
            "difficultCount": len(difficult),
            "veryDifficultCount": len(very_difficult),
            "rewriteCount": len(rewrite),
        },
        "fragments": fragments,
        "topFragmentIndexes": [
            int(item["index"]) for item in top_fragments
        ],
        "recommendations": recommendations,
        "method": (
            "Локальный анализ структуры и языка: "
            "данные документа не передаются во внешний AI."
        ),
    }
