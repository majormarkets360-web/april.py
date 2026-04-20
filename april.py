from __future__ import annotations
import os
import time
import threading
import streamlit as st
from datetime import datetime

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ClipMaster Pro",
    page_icon="🎬",
    layout="wide",
)

# ── Imports ───────────────────────────────────────────────────────────────────
from utils.clipper import download_video, generate_clips
from utils.poster import (
    generate_caption_with_claude,
    post_to_twitter,
    post_to_instagram_basic,
    post_to_tiktok_manual,
)

# ── Directories ───────────────────────────────────────────────────────────────
os.makedirs("downloads", exist_ok=True)
os.makedirs("clips", exist_ok=True)

# ── Session state ─────────────────────────────────────────────────────────────
for key, val in {
    "video_path": None,
    "video_title": "",
    "clips": [],
    "captions": {},
    "post_log": [],
    "auto_running": False,
    "download_done": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ═════════════════════════════════════════════════════
# SIDEBAR — credentials
# ═════════════════════════════════════════════════════
with st.sidebar:
    st.title("🔑 Credentials")

    st.markdown("**Anthropic (for captions)**")
    anthropic_key = st.text_input(
        "Claude API Key", type="password",
        value=os.getenv("ANTHROPIC_API_KEY", ""),
    )

    st.markdown("---")
    st.markdown("**Twitter / X**")
    tw_key    = st.text_input("API Key",          type="password")
    tw_secret = st.text_input("API Secret",       type="password")
    tw_token  = st.text_input("Access Token",     type="password")
    tw_tsecret= st.text_input("Access Secret",    type="password")

    st.markdown("---")
    st.markdown("**Instagram (Graph API)**")
    ig_token   = st.text_input("Access Token",    type="password", key="ig_tok")
    ig_user_id = st.text_input("Instagram User ID")

    st.markdown("---")
    st.markdown("**Post Settings**")
    post_interval = st.slider(
        "Minutes between posts", 1, 60, 10,
        help="How long to wait between each clip post",
    )
    platforms_to_post = st.multiselect(
        "Post to",
        ["Twitter/X", "Instagram", "TikTok"],
        default=["Twitter/X"],
    )

    st.markdown("---")
    if st.session_state.post_log:
        st.markdown(f"**Posts sent:** {len(st.session_state.post_log)}")

# ═════════════════════════════════════════════════════
# HEADER
# ═════════════════════════════════════════════════════
st.markdown(
    """
    <div style="background:linear-gradient(135deg,#1a0a2e,#0f172a);
                border:1px solid #7c3aed44; border-radius:14px;
                padding:1.5rem 2rem; margin-bottom:1.5rem;">
        <h1 style="margin:0; background:linear-gradient(135deg,#a78bfa,#60a5fa);
                   -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                   font-size:2rem;">
            🎬 ClipMaster Pro
        </h1>
        <p style="color:#94a3b8; margin:0.3rem 0 0;">
            Download → Clip → Caption → Post · Fully autonomous
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ═════════════════════════════════════════════════════
# TABS
# ═════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs(
    ["📥 Download", "✂️ Generate Clips", "📤 Post", "📋 Log"]
)

# ══════════════════════════════
# TAB 1 — DOWNLOAD
# ══════════════════════════════
with tab1:
    st.markdown("### Step 1 — Get your video")

    platform_choice = st.radio(
        "Platform",
        ["Tubi TV", "Pluto TV", "Other URL"],
        horizontal=True,
    )

    if platform_choice == "Tubi TV":
        st.info("Go to **tubitv.com**, find a show, copy the URL from your browser.")
        example = "https://tubitv.com/movies/000000/show-name"
    elif platform_choice == "Pluto TV":
        st.info("Go to **pluto.tv**, start playing a channel, copy the URL.")
        example = "https://pluto.tv/live-tv/channel-name"
    else:
        example = "https://..."

    video_url = st.text_input("Video / Show URL", placeholder=example)
    video_title_input = st.text_input(
        "Short title for this content",
        placeholder='e.g. "Breaking Bad S01E01"',
    )

    col1, col2 = st.columns(2)
    max_duration = col1.slider("Max download duration (min)", 5, 60, 20)
    num_clips    = col2.slider("Number of clips to generate", 7, 10, 8)
    clip_length  = col1.slider("Clip length (seconds)", 30, 90, 60)

    if st.button("⬇️ Download Video", type="primary", disabled=not video_url):
        prog = st.progress(0, "Starting download...")
        status = st.empty()

        with st.spinner("Downloading — this may take a few minutes..."):
            prog.progress(10, "Connecting to platform...")
            path = download_video(video_url, "downloads")

        if path:
            st.session_state.video_path  = path
            st.session_state.video_title = video_title_input or os.path.basename(path)
            st.session_state.download_done = True
            st.session_state.clips = []
            st.session_state.captions = {}
            prog.progress(100, "Download complete!")
            st.success(f"✅ Downloaded: `{os.path.basename(path)}`")
            st.info(f"File size: {os.path.getsize(path) / 1e6:.1f} MB")
        else:
            prog.empty()
            st.error(
                "❌ Download failed. This usually means:\n"
                "- The platform requires login / DRM protection\n"
                "- The URL is incorrect\n"
                "- The content is geo-restricted\n\n"
                "**Try:** Right-click the video → Copy video address, or use a direct mp4 URL."
            )

    if st.session_state.video_path and os.path.exists(st.session_state.video_path):
        st.markdown("---")
        st.success(f"**Ready:** `{st.session_state.video_title}`")
        st.caption(
            f"Path: `{st.session_state.video_path}` · "
            f"Size: {os.path.getsize(st.session_state.video_path)/1e6:.1f} MB"
        )

# ══════════════════════════════
# TAB 2 — GENERATE CLIPS
# ══════════════════════════════
with tab2:
    st.markdown("### Step 2 — Generate clips")

    if not st.session_state.download_done or not st.session_state.video_path:
        st.info("👈 Download a video in Tab 1 first.")
    else:
        st.success(f"Source: **{st.session_state.video_title}**")

        if st.button("⚡ Generate Clips + Captions", type="primary"):
            progress_bar = st.progress(0)
            status_box   = st.empty()

            def update_progress(pct: float, msg: str):
                progress_bar.progress(pct, msg)
                status_box.info(msg)

            clips = generate_clips(
                st.session_state.video_path,
                num_clips=num_clips,
                clip_duration=clip_length,
                progress_callback=update_progress,
            )

            if not clips:
                st.error("No clips generated. The video may be too short or corrupted.")
            else:
                st.session_state.clips = clips
                status_box.info("Generating captions with Claude...")

                captions = {}
                for i, clip_path in enumerate(clips):
                    for platform in (platforms_to_post or ["Twitter/X"]):
                        cap = generate_caption_with_claude(
                            clip_number=i + 1,
                            source_title=st.session_state.video_title,
                            platform=platform,
                            api_key=anthropic_key,
                        )
                        captions[f"{i}_{platform}"] = cap

                st.session_state.captions = captions
                progress_bar.progress(1.0, "All clips ready!")
                st.success(f"✅ {len(clips)} clips generated!")

        # ── Preview clips ──────────────────────────────────────────────────
        if st.session_state.clips:
            st.markdown(f"#### 📹 {len(st.session_state.clips)} Clips Ready")
            cols = st.columns(min(len(st.session_state.clips), 3))

            for i, clip_path in enumerate(st.session_state.clips):
                if not os.path.exists(clip_path):
                    continue
                with cols[i % 3]:
                    st.video(clip_path)
                    st.caption(f"**Clip #{i+1}**")

                    for platform in (platforms_to_post or ["Twitter/X"]):
                        cap_key = f"{i}_{platform}"
                        if cap_key in st.session_state.captions:
                            with st.expander(f"Caption — {platform}"):
                                edited = st.text_area(
                                    "Edit caption",
                                    value=st.session_state.captions[cap_key],
                                    key=f"cap_{cap_key}",
                                    height=120,
                                    label_visibility="collapsed",
                                )
                                st.session_state.captions[cap_key] = edited

# ══════════════════════════════
# TAB 3 — POST
# ══════════════════════════════
with tab3:
    st.markdown("### Step 3 — Post to social media")

    if not st.session_state.clips:
        st.info("👈 Generate clips in Tab 2 first.")
    else:
        st.markdown(
            f"**{len(st.session_state.clips)} clips** ready to post to: "
            f"`{'  ·  '.join(platforms_to_post or ['None selected'])}`"
        )
        st.caption(
            f"Interval between posts: **{post_interval} minutes** · "
            f"Total time: ~{len(st.session_state.clips) * post_interval} minutes"
        )

        col_a, col_b = st.columns(2)

        # ── Post all at once ───────────────────────────────────────────────
        if col_a.button(
            "🚀 Post All Now",
            type="primary",
            use_container_width=True,
            disabled=not platforms_to_post,
        ):
            total = len(st.session_state.clips) * len(platforms_to_post)
            prog  = st.progress(0)
            done  = 0

            for i, clip_path in enumerate(st.session_state.clips):
                if not os.path.exists(clip_path):
                    continue

                for platform in platforms_to_post:
                    cap_key = f"{i}_{platform}"
                    caption = st.session_state.captions.get(
                        cap_key,
                        f"Clip #{i+1} from {st.session_state.video_title} 🎬 #Viral #FYP",
                    )

                    result = _post_single(
                        platform, clip_path, caption,
                        tw_key, tw_secret, tw_token, tw_tsecret,
                        ig_token, ig_user_id,
                    )

                    log_entry = {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "clip": f"Clip #{i+1}",
                        "platform": platform,
                        "success": result.get("success", False),
                        "url": result.get("url", ""),
                        "error": result.get("error", ""),
                    }
                    st.session_state.post_log.append(log_entry)

                    done += 1
                    prog.progress(done / total, f"Posted {done}/{total}")

            st.success("✅ All clips posted!")
            st.rerun()

        # ── Auto-post with interval ────────────────────────────────────────
        if col_b.button(
            "⏱️ Auto-Post (with interval)",
            use_container_width=True,
            disabled=not platforms_to_post or st.session_state.auto_running,
        ):
            st.session_state.auto_running = True

            def auto_post_thread():
                clips   = st.session_state.clips
                for i, clip_path in enumerate(clips):
                    if not st.session_state.auto_running:
                        break
                    if not os.path.exists(clip_path):
                        continue

                    for platform in platforms_to_post:
                        cap_key = f"{i}_{platform}"
                        caption = st.session_state.captions.get(
                            cap_key,
                            f"Clip #{i+1} 🎬 #Viral #FYP",
                        )
                        result = _post_single(
                            platform, clip_path, caption,
                            tw_key, tw_secret, tw_token, tw_tsecret,
                            ig_token, ig_user_id,
                        )
                        st.session_state.post_log.append({
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "clip": f"Clip #{i+1}",
                            "platform": platform,
                            "success": result.get("success", False),
                            "url": result.get("url", ""),
                            "error": result.get("error", ""),
                        })

                    # Wait interval before next clip
                    if i < len(clips) - 1:
                        time.sleep(post_interval * 60)

                st.session_state.auto_running = False

            t = threading.Thread(target=auto_post_thread, daemon=True)
            t.start()
            st.success(
                f"⏱️ Auto-posting started! {len(st.session_state.clips)} clips "
                f"every {post_interval} min. Check the Log tab."
            )

        if st.session_state.auto_running:
            if st.button("⏹️ Stop Auto-Post", type="secondary"):
                st.session_state.auto_running = False
                st.warning("Auto-post stopped.")

# ══════════════════════════════
# TAB 4 — LOG
# ══════════════════════════════
with tab4:
    st.markdown("### 📋 Post Log")

    if not st.session_state.post_log:
        st.info("No posts yet.")
    else:
        for entry in reversed(st.session_state.post_log):
            icon = "✅" if entry["success"] else "❌"
            line = f"{icon} `{entry['time']}` — **{entry['clip']}** → {entry['platform']}"
            if entry["success"] and entry.get("url"):
                line += f" — [View]({entry['url']})"
            elif not entry["success"]:
                line += f" — `{entry.get('error', 'Unknown error')}`"
            st.markdown(line)

        if st.button("🗑️ Clear Log"):
            st.session_state.post_log = []
            st.rerun()

# ═════════════════════════════════════════════════════
# HELPER — single platform post (defined after tabs
# so it's available in the module scope)
# ═════════════════════════════════════════════════════
def _post_single(
    platform: str,
    clip_path: str,
    caption: str,
    tw_key: str, tw_secret: str, tw_token: str, tw_tsecret: str,
    ig_token: str, ig_user_id: str,
) -> dict:
    if platform == "Twitter/X":
        return post_to_twitter(
            caption, clip_path,
            tw_key, tw_secret, tw_token, tw_tsecret,
        )
    elif platform == "Instagram":
        return post_to_instagram_basic(
            caption, clip_path, ig_token, ig_user_id,
        )
    elif platform == "TikTok":
        return post_to_tiktok_manual(caption, clip_path)
    return {"success": False, "error": f"Unknown platform: {platform}"}
