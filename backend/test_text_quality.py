"""Test text quality with updated prompts."""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from app.services.generator.content import generate_topic_content


async def main():
    print("=" * 60)
    print("TESTING TEXT QUALITY WITH UPDATED PROMPTS")
    print("=" * 60)

    result = await generate_topic_content(
        name="Алексей",
        city="Москва",
        niche="недвижимость",
        topic_hint="",
    )

    # Extract meta
    meta = result.pop("_meta", {})

    print(f"\n📊 Generation rounds: {meta.get('generation_rounds', '?')}")
    print(f"📊 Final score: {meta.get('final_score', '?')}/10")

    if meta.get("rounds"):
        for r in meta["rounds"]:
            print(f"  Round {r['round']}: score={r['avg_score']}, verdict={r['verdict']}")
            if r.get("weak_points"):
                for wp in r["weak_points"]:
                    print(f"    ⚠ {wp}")

    print(f"\n🎯 ЗАГОЛОВОК: {result.get('hook_title', 'N/A')}")
    print()

    for i, p in enumerate(result.get("points", []), 1):
        print(f"--- Пункт {i}: {p.get('title', '')} ---")
        print(p.get("body", ""))
        print()

    print(f"💬 CTA: {result.get('cta_text', 'N/A')}")
    print(f"\n📝 Caption: {result.get('caption', 'N/A')[:200]}...")

    # Check for forbidden phrases
    forbidden = [
        "важно понимать", "стоит отметить", "обратите внимание",
        "в современном мире", "на самом деле", "как показывает практика",
        "ключевой момент", "необходимо учитывать", "следует помнить",
        "безусловно", "несомненно", "в целом", "подводя итог",
    ]

    all_text = json.dumps(result, ensure_ascii=False).lower()
    found_forbidden = [f for f in forbidden if f in all_text]

    print("\n" + "=" * 60)
    if found_forbidden:
        print(f"❌ FOUND {len(found_forbidden)} FORBIDDEN PHRASES:")
        for f in found_forbidden:
            print(f"  - '{f}'")
    else:
        print("✅ NO FORBIDDEN PHRASES DETECTED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
