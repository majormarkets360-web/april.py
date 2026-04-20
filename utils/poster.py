from __future__ import annotations
import io
import os
import time
import requests
from typing import Optional


# ── Twitter / X ───────────────────────────────────────────────────────────────
def post_twitter(
    caption: str, video_path: str,
    api_key: str, api_secret: str,
    access_token: str, access_secret: str,
) -> dict:
    if not all([api_key, api_secret, access_token, access_secret]):
        return {"success": False, "error": "Missing Twitter credentials"}
    try:
        import tweepy
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
        v1   = tweepy.API(auth)
        client = tweepy.Client(
            consumer_key=api_key, consumer_secret=api_secret,
            access_token=access_token, access_token_secret=access_secret,
        )
        media_ids = []
        if video_path and os.path.exists(video_path):
            media = v1.media_upload(
                filename=video_path, chunked=True,
                media_category="tweet_video",
            )
            for _ in range(30):
                info  = v1.get_media_upload_status(media.media_id)
                state = info.processing_info.get("state", "")
                if state == "succeeded":
                    break
                if state == "failed":
                    return {"success": False, "error": "Twitter video processing failed"}
                time.sleep(3)
            media_ids.append(media.media_id)

        tweet = client.create_tweet(
            text=caption[:280],
            media_ids=media_ids or None,
        )
        tid = tweet.data["id"]
        return {"success": True, "url": f"https://twitter.com/i/web/status/{tid}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── YouTube Shorts ────────────────────────────────────────────────────────────
def post_youtube(
    caption: str, video_path: str,
    client_secrets_json: str = "",
) -> dict:
    """
    Requires OAuth2. client_secrets_json = path to downloaded JSON from
    console.cloud.google.com → APIs → YouTube Data API v3.
    """
    if not client_secrets_json or not os.path.exists(client_secrets_json):
        return {
            "success": False,
            "error": (
                "YouTube needs a client_secrets.json from Google Cloud Console. "
                "Enable YouTube Data API v3, download OAuth credentials, "
                "upload the JSON file and provide its path."
            ),
        }
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(
            client_secrets_json,
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )
        creds   = flow.run_local_server(port=0)
        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": caption[:100],
                "description": caption,
                "tags": ["shorts", "viral", "trending"],
                "categoryId": "24",
            },
            "status": {"privacyStatus": "public"},
        }
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        req   = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        resp  = req.execute()
        vid_id = resp.get("id", "")
        return {"success": True, "url": f"https://youtube.com/shorts/{vid_id}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Facebook ──────────────────────────────────────────────────────────────────
def post_facebook(
    caption: str, video_path: str,
    page_token: str, page_id: str,
) -> dict:
    if not page_token or not page_id:
        return {"success": False, "error": "Missing Facebook credentials"}
    try:
        with open(video_path, "rb") as f:
            resp = requests.post(
                f"https://graph.facebook.com/{page_id}/videos",
                data={"description": caption, "access_token": page_token},
                files={"source": f},
                timeout=120,
            )
        resp.raise_for_status()
        vid_id = resp.json().get("id", "")
        return {"success": True, "url": f"https://facebook.com/{vid_id}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── LinkedIn ──────────────────────────────────────────────────────────────────
def post_linkedin(
    caption: str, video_path: str,
    access_token: str, person_urn: str,
) -> dict:
    if not access_token or not person_urn:
        return {"success": False, "error": "Missing LinkedIn credentials"}
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        body = {
            "author": person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": caption[:3000]},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }
        resp = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=headers, json=body, timeout=30,
        )
        resp.raise_for_status()
        post_id = resp.headers.get("x-restli-id", "")
        return {"success": True, "url": f"https://linkedin.com/feed/update/{post_id}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Instagram ─────────────────────────────────────────────────────────────────
def post_instagram(
    caption: str, video_path: str,
    access_token: str, ig_user_id: str,
) -> dict:
    return {
        "success": False,
        "error": (
            "Instagram requires a public video URL hosted on a CDN. "
            "For now, download the clip and upload it manually via the Instagram app."
        ),
        "caption_ready": caption,
    }


# ── TikTok ────────────────────────────────────────────────────────────────────
def post_tiktok(caption: str, video_path: str) -> dict:
    return {
        "success": False,
        "error": "TikTok API requires verified developer access. Upload manually.",
        "caption_ready": caption,
    }


# ── Reddit ────────────────────────────────────────────────────────────────────
def post_reddit(
    title: str, video_path: str,
    client_id: str, client_secret: str,
    username: str, password: str,
    subreddit: str = "videos",
) -> dict:
    if not all([client_id, client_secret, username, password]):
        return {"success": False, "error": "Missing Reddit credentials"}
    try:
        import praw
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            user_agent="ClipMasterPro/1.0",
        )
        sub  = reddit.subreddit(subreddit)
        post = sub.submit_video(title=title[:300], video_path=video_path)
        return {"success": True, "url": f"https://reddit.com{post.permalink}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Dispatcher ────────────────────────────────────────────────────────────────
def post_to_platform(
    platform: str,
    caption: str,
    video_path: str,
    creds: dict,
) -> dict:
    p = platform
    c = creds

    if p == "Twitter/X":
        return post_twitter(
            caption, video_path,
            c.get("tw_key",""), c.get("tw_secret",""),
            c.get("tw_token",""), c.get("tw_tsecret",""),
        )
    elif p == "Facebook":
        return post_facebook(
            caption, video_path,
            c.get("fb_token",""), c.get("fb_page_id",""),
        )
    elif p == "LinkedIn":
        return post_linkedin(
            caption, video_path,
            c.get("li_token",""), c.get("li_urn",""),
        )
    elif p == "YouTube Shorts":
        return post_youtube(
            caption, video_path,
            c.get("yt_secrets",""),
        )
    elif p == "Instagram":
        return post_instagram(
            caption, video_path,
            c.get("ig_token",""), c.get("ig_user_id",""),
        )
    elif p == "TikTok":
        return post_tiktok(caption, video_path)
    elif p == "Reddit":
        return post_reddit(
            caption[:300], video_path,
            c.get("reddit_client_id",""), c.get("reddit_client_secret",""),
            c.get("reddit_username",""), c.get("reddit_password",""),
            c.get("reddit_subreddit","videos"),
        )
    return {"success": False, "error": f"Unknown platform: {p}"}
