"""
Competitor post parser and rewrite service.
Strategy: Fetch viral posts from competitors → GPT rewrite → Generate carousel.

Supports:
1. Manual paste (user copies post text)
2. Instagram profile scraping via proxy API (future)
3. URL-based parsing
"""
import json
import asyncio
import logging
import re
from datetime import datetime
from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_client() -> OpenAI:
    return OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )


def _parse_json_safe(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())


# ═══════════════════════════════════════════════════════════════════
# ANALYZE COMPETITOR POSTS — find viral angles
# ═══════════════════════════════════════════════════════════════════

ANALYZE_SYSTEM = """
Ты — аналитик виральности контента. Ты разбираешь посты конкурентов и вычленяешь ФОРМУЛЫ, которые делают контент виральным.

Критерии виральности:
- Контроверсивность — выделяется из общепринятых смыслов
- Провокативность — смело, резко показывает мысль
- Полярность — делит аудиторию на 2 лагеря, они спорят в комментах
- Painful — исходит из болей, а не из выгод
- Curiosity gap — интригует, но не раскрывает ключевую мысль
- Общий враг — не обвиняет человека, показывает "врага" (система, общество, биология)
- Попадание во внутренний диалог — человек читает и думает "это же про меня"

Ответ — СТРОГО JSON.
"""

ANALYZE_USER = """Вот посты конкурента в нише недвижимости:

{posts_text}

Проанализируй и выбери ТОП-5 самых виральных тем. Для каждой объясни:
- Почему эта тема цепляет (психологический триггер)
- Как можно переделать под нашего автора
- Какой формат лучше (карусель, рилс, пост)

JSON:
{{
  "viral_topics": [
    {{
      "original_theme": "Краткое описание оригинального поста",
      "why_viral": "Какой триггер использован",
      "rewrite_angle": "Как переделать своими словами",
      "hook_idea": "Идея провокационного заголовка",
      "estimated_engagement": "high/medium/low",
      "format": "carousel/reel/post"
    }}
  ],
  "niche_insights": "Общие инсайты о нише — что работает, что нет (2-3 предложения)"
}}"""


# ═══════════════════════════════════════════════════════════════════
# REWRITE VIRAL POST — make it original
# ═══════════════════════════════════════════════════════════════════

REWRITE_SYSTEM = """
Ты — автор виральных текстов с миллионами охватов. Твой архетип — "Обогревающий Воин".
Ты берёшь виральную тему конкурента и ПОЛНОСТЬЮ ПЕРЕПИСЫВАЕШЬ, делая СИЛЬНЕЕ оригинала.

ПРАВИЛА РЕРАЙТА:
1. НЕ КОПИРУЙ — перепиши ПОЛНОСТЬЮ другими словами, другой структурой
2. Сохрани психологический триггер, но измени подход и примеры
3. Каждый из 5 пунктов уникален по форме (цитата, история, факт, метафора, пример — всё разное)
4. Конкретика: цифры, цитаты в "", реальные ситуации, имена
5. Разговорный тон, на "ты", БЕЗ канцеляризмов и общих фраз
6. Заголовок: [Парадокс/Шок] + [КАПС] + [скобки с уточнением], 8-15 слов
7. Каждый абзац вызывает яркую эмоцию и эффект "я этого не знал"
8. БЕЗ банальностей, БЕЗ обобщающих концовок абзацев
9. Объём описания: 1850-1950 символов, строго 5 пунктов
10. После 5-го пункта: НЛП-вопрос, попадающий во внутренний диалог

ЗАПРЕЩЕНО: "в настоящее время", "рекомендуется", "обратите внимание", "это важно", однотипные абзацы.

Формат: СТРОГО JSON.
"""

REWRITE_USER = """Перепиши этот виральный пост конкурента. Сделай его МОЩНЕЕ оригинала.

Оригинальная тема: {original_theme}
Почему она вирусная: {why_viral}
Направление рерайта: {rewrite_angle}

Автор: {name}, город: {city}, ниша: {niche}

Создай карусель из 5 пунктов по структуре:
1. Вскрытие боли / разрыв шаблона
2. Механизм / удар по болям
3. Биологическое или иерархическое обоснование
4. Точка невозврата / скрытый враг
5. Философский / экзистенциальный удар

JSON:
{{
  "hook_title": "Виральный заголовок с КАПСОМ и скобками (8-15 слов, ДРУГОЙ от оригинала)",
  "points": [
    {{
      "title": "Короткий цепляющий заголовок (3-6 слов)",
      "body": "4-6 предложений, макс 60 слов: конкретика, детали, примеры, цитаты. Разговорный тон."
    }}
  ],
  "cta_text": "НЛП-вопрос, попадающий во внутренний диалог",
  "caption": "Хук + интрига + провокационный вопрос + 12-15 хэштегов",
  "source_inspiration": "Краткое описание оригинальной темы (для внутреннего учёта)"
}}"""


# ═══════════════════════════════════════════════════════════════════
# GENERATE FROM SCRATCH (more human-like)
# ═══════════════════════════════════════════════════════════════════

HUMAN_STYLE_SYSTEM = """
Ты — автор виральных Instagram-каруселей с миллионами охватов. Архетип "Обогревающий Воин".

Метод создания виральных текстов:
1. Контроверсивность — переворачивай общепринятые смыслы с ног на голову
2. Провокативность — смело, резко, без церемоний
3. Полярность — дели аудиторию на 2 лагеря, провоцируй споры
4. Painful — исходи из болей, показывай "общего врага"
5. Конкретика — цифры, цитаты в "", реальные истории, имена
6. Разнообразие формы — каждый абзац уникален по структуре
7. НЛП-финал — завершай вопросом, попадающим во внутренний диалог

ЗАПРЕЩЕНО:
- Канцеляризмы, общие фразы, вода, банальности
- Шаблонные заголовки ("5 советов...")
- Однотипные абзацы
- Обобщающие концовки абзацев

Формат: СТРОГО JSON.
"""


async def analyze_competitor_posts(posts_text: str) -> dict:
    """Analyze competitor posts and find viral angles."""
    logger.info("[Competitor] Analyzing competitor posts...")

    messages = [
        {"role": "system", "content": ANALYZE_SYSTEM},
        {"role": "user", "content": ANALYZE_USER.format(posts_text=posts_text)},
    ]

    client = _get_client()
    response = await asyncio.to_thread(
        lambda: client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=2500,
        )
    )

    result = _parse_json_safe(response.choices[0].message.content)
    logger.info(f"[Competitor] Found {len(result.get('viral_topics', []))} viral topics")
    return result


async def rewrite_viral_post(
    original_theme: str,
    why_viral: str,
    rewrite_angle: str,
    name: str = "Эксперт",
    city: str = "",
    niche: str = "",
) -> dict:
    """Rewrite a viral competitor post as original content."""
    logger.info(f"[Competitor] Rewriting viral post: {original_theme[:50]}...")

    messages = [
        {"role": "system", "content": REWRITE_SYSTEM},
        {"role": "user", "content": REWRITE_USER.format(
            original_theme=original_theme,
            why_viral=why_viral,
            rewrite_angle=rewrite_angle,
            name=name,
            city=city,
            niche=niche,
        )},
    ]

    client = _get_client()
    response = await asyncio.to_thread(
        lambda: client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.85,
            max_tokens=2500,
        )
    )

    result = _parse_json_safe(response.choices[0].message.content)
    result["_meta"] = {
        "source": "competitor_rewrite",
        "original_theme": original_theme,
        "rewrite_angle": rewrite_angle,
    }

    logger.info(f"[Competitor] Rewrite done: hook='{result.get('hook_title', '')[:50]}'")
    return result


async def generate_viral_ideas(
    niche: str = "",
    city: str = "",
    count: int = 5,
) -> dict:
    """Generate viral topic ideas based on current trends."""
    logger.info(f"[Competitor] Generating {count} viral ideas for {niche}...")

    messages = [
        {"role": "system", "content": ANALYZE_SYSTEM},
        {"role": "user", "content": f"""Придумай {count} САМЫХ ВИРАЛЬНЫХ тем для Instagram-каруселей
в нише "{niche}" в городе {city}.

Темы должны быть:
- Провокационными — вызывать споры в комментариях
- Полезными — давать конкретную информацию с цифрами
- Актуальными — привязанными к текущим трендам рынка

JSON:
{{
  "viral_topics": [
    {{
      "original_theme": "Тема",
      "why_viral": "Почему залетит",
      "rewrite_angle": "Как подать",
      "hook_idea": "Идея провокационного заголовка",
      "estimated_engagement": "high/medium",
      "format": "carousel"
    }}
  ],
  "niche_insights": "Что сейчас тренд в этой нише"
}}"""},
    ]

    client = _get_client()
    response = await asyncio.to_thread(
        lambda: client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.9,
            max_tokens=2000,
        )
    )

    return _parse_json_safe(response.choices[0].message.content)


# ═══════════════════════════════════════════════════════════════════
# ANALYZE VIRAL REELS — find what makes videos go viral
# ═══════════════════════════════════════════════════════════════════

ANALYZE_REELS_SYSTEM = """
Ты — аналитик виральных видео и Reels в Instagram. Ты разбираешь залетевшие видео конкурентов
и вычленяешь ФОРМУЛЫ, благодаря которым они набирают миллионы просмотров.

Ключевые факторы виральности Reels:
- Хук первых 3 секунд — что заставляет не пролистывать
- Curiosity gap — интрига, которая удерживает до конца
- Эмоциональный триггер — страх, восхищение, зависть, шок
- Storytelling — история с конфликтом и развязкой
- Тренд-формат — использование актуальных шаблонов/звуков
- CTA — что заставляет сохранить/поделиться/прокомментировать

Важно: из видео-тем нужно извлечь КЛЮЧЕВЫЕ ИДЕИ, которые можно адаптировать
в формат КАРУСЕЛЕЙ (слайдов), потому что наш основной формат — это карусели.

Ответ — СТРОГО JSON.
"""

ANALYZE_REELS_USER = """Вот топ залетевших Reels конкурента в нише недвижимости:

{reels_text}

Проанализируй и создай ТОП-5 идей для КАРУСЕЛЕЙ на основе виральных видео.
Для каждой:
- Какая тема из видео залетела и ПОЧЕМУ
- Как адаптировать эту тему в формат карусели (5 слайдов)
- Какой хук использовать на первом слайде

JSON:
{{
  "viral_reels_analysis": [
    {{
      "original_reel_theme": "О чём было видео",
      "views": 0,
      "why_viral": "Почему набрало просмотры (конкретный триггер)",
      "carousel_adaptation": "Как переделать в карусель",
      "hook_for_first_slide": "Заголовок для 1-го слайда карусели",
      "estimated_engagement": "high/medium",
      "content_angle": "Уникальный угол подачи"
    }}
  ],
  "reels_insights": "Общие паттерны: что работает в видео этого конкурента (2-3 предложения)",
  "trending_formats": ["Формат 1", "Формат 2", "Формат 3"]
}}"""


async def analyze_viral_reels(reels_text: str) -> dict:
    """Analyze viral reels and generate carousel ideas from them."""
    logger.info("[Competitor] Analyzing viral reels...")

    messages = [
        {"role": "system", "content": ANALYZE_REELS_SYSTEM},
        {"role": "user", "content": ANALYZE_REELS_USER.format(reels_text=reels_text)},
    ]

    client = _get_client()
    response = await asyncio.to_thread(
        lambda: client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=3000,
        )
    )

    result = _parse_json_safe(response.choices[0].message.content)
    logger.info(f"[Competitor] Extracted {len(result.get('viral_reels_analysis', []))} carousel ideas from reels")
    return result


async def rewrite_reel_to_carousel(
    reel_theme: str,
    why_viral: str,
    carousel_adaptation: str,
    hook: str,
    name: str = "Эксперт",
    city: str = "",
    niche: str = "",
) -> dict:
    """Take a viral reel concept and create full carousel content from it."""
    logger.info(f"[Competitor] Rewriting reel to carousel: {reel_theme[:50]}...")

    messages = [
        {"role": "system", "content": REWRITE_SYSTEM},
        {"role": "user", "content": f"""Переработай эту виральную тему из Reels конкурента В КАРУСЕЛЬ.

Тема залетевшего Reels: {reel_theme}
Почему залетело: {why_viral}
Как адаптировать в карусель: {carousel_adaptation}
Идея хука: {hook}

Автор: {name}, город: {city}, ниша: {niche}

Создай карусель из 5 пунктов по структуре:
1. Вскрытие боли / разрыв шаблона (на основе хука из рилса)
2. Механизм / удар по болям
3. Доказательство с цифрами и примерами
4. Точка невозврата / скрытый враг
5. Философский удар + call-to-action

JSON:
{{
  "hook_title": "Виральный заголовок с КАПСОМ и скобками (8-15 слов)",
  "points": [
    {{
      "title": "Короткий цепляющий заголовок (3-6 слов)",
      "body": "4-6 предложений: конкретика, цифры, примеры. Разговорный тон."
    }}
  ],
  "cta_text": "НЛП-вопрос, попадающий во внутренний диалог",
  "caption": "Хук + интрига + провокационный вопрос + 12-15 хэштегов",
  "source_inspiration": "Адаптация из Reels: {reel_theme[:80]}"
}}"""},
    ]

    client = _get_client()
    response = await asyncio.to_thread(
        lambda: client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.85,
            max_tokens=2500,
        )
    )

    result = _parse_json_safe(response.choices[0].message.content)
    result["_meta"] = {
        "source": "reel_to_carousel",
        "original_reel_theme": reel_theme,
        "adaptation": carousel_adaptation,
    }

    logger.info(f"[Competitor] Reel→Carousel done: hook='{result.get('hook_title', '')[:50]}'")
    return result


def extract_posts_from_text(raw_text: str) -> list[dict]:
    """Parse raw pasted text into individual posts.

    Supports formats:
    - Posts separated by blank lines
    - Numbered posts (1. ... 2. ...)
    - Posts with --- separators
    """
    if not raw_text.strip():
        return []

    # Try separator-based splitting first
    for sep in ['---', '===', '***']:
        if sep in raw_text:
            parts = [p.strip() for p in raw_text.split(sep) if p.strip()]
            return [{"text": p, "index": i+1} for i, p in enumerate(parts)]

    # Try double-newline splitting
    parts = re.split(r'\n\s*\n', raw_text.strip())
    if len(parts) > 1:
        return [{"text": p.strip(), "index": i+1} for i, p in enumerate(parts) if p.strip()]

    # Single post
    return [{"text": raw_text.strip(), "index": 1}]


# ═══════════════════════════════════════════════════════════════════
# ENGLISH → RUSSIAN REWRITE + LEAD MAGNET
# ═══════════════════════════════════════════════════════════════════

TRANSLATE_REWRITE_SYSTEM = """
Ты — мастер адаптации иностранного контента для русскоязычной Instagram-аудитории.

Задача: взять английский пост/карусель, полностью ПЕРЕРАБОТАТЬ (не перевести!) на русский,
сделать виральным для русскоязычной аудитории, добавить лид-магнит в конце.

ПРАВИЛА:
- НЕ буквальный перевод — АДАПТАЦИЯ. Локальные примеры, рубли, российские реалии.
- Виральные формулы: шок-заголовок, КАПС, (скобки), парадокс, curiosity gap.
- Текст как разговор с другом, на "ты", без канцеляризмов.
- Каждый слайд тянет свайпнуть дальше.
- Последний слайд: философский удар + CTA.
- Caption: кликбейт в первых 2 строках + 5-7 хэштегов.
- Для АКЦЕНТА: оберни 1-2 ключевых слова в *звёздочки*.
- БЕЗ ЭМОДЗИ.

Формат: СТРОГО JSON.
"""


async def rewrite_english_to_russian(
    original_caption: str,
    original_slides_text: str = "",
    lead_magnet: str = "",
    name: str = "Эксперт",
    niche: str = "",
    cta_text: str = "",
) -> dict:
    """
    Take an English carousel/post and rewrite it as a Russian viral carousel.
    Adds lead magnet to the CTA slide and caption.
    """
    logger.info(f"[Rewrite] EN→RU rewrite: {original_caption[:60]}...")

    lead_magnet_instruction = ""
    if lead_magnet:
        lead_magnet_instruction = f"""

LEAD MAGNET (обязательно добавить):
В cta_text вставь: "{cta_text or 'Напиши + в директ'}"
В конец caption добавь: "{lead_magnet}"
"""

    user_prompt = f"""Переработай этот английский пост в виральную русскоязычную карусель.

ОРИГИНАЛ (английский):
{original_caption}

{f'ТЕКСТ СЛАЙДОВ: {original_slides_text}' if original_slides_text else ''}

Автор: {name}, ниша: {niche}
{lead_magnet_instruction}

Выбери оптимальное количество слайдов (3-7 points).

JSON:
{{
  "hook_title": "Виральный РУССКИЙ заголовок с КАПСОМ и (скобками)",
  "slide_count": 7,
  "points": [
    {{
      "title": "Цепляющий заголовок 3-8 слов с *акцентом*",
      "body": "3-4 предложения. Адаптировано для русской аудитории."
    }}
  ],
  "cta_text": "CTA + лид-магнит",
  "caption": "Кликбейт + пункты + вопрос + лид-магнит + 5-7 хэштегов. 1400-1800 символов.",
  "source_language": "en",
  "adaptation_notes": "Что изменили при адаптации"
}}"""

    client = _get_client()
    response = await asyncio.to_thread(
        lambda: client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": TRANSLATE_REWRITE_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.85,
            max_tokens=4096,
        )
    )

    result = _parse_json_safe(response.choices[0].message.content)
    result["_meta"] = {
        "source": "english_rewrite",
        "original_caption_preview": original_caption[:100],
        "lead_magnet_added": bool(lead_magnet),
    }

    logger.info(f"[Rewrite] EN→RU done: hook='{result.get('hook_title', '')[:50]}'")
    return result


async def analyze_and_rank_posts(posts: list[dict]) -> list[dict]:
    """
    Analyze a list of scraped posts, rank by virality.
    Returns posts with analysis and viral scores.
    """
    if not posts:
        return []

    # Sort by engagement score
    ranked = sorted(posts, key=lambda p: p.get("engagement_score", 0), reverse=True)

    # Analyze top 5 with AI
    top_posts = ranked[:5]
    if not top_posts:
        return ranked

    posts_text = "\n\n".join([
        f"--- POST #{i+1} (likes: {p['likes']}, comments: {p['comments']}) ---\n{p.get('caption', '')[:500]}"
        for i, p in enumerate(top_posts)
    ])

    try:
        client = _get_client()
        response = await asyncio.to_thread(
            lambda: client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "Analyze these Instagram posts. For each one, explain in 1-2 sentences WHY it went viral. Response: JSON array of {\"index\": 1, \"why_viral\": \"...\", \"rewrite_angle\": \"...\"}"},
                    {"role": "user", "content": posts_text},
                ],
                temperature=0.5,
                max_tokens=1500,
            )
        )
        analysis = _parse_json_safe(response.choices[0].message.content)
        if isinstance(analysis, dict) and "posts" in analysis:
            analysis = analysis["posts"]
        if isinstance(analysis, list):
            for item in analysis:
                idx = item.get("index", 0) - 1
                if 0 <= idx < len(top_posts):
                    top_posts[idx]["why_viral"] = item.get("why_viral", "")
                    top_posts[idx]["rewrite_angle"] = item.get("rewrite_angle", "")
    except Exception as e:
        logger.warning(f"[Competitor] AI analysis failed: {e}")

    return ranked
