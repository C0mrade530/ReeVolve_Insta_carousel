"""
AI content generation service — Optimized 3-Step Pipeline for expert carousels.

Pipeline (3 LLM calls minimum, 5 max):
  Step 1 (ТЕМА-СТРАТЕГ) → Sonnet standard — тема + план слайдов (1 call instead of 2)
  Step 2 (СЛАЙД-РАЙТЕР) → Sonnet standard — слайды + caption
  Step 3 (ВИРАЛ-АНАЛИТИК) → Sonnet thinking — оценка виральности
  [если score < 7.5 → рефайн + повторная оценка, до 2 раз]

Cost: ~5-8 центов за карусель (vs 10-15 с 4 агентами)
Progress: reports current step via callback for SSE/UI updates.

Uses CometAPI (OpenAI-compatible proxy) with Claude models.
Supports both legacy (realtor-specific) and universal (multi-niche) prompts.
When brand_profile is provided, universal parametric prompts are used.
"""
import re
import json
import asyncio
import logging
from typing import Callable, Optional
from openai import OpenAI

from app.config import get_settings
# Legacy realtor-specific prompts (backward compatibility)
from app.utils.prompts import (
    TOPIC_STRATEGIST_SYSTEM,
    TOPIC_STRATEGIST_USER,
    SLIDES_WRITER_SYSTEM,
    SLIDES_WRITER_USER,
    VIRAL_ANALYST_SYSTEM,
    VIRAL_ANALYST_USER,
    REFINE_SYSTEM_PROMPT,
    REFINE_USER_PROMPT,
    PROPERTY_SYSTEM_PROMPT,
    PROPERTY_USER_PROMPT,
    EVALUATE_SYSTEM_PROMPT,
    EVALUATE_USER_PROMPT,
)
# Universal multi-niche prompts (used when brand_profile is available)
from app.utils.prompts_universal import (
    build_topic_strategist_system,
    build_topic_strategist_user,
    build_slides_writer_system,
    build_slides_writer_user,
    build_viral_analyst_system,
    build_viral_analyst_user,
    build_refine_system,
    REFINE_USER_UNIVERSAL,
)

logger = logging.getLogger(__name__)
settings = get_settings()

QUALITY_THRESHOLD = 7.5
MAX_REFINE_ROUNDS = 2

_MODELS_WITH_JSON_MODE = {"gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-5", "gpt-5.2"}

# Progress callback type
ProgressCallback = Optional[Callable[[str, int, int], None]]


def get_openai_client() -> OpenAI:
    return OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )


def _is_json_mode_supported() -> bool:
    model = settings.openai_model.lower()
    return any(m in model for m in _MODELS_WITH_JSON_MODE)


def _call_llm_sync(messages: list[dict], temperature: float = 0.9,
                    use_eval_model: bool = False) -> str:
    """
    Synchronous LLM call.
    use_eval_model=True → Sonnet thinking (Step 3: viral analysis)
    use_eval_model=False → Sonnet standard (Step 1, Step 2)
    """
    client = get_openai_client()
    model = settings.openai_eval_model if use_eval_model else settings.openai_model
    mode = "thinking" if use_eval_model else "standard"
    logger.info(f"[LLM] Calling {model} ({mode}) via {settings.openai_base_url}")

    kwargs = dict(
        model=model,
        messages=messages,
        max_tokens=8192 if use_eval_model else 4096,
    )

    if use_eval_model:
        kwargs["temperature"] = 1.0
        kwargs["extra_body"] = {
            "thinking": {"type": "enabled", "budget_tokens": 2048}
        }
    else:
        kwargs["temperature"] = temperature

    if _is_json_mode_supported():
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def _parse_json_safe(text: str) -> dict:
    """Parse JSON with robust fallback."""
    if not text:
        raise ValueError("Empty response from LLM")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON: {text[:300]}")


# ═══════════════════════════════════════════════════════════════════
# 3-STEP PIPELINE
# ═══════════════════════════════════════════════════════════════════

async def _step1_topic(name: str, city: str, niche: str, topic_hint: str,
                       on_progress: ProgressCallback = None,
                       used_topics: list[str] | None = None,
                       brand_profile: dict | None = None) -> dict:
    """Step 1: Generate topic + slide plan (merged Agent 1+2, 1 LLM call).
    When brand_profile is provided, uses universal parametric prompts.
    Otherwise falls back to legacy realtor-specific prompts.
    """
    if on_progress:
        on_progress("topic", 1, 5)
    logger.info("[Step 1] Generating topic strategy...")

    # Build diversity instructions for batch generation
    if topic_hint:
        hint_text = f"Тема: {topic_hint}"
    elif used_topics:
        exclusion_list = "\n".join(f"  - {t}" for t in used_topics)
        if brand_profile:
            # Universal: rotate through brand_profile categories
            categories = brand_profile.get("content_topics", [])
            if categories:
                batch_idx = len(used_topics) % len(categories)
                target_cat = categories[batch_idx].get("category", "")
                hint_text = (
                    f"ОБЯЗАТЕЛЬНО выбери тему из категории '{target_cat}'.\n\n"
                    "Следующие темы УЖЕ ИСПОЛЬЗОВАНЫ в этом батче. "
                    "Придумай ПРИНЦИПИАЛЬНО ДРУГУЮ тему:\n"
                    f"{exclusion_list}\n\n"
                    "НЕ повторяй сюжет, угол подачи или эмоциональный триггер."
                )
            else:
                hint_text = (
                    "Придумай тему сам. "
                    "Следующие темы УЖЕ ИСПОЛЬЗОВАНЫ:\n"
                    f"{exclusion_list}\n\n"
                    "НЕ повторяй сюжет."
                )
        else:
            # Legacy: rotate categories B, C, D
            _CATEGORY_ROTATION = ["B", "C", "D", "B", "D", "C", "A"]
            batch_idx = len(used_topics) % len(_CATEGORY_ROTATION)
            target_cat = _CATEGORY_ROTATION[batch_idx]
            hint_text = (
                f"ОБЯЗАТЕЛЬНО выбери тему из КАТЕГОРИИ {target_cat}. "
                f"НЕ выбирай категорию A (сделки/деньги), если не указана категория A.\n\n"
                "Следующие темы УЖЕ ИСПОЛЬЗОВАНЫ в этом батче. "
                "Придумай ПРИНЦИПИАЛЬНО ДРУГУЮ тему с ДРУГОЙ категорией, "
                "ДРУГОЙ виральной формулой и ДРУГОЙ историей:\n"
                f"{exclusion_list}\n\n"
                "НЕ повторяй сюжет, угол подачи или эмоциональный триггер."
            )
    else:
        if brand_profile:
            hint_text = "Придумай виральную тему сам, используя одну из категорий контента эксперта."
        else:
            hint_text = (
                "Придумай тему сам. Выбери категорию B (соседи, быт), "
                "C (психология, философия дома) или D (мир, СССР, факты). "
                "НЕ выбирай категорию A (сделки/деньги) по умолчанию!"
            )

    # Choose prompts: universal (brand_profile) or legacy (realtor)
    if brand_profile:
        system_prompt = build_topic_strategist_system(brand_profile)
        user_prompt = build_topic_strategist_user(
            name=name, niche=niche, topic_hint=hint_text
        )
    else:
        system_prompt = TOPIC_STRATEGIST_SYSTEM
        user_prompt = TOPIC_STRATEGIST_USER.format(
            name=name,
            city=city,
            niche=niche,
            topic_hint=hint_text,
            top_posts_context="",
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    content = await asyncio.to_thread(_call_llm_sync, messages, 0.9)
    result = _parse_json_safe(content)
    logger.info(f"[Step 1] Topic: '{result.get('hook_title', '')[:60]}'")
    logger.info(f"[Step 1] Pain: {result.get('pain_trigger', '?')}, Emotion: {result.get('target_emotion', '?')}")
    return result


async def _step2_slides(topic: dict, name: str, city: str, niche: str,
                        on_progress: ProgressCallback = None,
                        brand_profile: dict | None = None) -> dict:
    """Step 2: Write 5 slides + caption (1 LLM call)."""
    if on_progress:
        on_progress("slides", 2, 5)
    logger.info("[Step 2] Writing slides + caption...")

    hook_title = topic.get("hook_title", "")
    topic_json = json.dumps(topic, ensure_ascii=False, indent=2)

    if brand_profile:
        system_prompt = build_slides_writer_system(brand_profile)
        user_prompt = build_slides_writer_user(
            name=name, niche=niche,
            approved_topic_json=topic_json, hook_title=hook_title,
        )
    else:
        system_prompt = SLIDES_WRITER_SYSTEM
        user_prompt = SLIDES_WRITER_USER.format(
            name=name, city=city, niche=niche,
            approved_topic_json=topic_json, hook_title=hook_title,
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    content = await asyncio.to_thread(_call_llm_sync, messages, 0.9)
    result = _parse_json_safe(content)
    logger.info(f"[Step 2] Slides: {len(result.get('points', []))}, Caption: {len(result.get('caption', ''))} chars")
    return result


async def _step3_evaluate(carousel: dict,
                          on_progress: ProgressCallback = None,
                          brand_profile: dict | None = None) -> dict:
    """Step 3: Evaluate virality (thinking mode, 1 LLM call)."""
    if on_progress:
        on_progress("evaluate", 3, 5)
    logger.info("[Step 3] Evaluating virality...")

    carousel_json = json.dumps(carousel, ensure_ascii=False, indent=2)

    if brand_profile:
        system_prompt = build_viral_analyst_system(brand_profile)
        user_prompt = build_viral_analyst_user(carousel_json)
    else:
        system_prompt = VIRAL_ANALYST_SYSTEM
        user_prompt = VIRAL_ANALYST_USER.format(carousel_json=carousel_json)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    content = await asyncio.to_thread(_call_llm_sync, messages, 0.3, True)
    result = _parse_json_safe(content)
    logger.info(f"[Step 3] Viral score: {result.get('avg_score', 0)}/10, verdict: {result.get('verdict', '?')}")
    return result


async def _refine_carousel(original: dict, evaluation: dict,
                           on_progress: ProgressCallback = None,
                           brand_profile: dict | None = None) -> dict:
    """Refine based on feedback (1 LLM call)."""
    if on_progress:
        on_progress("refine", 3, 5)
    logger.info("[Refine] Improving slides + caption...")

    if brand_profile:
        system_prompt = build_refine_system(brand_profile)
        user_prompt = REFINE_USER_UNIVERSAL.format(
            original_json=json.dumps(original, ensure_ascii=False, indent=2),
            evaluation_json=json.dumps(evaluation, ensure_ascii=False, indent=2),
        )
    else:
        system_prompt = REFINE_SYSTEM_PROMPT
        user_prompt = REFINE_USER_PROMPT.format(
            original_json=json.dumps(original, ensure_ascii=False, indent=2),
            evaluation_json=json.dumps(evaluation, ensure_ascii=False, indent=2),
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    content = await asyncio.to_thread(_call_llm_sync, messages, 0.8)
    result = _parse_json_safe(content)
    logger.info(f"[Refine] Updated: hook='{result.get('hook_title', '')[:50]}'")
    return result


async def generate_topic_content(
    name: str,
    city: str,
    niche: str,
    topic_hint: str = "",
    on_progress: ProgressCallback = None,
    used_topics: list[str] | None = None,
    brand_profile: dict | None = None,
) -> dict:
    """
    Optimized 3-Step Pipeline:
    1. ТЕМА-СТРАТЕГ — тема + план слайдов (1 call, saves Agent 2)
    2. СЛАЙД-РАЙТЕР — все слайды + caption (1 call)
    3. ВИРАЛ-АНАЛИТИК — оценка (1 call, thinking)
    4. [если score < 7.5] → рефайн + повторная оценка (2 calls)

    Total: 3-5 LLM calls. Cost: ~5-8 центов.

    on_progress: optional callback(step_name, current_step, total_steps)
    brand_profile: optional dict from brand_profiles table — enables universal prompts
    """
    rounds_log = []
    mode = "universal" if brand_profile else "legacy"
    logger.info(f"[Pipeline] Mode: {mode}, niche: {niche}")

    # ───── Step 1: Topic strategy (merged Agent 1+2) ─────
    topic = await _step1_topic(
        name, city, niche, topic_hint, on_progress,
        used_topics=used_topics, brand_profile=brand_profile
    )
    rounds_log.append({"step": "topic_strategy", "result": "ok"})

    # ───── Step 2: Write slides + caption ─────
    carousel = await _step2_slides(
        topic, name, city, niche, on_progress,
        brand_profile=brand_profile
    )
    rounds_log.append({"step": "slides_writer", "result": "ok"})

    # ───── Step 3: Viral evaluation + refine loop ─────
    best = carousel
    best_score = 0

    for round_num in range(1, MAX_REFINE_ROUNDS + 2):
        evaluation = await _step3_evaluate(best, on_progress, brand_profile=brand_profile)
        avg_score = evaluation.get("avg_score", 0)
        verdict = evaluation.get("verdict", "refine")

        rounds_log.append({
            "step": "viral_analyst",
            "round": round_num,
            "avg_score": avg_score,
            "verdict": verdict,
            "scores": evaluation.get("scores", {}),
            "weak_points": evaluation.get("weak_points", []),
        })

        if avg_score > best_score:
            best_score = avg_score

        if verdict == "publish" or avg_score >= QUALITY_THRESHOLD or round_num > MAX_REFINE_ROUNDS:
            logger.info(f"[Pipeline] Final: {avg_score}/10 after {round_num} round(s)")
            break

        logger.info(f"[Pipeline] Score {avg_score} < {QUALITY_THRESHOLD}, refining...")
        best = await _refine_carousel(best, evaluation, on_progress, brand_profile=brand_profile)
        rounds_log.append({"step": "refine", "round": round_num})

    # Text generation done — pipeline.py will send slides_render + done

    best["_meta"] = {
        "pipeline": "3-step-v2",
        "mode": mode,
        "total_llm_calls": sum(1 for r in rounds_log if r["step"] in ("topic_strategy", "slides_writer", "viral_analyst", "refine")),
        "final_viral_score": best_score,
        "approved_topic": topic.get("hook_title", ""),
        "pain_trigger": topic.get("pain_trigger", ""),
        "rounds": rounds_log,
        "generation_rounds": len([r for r in rounds_log if r["step"] == "viral_analyst"]),
        "final_score": best_score,
    }

    return best


# ═══════════════════════════════════════════════════════════════════
# PROPERTY CAROUSEL (legacy)
# ═══════════════════════════════════════════════════════════════════

async def _generate_draft(messages: list[dict]) -> dict:
    content = await asyncio.to_thread(_call_llm_sync, messages, 0.9)
    return _parse_json_safe(content)


async def _evaluate(carousel_json: str) -> dict:
    messages = [
        {"role": "system", "content": EVALUATE_SYSTEM_PROMPT},
        {"role": "user", "content": EVALUATE_USER_PROMPT.format(carousel_json=carousel_json)},
    ]
    content = await asyncio.to_thread(_call_llm_sync, messages, 0.3, True)
    return _parse_json_safe(content)


async def generate_property_content(
    listing: dict,
    on_progress: ProgressCallback = None,
) -> dict:
    """
    Generate 6-slide property carousel content.
    Steps: draft (1 LLM call) → evaluate (1 LLM call) → optional refine.
    """
    from app.utils.prompts import PROPERTY_SLIDES_SYSTEM, PROPERTY_SLIDES_USER

    special_conditions = listing.get("special_conditions") or {}
    if isinstance(special_conditions, dict):
        conditions_text = ", ".join(f"{k}: {v}" for k, v in special_conditions.items() if v)
    else:
        conditions_text = str(special_conditions)

    price = listing.get("price", 0)

    # Step 1: Generate 6-slide content
    if on_progress:
        on_progress("generate_text", 2, 5)
    logger.info("[Property] Generating 6-slide content...")

    user_prompt = PROPERTY_SLIDES_USER.format(
        complex_name=listing.get("complex_name") or "Не указано",
        area_total=listing.get("area_total") or "?",
        rooms=listing.get("rooms") or "?",
        price=price,
        special_conditions=conditions_text or "Нет спецусловий",
        district=listing.get("district") or "",
        metro_station=listing.get("metro_station") or "не указано",
        description=listing.get("description") or "Нет описания",
    )

    draft = await _generate_draft([
        {"role": "system", "content": PROPERTY_SLIDES_SYSTEM},
        {"role": "user", "content": user_prompt},
    ])

    # Step 2: Evaluate quality
    if on_progress:
        on_progress("evaluate", 3, 5)
    logger.info("[Property] Evaluating carousel quality...")

    evaluation = await _evaluate(json.dumps(draft, ensure_ascii=False, indent=2))
    avg_score = evaluation.get("avg_score", 0)

    # Step 3: Refine if needed
    best = draft
    rounds = 1
    if avg_score < QUALITY_THRESHOLD:
        if on_progress:
            on_progress("refine", 3, 5)
        logger.info(f"[Property] Score {avg_score} < {QUALITY_THRESHOLD}, refining...")

        messages = [
            {"role": "system", "content": REFINE_SYSTEM_PROMPT},
            {"role": "user", "content": REFINE_USER_PROMPT.format(
                original_json=json.dumps(draft, ensure_ascii=False, indent=2),
                evaluation_json=json.dumps(evaluation, ensure_ascii=False, indent=2),
            )},
        ]
        content = await asyncio.to_thread(_call_llm_sync, messages, 0.8)
        best = _parse_json_safe(content)
        rounds = 2

    best["_meta"] = {
        "pipeline": "property-6slide",
        "pipeline_version": "2.0",
        "generation_rounds": rounds,
        "final_score": avg_score,
        "total_llm_calls": rounds + 1,
    }

    logger.info(f"[Property] Done: score={avg_score}, rounds={rounds}")
    return best
