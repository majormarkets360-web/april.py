from __future__ import annotations
import io
import os
import requests
from typing import Optional


def post_to_twitter(
    text: str,
    video_path: Optional[str] = None,
    api_key: str = "",
    api_secret: str = "",
    access_token: str = "",
    access_secret: str = "",
) -> dict:
    try:
        import tweepy

        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
        api_v1 = tweepy.API(auth)
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_secret,
        )

        media_ids = []
        if video_path and os.path.exists(video_path):
            media = api_v1.media_upload(
                filename=video_path,
                chunked=True,
                media_category="tweet_video",
            )
            # Wait for processing
            import time
            for _ in range(20):
                info = api_v1.get_media_upload_status(media.media_id)
                state = info.processing_info.get("state", "")
                if state == "succeeded":
                    break
                elif state == "failed":
                    return {"success": False, "error": "Twitter video processing failed"}
                time.sleep(3)
            media_ids.append(media.media_id)

        tweet = client.create_tweet(
            text=text[:280],
            media_ids=media_ids if media_ids else None,
        )
        tweet_id = tweet.data["id"]
        return {
            "success": True,
            "url": f"https://twitter.com/i/web/status/{tweet_id}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def post_to_instagram_basic(
    caption: str,
    video_path: Optional[str] = None,
    access_token: str = "",
    ig_user_id: str = "",
) -> dict:
    """
    Instagram Graph API — requires public video URL.
    For local files, this returns instructions since IG requires a CDN URL.
    """
    if not access_token or not ig_user_id:
        return {"success": False, "error": "Missing Instagram credentials"}

    return {
        "success": False,
        "error": (
            "Instagram requires a public video URL (CDN-hosted). "
            "Upload your clip to a public host first, then post via Graph API."
        ),
        "caption_ready": caption,
    }


def post_to_tiktok_manual(caption: str, video_path: str) -> dict:
    """TikTok requires verified developer account for API posting."""
    return {
        "success": False,
        "error": "TikTok API requires a verified developer account. Use manual upload.",
        "caption_ready": caption,
        "video_path": video_path,
    }


def generate_caption_with_claude(
    clip_number: int,
    source_title: str,
    platform: str,
    api_key: str = "",
) -> str:
    """Generate a short viral caption for a clip using Claude."""
    key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        return _fallback_caption(clip_number, source_title, platform)

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=key)

        platform_rules = {
            "Twitter/X": "max 220 chars, 2-3 hashtags, punchy",
            "Instagram": "engaging, storytelling, 5-10 hashtags",
            "TikTok": "hook in first line, trending hashtags, casual tone",
            "LinkedIn": "professional, insightful, 3-5 hashtags",
            "Facebook": "conversational, shareable, broad appeal",
        }
        rules = platform_rules.get(platform, "engaging and shareable")

        resp = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (
                    f"Write a short viral social media caption for clip #{clip_number} "
                    f"from '{source_title}'. Platform: {platform}. Rules: {rules}. "
                    "Make it engaging, add relevant emojis and hashtags. "
                    "Return ONLY the caption text, nothing else."
                ),
            }],
        )
        return resp.content[0].text.strip()
    except Exception:
        return _fallback_caption(clip_number, source_title, platform)


def _fallback_caption(clip_number: int, source_title: str, platform: str) -> str:
    hooks = [
        "You won't believe this moment 👀",
        "This scene is everything 🔥",
        "Can't stop watching this 😮",
        "The best part of the whole show ✨",
        "This moment hit different 💯",
    ]
    hook = hooks[clip_number % len(hooks)]
    return (
        f"{hook}\n\n"
        f"Clip #{clip_number} from {source_title} 🎬\n\n"
        "#Viral #MustWatch #TVClips #Trending #FYP"
    )
