"""
Brand personality unpacker service.
Accepts uploaded files (MD, TXT, PDF, DOCX), extracts text,
sends to Claude for analysis, returns structured brand profile.

Uses the secondary CometAPI key (openai_api_key_v2) for heavy analysis tasks.
"""
import io
import json
import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

from openai import OpenAI

from app.config import get_settings
from app.utils.prompts_universal import BRAND_UNPACK_SYSTEM, BRAND_UNPACK_USER

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_unpack_client() -> OpenAI:
    """Get OpenAI client with the secondary API key for brand unpacking."""
    api_key = settings.openai_api_key_v2 or settings.openai_api_key
    return OpenAI(
        api_key=api_key,
        base_url=settings.openai_base_url,
    )


def extract_text_from_file(filename: str, content: bytes) -> str:
    """Extract plain text from uploaded file based on extension."""
    ext = Path(filename).suffix.lower()

    if ext in (".txt", ".md"):
        return content.decode("utf-8", errors="replace")

    elif ext == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                pages = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
                return "\n\n".join(pages)
        except ImportError:
            logger.warning("pdfplumber not installed, trying PyPDF2")
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(io.BytesIO(content))
                pages = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
                return "\n\n".join(pages)
            except ImportError:
                raise ValueError("PDF parsing requires pdfplumber or PyPDF2. Install: pip install pdfplumber")

    elif ext in (".docx", ".doc"):
        try:
            from docx import Document
            doc = Document(io.BytesIO(content))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(paragraphs)
        except ImportError:
            raise ValueError("DOCX parsing requires python-docx. Install: pip install python-docx")

    else:
        raise ValueError(f"Unsupported file format: {ext}. Supported: .md, .txt, .pdf, .docx")


def _parse_json_safe(text: str) -> dict:
    """Parse JSON with robust fallback (same pattern as content.py)."""
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

    raise ValueError(f"Could not parse JSON from LLM response: {text[:300]}")


def _call_unpack_llm_sync(messages: list[dict]) -> str:
    """Synchronous LLM call for brand unpacking. Uses thinking mode for deep analysis."""
    client = _get_unpack_client()
    model = settings.openai_eval_model  # Opus for deep brand analysis
    logger.info(f"[Brand Unpack] Calling {model} with thinking mode via {settings.openai_base_url}")

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=8192,
        temperature=1.0,
        extra_body={
            "thinking": {"type": "enabled", "budget_tokens": 4096}
        },
    )
    return response.choices[0].message.content


async def unpack_brand_profile(
    raw_text: str,
    on_progress: Optional[callable] = None,
) -> dict:
    """
    Analyze expert's materials and extract structured brand profile.

    Args:
        raw_text: Combined text from all uploaded files
        on_progress: Optional callback(step_name, current, total)

    Returns:
        dict with keys: positioning, target_audience, services,
        content_topics, tone_of_voice, unique_phrases, niche
    """
    if not raw_text or len(raw_text.strip()) < 50:
        raise ValueError(
            "Not enough text to analyze. Please upload more detailed materials "
            "about your expertise, services, and target audience."
        )

    # Truncate to ~80K chars if too long (Claude handles well but let's be safe)
    if len(raw_text) > 80000:
        raw_text = raw_text[:80000]
        logger.warning(f"[Brand Unpack] Truncated input to 80K chars")

    if on_progress:
        on_progress("analyzing", 1, 3)

    logger.info(f"[Brand Unpack] Analyzing {len(raw_text)} chars of expert materials...")

    messages = [
        {"role": "system", "content": BRAND_UNPACK_SYSTEM},
        {"role": "user", "content": BRAND_UNPACK_USER.format(raw_text=raw_text)},
    ]

    content = await asyncio.to_thread(_call_unpack_llm_sync, messages)
    result = _parse_json_safe(content)

    if on_progress:
        on_progress("finalizing", 2, 3)

    # Validate required fields
    required_fields = ["positioning", "target_audience", "services",
                       "content_topics", "tone_of_voice", "niche"]
    for field in required_fields:
        if field not in result:
            logger.warning(f"[Brand Unpack] Missing field '{field}' in LLM response, using default")
            if field in ("target_audience", "services", "content_topics"):
                result[field] = []
            elif field == "tone_of_voice":
                result[field] = {}
            else:
                result[field] = ""

    if on_progress:
        on_progress("done", 3, 3)

    logger.info(
        f"[Brand Unpack] Done: niche='{result.get('niche', '')}', "
        f"personas={len(result.get('target_audience', []))}, "
        f"topics={len(result.get('content_topics', []))}"
    )

    return result
