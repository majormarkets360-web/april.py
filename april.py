from __future__ import annotations
import os
import time
import threading
from datetime import datetime
import streamlit as st

st.set_page_config(
    page_title="ClipMaster Pro",
    page_icon="🎬",
    layout="wide",
)

from utils.clipper import download_video, generate_clips
from utils.poster  import post_to_platform
from utils.ai_engine import generate_caption, generate_content_strategy

# ── Dirs ──────────────────────────────────────────────────────────────────────
for d in ["downloads", "clips"]:
    os.makedirs(d, exist_ok=True)

# ── Session state ─────────────────────────────────────────────────────────────
DEFAULTS = {
    "video_path":    None,
    "video_title":   "",
    "clips":         [],
    "captions":      {},
    "post_log":      [],
    "auto_running":  False,
    "ready":         False,
    "strategy":      "",
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

ALL_PLATFORMS = [
    "Twitter/X", "Instagram", "TikTok",
    "Facebook", "LinkedIn", "YouTube Shorts", "Reddit",
]

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.hero{background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);
      border-radius:16px;padding:2rem 2.5rem;margin-bottom:1.5rem;
      border:1px solid #7c3aed44;}
.hero h1{font-size:2.2rem;font-weight:700;margin:0;
         background:linear-gradient(135deg,#a78bfa,#60a5fa,#f472b6);
         -webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.hero p{color:#94a3b8;margin:.3rem 0 0;font-size:1rem;}
.card{background:#1a1a2e;border:1px solid #2d2d4a;border-radius:12px;
      padding:1.25rem 1.5rem;margin-bottom:.75rem;}
.log-ok{color:#10b981;} .log-err{color:#ef4444;}
section[data-testid="stSidebar"]{background:#0d0d1a;border-right:1px solid #1a1a2e;}
</style>
""", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚙️ Configuration")

    # ── AI Keys ───────────────────────────────────────
    with st.expander("🤖 AI Keys", expanded=True):
        st.caption("Get Gemini free at aistudio.google.com")
        gemini_key = st.text_input(
            "Gemini API Key (free)",
            type="password",
            value=os.getenv("GEMINI_API_KEY", ""),
        )
        st.caption("Get Groq free at console.groq.com")
        groq_key = st.text_input(
            "Groq API Key (free fallback)",
            type="password",
            value=os.getenv("GROQ_API_KEY", ""),
        )

    # ── Social credentials ─────────────────────────────
    with st.expander("📱 Twitter / X"):
        tw_key     = st.text_input("API Key",       type="password", key="twk")
        tw_secret  = st.text_input("API Secret",    type="password", key="tws")
        tw_token   = st.text_input("Access Token",  type="password", key="twt")
        tw_tsecret = st.text_input("Access Secret", type="password", key="twts")

    with st.expander("📘 Facebook"):
        fb_token   = st.text_input("Page Token",   type="password", key="fbt")
        fb_page_id = st.text_input("Page ID",                        key="fbp")

    with st.expander("💼 LinkedIn"):
        li_token = st.text_input("Access Token", type="password", key="lit")
        li_urn   = st.text_input("Person URN",   placeholder="urn:li:person:XXX")

    with st.expander("▶️ YouTube Shorts"):
        yt_secrets = st.text_input(
            "client_secrets.json path",
            placeholder="/path/to/client_secrets.json",
        )

    with st.expander("📸 Instagram"):
        ig_token   = st.text_input("Access Token",   type="password", key="igt")
        ig_user_id = st.text_input("Instagram User ID")

    with st.expander("🤖 Reddit"):
        reddit_client_id     = st.text_input("Client ID",     key="rci")
        reddit_client_secret = st.text_input("Client Secret", type="password", key="rcs")
        reddit_username      = st.text_input("Username",      key="ru")
        reddit_password      = st.text_input("Password",      type="password", key="rp")
        reddit_subreddit     = st.text_input("Subreddit",     value="videos", key="rs")

    # ── Post settings ──────────────────────────────────
    st.markdown("---")
    st.markdown("### 🚀 Post Settings")
    platforms_selected = st.multiselect(
        "Active platforms",
        ALL_PLATFORMS,
        default=["Twitter/X"],
    )
    post_interval = st.slider("Minutes between posts", 1, 120, 15)
    add_watermark = st.toggle("Add watermark to clips", value=False)

    st.markdown("---")
    st.metric("Clips ready",   len(st.session_state.clips))
    st.metric("Posts sent",    len(st.session_state.post_log))
    if st.session_state.auto_running:
        st.success("🟢 Auto-posting active")

# Bundle credentials
creds = {
    "tw_key": tw_key,         "tw_secret": tw_secret,
    "tw_token": tw_token,     "tw_tsecret": tw_tsecret,
    "fb_token": fb_token,     "fb_page_id": fb_page_id,
    "li_token": li_token,     "li_urn": li_urn,
    "yt_secrets": yt_secrets,
    "ig_token": ig_token,     "ig_user_id": ig_user_id,
    "reddit_client_id": reddit_client_id,
    "reddit_client_secret": reddit_client_secret,
    "reddit_username": reddit_username,
    "reddit_password": reddit_password,
    "reddit_subreddit": reddit_subreddit,
}

# ═════════════════════════════════════════════════════
# HERO
# ═════════════════════════════════════════════════════
st.markdown("""
<div class="hero">
  <h1>🎬 ClipMaster Pro</h1>
  <p>Autonomous video clip generator · AI captions · Multi-platform publisher</p>
</div>
""", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════
# TABS
# ═════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📥 Download",
    "✂️ Generate Clips",
    "📤 Publish",
    "📈 Strategy",
    "📋 Log",
])

# ════════════════════════
# TAB 1 — DOWNLOAD
# ════════════════════════
with tab1:
    st.markdown("### Step 1 — Download your show or video")

    st.info(
        "**Supported:** Tubi TV · Pluto TV · YouTube · Dailymotion · Most public video URLs\n\n"
        "⚠️ DRM-protected streams (Netflix, Disney+, Hulu) cannot be downloaded.",
        icon="ℹ️",
    )

    source = st.radio(
        "Source platform",
        ["Tubi TV", "Pluto TV", "YouTube", "Direct MP4 URL", "Other"],
        horizontal=True,
    )

    examples = {
        "Tubi TV":        "https://tubitv.com/movies/000000/show-name",
        "Pluto TV":       "https://pluto.tv/live-tv/channel-name",
        "YouTube":        "https://youtube.com/watch?v=XXXXXXXXXXX",
        "Direct MP4 URL": "https://example.com/video.mp4",
        "Other":          "https://...",
    }
    video_url = st.text_input("Video URL", placeholder=examples[source])
    title_input = st.text_input(
        "Content title",
        placeholder='e.g. "The Office S02E05" or "ESPN Highlights"',
    )

    c1, c2, c3 = st.columns(3)
    num_clips    = c1.slider("Clips to generate",    7, 10, 8)
    clip_length  = c2.slider("Clip length (sec)",   30, 90, 60)

    if st.button("⬇️ Download Now", type="primary", disabled=not video_url):
        with st.spinner("Downloading... please wait."):
            path = download_video(video_url)

        if path and os.path.exists(path):
            st.session_state.video_path  = path
            st.session_state.video_title = title_input or os.path.basename(path)
            st.session_state.ready       = True
            st.session_state.clips       = []
            st.session_state.captions    = {}
            size_mb = os.path.getsize(path) / 1e6
            st.success(f"✅ Downloaded! `{os.path.basename(path)}` ({size_mb:.1f} MB)")
        else:
            st.error(
                "❌ Download failed.\n\n"
                "**Try these fixes:**\n"
                "- Make sure the URL is the actual video page URL\n"
                "- Try a YouTube video first to confirm it works\n"
                "- Tubi/Pluto may require the full episode URL from your browser\n"
                "- Some content uses DRM and cannot be downloaded"
            )

    if st.session_state.video_path:
        st.markdown("---")
        st.success(f"**Loaded:** {st.session_state.video_title}")

# ════════════════════════
# TAB 2 — GENERATE CLIPS
# ════════════════════════
with tab2:
    st.markdown("### Step 2 — Generate & caption your clips")

    if not st.session_state.ready:
        st.info("👈 Download a video in Tab 1 first.")
    else:
        st.success(f"Source: **{st.session_state.video_title}**")

        col_a, col_b = st.columns(2)
        num_clips_tab2   = col_a.slider("Number of clips", 7, 10, 8,  key="nc2")
        clip_length_tab2 = col_b.slider("Clip length (s)", 30, 90, 60, key="cl2")

        if st.button("⚡ Generate Clips + AI Captions", type="primary"):
            prog   = st.progress(0.0)
            status = st.empty()

            def cb(pct, msg):
                prog.progress(pct, msg)
                status.info(f"**{msg}**")

            clips = generate_clips(
                st.session_state.video_path,
                num_clips=num_clips_tab2,
                clip_duration=clip_length_tab2,
                watermark=add_watermark,
                progress_callback=cb,
            )

            if not clips:
                st.error("No clips generated. Video may be too short or corrupted.")
            else:
                st.session_state.clips = clips
                status.info("Generating AI captions...")

                captions = {}
                for i, _ in enumerate(clips):
                    for platform in (platforms_selected or ["Twitter/X"]):
                        key = f"{i}_{platform}"
                        captions[key] = generate_caption(
                            clip_number=i + 1,
                            source_title=st.session_state.video_title,
                            platform=platform,
                            gemini_key=gemini_key,
                            groq_key=groq_key,
                        )

                st.session_state.captions = captions
                prog.progress(1.0, "All clips and captions ready!")
                st.success(f"✅ {len(clips)} clips generated!")
                st.balloons()

        # Preview
        if st.session_state.clips:
            st.markdown(f"#### 📹 {len(st.session_state.clips)} Clips")
            cols = st.columns(3)
            for i, clip_path in enumerate(st.session_state.clips):
                if not os.path.exists(clip_path):
                    continue
                with cols[i % 3]:
                    st.video(clip_path)
                    st.caption(f"**Clip #{i+1}**")
                    for platform in (platforms_selected or ["Twitter/X"]):
                        cap_key = f"{i}_{platform}"
                        if cap_key in st.session_state.captions:
                            with st.expander(f"✏️ {platform} caption"):
                                edited = st.text_area(
                                    "Caption",
                                    value=st.session_state.captions[cap_key],
                                    key=f"edit_{cap_key}",
                                    height=110,
                                    label_visibility="collapsed",
                                )
                                st.session_state.captions[cap_key] = edited

# ════════════════════════
# TAB 3 — PUBLISH
# ════════════════════════
with tab3:
    st.markdown("### Step 3 — Publish")

    if not st.session_state.clips:
        st.info("👈 Generate clips in Tab 2 first.")
    else:
        st.markdown(
            f"**{len(st.session_state.clips)} clips** · "
            f"**{len(platforms_selected)} platforms** · "
            f"**{post_interval} min interval**"
        )

        col1, col2 = st.columns(2)

        # Post all immediately
        if col1.button("🚀 Post All Now", type="primary", use_container_width=True):
            total = len(st.session_state.clips) * len(platforms_selected)
            prog  = st.progress(0.0)
            done  = 0

            for i, clip_path in enumerate(st.session_state.clips):
                if not os.path.exists(clip_path):
                    continue
                for platform in platforms_selected:
                    cap_key = f"{i}_{platform}"
                    caption = st.session_state.captions.get(
                        cap_key,
                        f"Clip #{i+1} — {st.session_state.video_title} 🎬 #Viral #FYP",
                    )
                    result = post_to_platform(platform, caption, clip_path, creds)
                    st.session_state.post_log.append({
                        "time":     datetime.now().strftime("%H:%M:%S"),
                        "clip":     f"Clip #{i+1}",
                        "platform": platform,
                        "success":  result.get("success", False),
                        "url":      result.get("url", ""),
                        "error":    result.get("error", ""),
                    })
                    done += 1
                    prog.progress(done / total, f"Posted {done}/{total}")

            st.success("✅ All done! Check the Log tab.")
            st.rerun()

        # Auto-post with interval
        if col2.button(
            "⏱️ Auto-Post (interval)",
            use_container_width=True,
            disabled=st.session_state.auto_running,
        ):
            st.session_state.auto_running = True

            def _auto():
                clips = st.session_state.clips[:]
                for i, clip_path in enumerate(clips):
                    if not st.session_state.auto_running:
                        break
                    if not os.path.exists(clip_path):
                        continue
                    for platform in platforms_selected:
                        cap_key = f"{i}_{platform}"
                        caption = st.session_state.captions.get(
                            cap_key,
                            f"Clip #{i+1} — {st.session_state.video_title} 🎬 #Viral #FYP",
                        )
                        result = post_to_platform(platform, caption, clip_path, creds)
                        st.session_state.post_log.append({
                            "time":     datetime.now().strftime("%H:%M:%S"),
                            "clip":     f"Clip #{i+1}",
                            "platform": platform,
                            "success":  result.get("success", False),
                            "url":      result.get("url", ""),
                            "error":    result.get("error", ""),
                        })
                    if i < len(clips) - 1:
                        time.sleep(post_interval * 60)

                st.session_state.auto_running = False

            threading.Thread(target=_auto, daemon=True).start()
            st.success(
                f"⏱️ Auto-posting {len(st.session_state.clips)} clips "
                f"every {post_interval} min. Check Log tab for progress."
            )

        if st.session_state.auto_running:
            if st.button("⏹️ Stop Auto-Post", type="secondary"):
                st.session_state.auto_running = False
                st.warning("Auto-post stopped.")

# ════════════════════════
# TAB 4 — STRATEGY
# ════════════════════════
with tab4:
    st.markdown("### 📈 AI Content Strategy")
    st.caption("Powered by Gemini / Groq — add a free API key in the sidebar.")

    if st.button("🧠 Generate Strategy", type="primary"):
        with st.spinner("Generating strategy..."):
            st.session_state.strategy = generate_content_strategy(
                source_title=st.session_state.video_title or "your content",
                num_clips=len(st.session_state.clips) or 8,
                platforms=platforms_selected or ALL_PLATFORMS,
                gemini_key=gemini_key,
                groq_key=groq_key,
            )

    if st.session_state.strategy:
        st.markdown(st.session_state.strategy)
        st.download_button(
            "⬇️ Download Strategy",
            st.session_state.strategy,
            "strategy.md",
            use_container_width=True,
        )

# ════════════════════════
# TAB 5 — LOG
# ════════════════════════
with tab5:
    st.markdown("### 📋 Post Log")

    if not st.session_state.post_log:
        st.info("No posts yet.")
    else:
        success_count = sum(1 for e in st.session_state.post_log if e["success"])
        fail_count    = len(st.session_state.post_log) - success_count

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Posted", len(st.session_state.post_log))
        m2.metric("✅ Success",   success_count)
        m3.metric("❌ Failed",    fail_count)

        st.markdown("---")
        for entry in reversed(st.session_state.post_log):
            icon = "✅" if entry["success"] else "❌"
            line = (
                f"{icon} `{entry['time']}` · **{entry['clip']}** → "
                f"**{entry['platform']}**"
            )
            if entry["success"] and entry.get("url"):
                line += f" · [View post]({entry['url']})"
            elif not entry["success"]:
                line += f" · `{entry.get('error', '')}`"
            st.markdown(line)

        if st.button("🗑️ Clear Log"):
            st.session_state.post_log = []
            st.rerun()
