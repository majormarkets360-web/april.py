from __future__ import annotations
import os
import json
import time
import subprocess
from typing import Optional, Callable
import numpy as np


def download_video(url: str, out_dir: str = "downloads") -> Optional[str]:
    os.makedirs(out_dir, exist_ok=True)

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--merge-output-format", "mp4",
        "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "-o", os.path.join(out_dir, "%(title).60s.%(ext)s"),
        "--no-warnings",
        url,
    ]

    try:
        subprocess.run(cmd, timeout=600, check=True)
        files = sorted(
            [os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.endswith(".mp4")],
            key=os.path.getmtime,
            reverse=True,
        )
        return files[0] if files else None
    except Exception as e:
        print(f"Download error: {e}")
        return None


def get_duration(path: str) -> float:
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", path,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        return 0.0


def detect_highlights(
    path: str,
    num_clips: int = 8,
    min_gap: int = 65,
) -> list[float]:
    import cv2

    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    duration = get_duration(path)

    scores: dict[float, float] = {}
    prev_gray = None
    frame_idx = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % int(fps) == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if prev_gray is not None:
                diff = cv2.absdiff(gray, prev_gray)
                ts = frame_idx / fps
                scores[ts] = float(np.mean(diff))
            prev_gray = gray
        frame_idx += 1
    cap.release()

    if not scores:
        step = max(1, duration / (num_clips + 1))
        return [round(step * i, 1) for i in range(1, num_clips + 1)]

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    highlights = []

    for ts, _ in ranked:
        if len(highlights) >= num_clips:
            break
        if ts > duration - 65:
            continue
        if not any(abs(ts - h) < min_gap for h in highlights):
            highlights.append(round(ts, 1))

    # Fill gaps with evenly spaced if needed
    if len(highlights) < num_clips:
        step = duration / (num_clips + 1)
        for i in range(1, num_clips + 1):
            t = round(step * i, 1)
            if t < duration - 65 and not any(abs(t - h) < min_gap for h in highlights):
                highlights.append(t)
            if len(highlights) >= num_clips:
                break

    return sorted(highlights[:num_clips])


def add_watermark(
    in_path: str,
    out_path: str,
    text: str = "🎬 ClipMaster",
) -> str:
    """Add subtle text watermark using ffmpeg drawtext."""
    cmd = [
        "ffmpeg", "-y", "-i", in_path,
        "-vf", (
            f"drawtext=text='{text}':fontsize=24:fontcolor=white@0.5:"
            "x=10:y=10:shadowcolor=black@0.5:shadowx=2:shadowy=2"
        ),
        "-c:a", "copy",
        "-preset", "fast",
        out_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=120, check=True)
        return out_path
    except Exception:
        return in_path  # return original if watermark fails


def cut_clip(
    path: str,
    start: float,
    duration: int = 60,
    out_path: str = "",
    add_fade: bool = True,
) -> Optional[str]:
    os.makedirs("clips", exist_ok=True)
    if not out_path:
        out_path = f"clips/clip_{int(start)}_{int(time.time())}.mp4"

    # Build filter for fade in/out
    vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
    if add_fade:
        vf += f",fade=t=in:st=0:d=0.5,fade=t=out:st={duration-1}:d=0.5"

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", path,
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-preset", "fast",
        "-crf", "23",
        "-movflags", "+faststart",
        out_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=180, check=True)
        return out_path if os.path.exists(out_path) else None
    except Exception as e:
        print(f"Cut error: {e}")
        return None


def generate_clips(
    video_path: str,
    num_clips: int = 8,
    clip_duration: int = 60,
    watermark: bool = True,
    progress_callback: Optional[Callable] = None,
) -> list[str]:
    os.makedirs("clips", exist_ok=True)
    duration = get_duration(video_path)

    if duration < clip_duration + 10:
        return []

    if progress_callback:
        progress_callback(0.05, "Scanning video for best moments...")

    highlights = detect_highlights(video_path, num_clips)

    clips = []
    for i, start in enumerate(highlights):
        if progress_callback:
            pct = 0.05 + 0.85 * (i / len(highlights))
            progress_callback(pct, f"Cutting clip {i+1} of {len(highlights)}...")

        raw_path  = f"clips/raw_{i+1}_{int(time.time())}.mp4"
        final_path = f"clips/clip_{i+1}_{int(time.time())}.mp4"

        result = cut_clip(video_path, start, clip_duration, raw_path)

        if result:
            if watermark:
                final = add_watermark(raw_path, final_path)
                # Clean up raw
                if os.path.exists(raw_path) and raw_path != final:
                    os.remove(raw_path)
            else:
                final = raw_path
            if final and os.path.exists(final):
                clips.append(final)

    if progress_callback:
        progress_callback(1.0, f"Done! {len(clips)} clips ready.")

    return clips
