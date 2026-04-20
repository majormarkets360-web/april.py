from __future__ import annotations
import os
import json
from typing import Optional


# ── Gemini (free tier) ────────────────────────────────────────────────────────
def generate_with_gemini(
    prompt: str,
    api_key: str = "",
    max_tokens: int = 300,
) -> str:
    key = api_key or os.getenv("GEMINI_API_KEY", "")
    if not key:
        return ""
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp = model.generate_content(prompt)
        return resp.text.strip()
    except Exception as e:
        print(f"Gemini error: {e}")
        return ""


# ── Groq (free tier, very fast) ───────────────────────────────────────────────
def generate_with_groq(
    prompt: str,
    api_key: str = "",
    max_tokens: int = 300,
) -> str:
    key = api_key or os.getenv("GROQ_API_KEY", "")
    if not key:
        return ""
    try:
        from groq import Groq
        client = Groq(api_key=key)
        resp = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"Groq error: {e}")
        return ""


# ── Main caption generator (tries Gemini first, falls back to Groq) ───────────
def generate_caption(
    clip_number: int,
    source_title: str,
    platform: str,
    gemini_key: str = "",
    groq_key: str = "",
) -> str:

    platform_rules = {
        "Twitter/X":   "Max 220 chars. Punchy, 2-3 hashtags, hook in first 5 words.",
        "Instagram":   "Storytelling tone, 150-300 chars, 8-15 hashtags at end, emojis.",
        "TikTok":      "Casual, hook in first line, trending hashtags, under 150 chars.",
        "LinkedIn":    "Professional, insightful, 150-200 chars, 3-5 hashtags.",
        "Facebook":    "Conversational, shareable, 100-200 chars, 2-4 hashtags.",
        "YouTube":     "Descriptive, searchable keywords, 100-150 chars, 5-8 hashtags.",
        "Pinterest":   "Descriptive, inspiring, include keywords, 2-3 hashtags.",
        "Reddit":      "Conversational title-style, no hashtags, community-friendly.",
    }

    rules = platform_rules.get(platform, "Engaging and shareable, add hashtags.")

    prompt = (
        f"Write a viral social media caption for clip #{clip_number} "
        f"from the show/video: '{source_title}'.\n"
        f"Platform: {platform}\n"
        f"Rules: {rules}\n"
        f"Make it attention-grabbing with relevant emojis.\n"
        f"Return ONLY the caption, no explanation, no quotes."
    )

    # Try Gemini first
    result = generate_with_gemini(prompt, gemini_key)
    if result:
        return result

    # Fall back to Groq
    result = generate_with_groq(prompt, groq_key)
    if result:
        return result

    # Final fallback
    return _fallback_caption(clip_number, source_title, platform)


def generate_content_strategy(
    source_title: str,
    num_clips: int,
    platforms: list[str],
    gemini_key: str = "",
    groq_key: str = "",
) -> str:
    prompt = (
        f"Create a short posting strategy for {num_clips} viral clips "
        f"from '{source_title}' across {', '.join(platforms)}.\n"
        f"Include: best times to post, caption style per platform, hashtag strategy.\n"
        f"Format as clean bullet points. Keep it practical and concise."
    )
    result = generate_with_gemini(prompt, gemini_key, max_tokens=500)
    if not result:
        result = generate_with_groq(prompt, groq_key, max_tokens=500)
    return result or "Add a Gemini or Groq API key to generate strategy."


def _fallback_caption(clip_number: int, source_title: str, platform: str) -> str:
    hooks = [
        "This moment is everything 🔥",
        "You need to see this 👀",
        "Can't stop rewatching this 😮",
        "The best scene of the whole show ✨",
        "This hit different 💯",
        "Nobody talks about this moment 🤯",
        "The scene everyone is talking about 🎬",
    ]
    hook = hooks[clip_number % len(hooks)]
    tags = {
        "TikTok":    "#fyp #foryou #viral #trending #mustwatch",
        "Instagram": "#reels #viral #trending #mustwatch #tvclips #entertainment",
        "Twitter/X": "#viral #mustwatch #trending",
        "YouTube":   "#shorts #viral #trending #mustwatch",
        "LinkedIn":  "#entertainment #content #trending",
        "Facebook":  "#viral #mustwatch #trending",
        "Pinterest": "#viral #tvshow #mustwatch",
        "Reddit":    "",
    }
    hashtags = tags.get(platform, "#viral #trending #mustwatch")
    return f"{hook}\n\nClip #{clip_number} — {source_title} 🎬\n\n{hashtags}"
