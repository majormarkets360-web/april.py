from __future__ import annotations
import os
import time
import subprocess
import json
from typing import Optional
import numpy as np


def download_video(url: str, out_dir: str = "downloads") -> Optional[str]:
    """Download video from Tubi/Pluto using yt-dlp. Returns file path or None."""
    os.makedirs(out_dir, exist_ok=True)
    out_template = os.path.join(out_dir, "%(title).50s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--merge-output-format", "mp4",
        "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "-o", out_template,
        "--print", "filename",
        url,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            return None
        # Find the downloaded file
        for line in result.stdout.strip().split("\n"):
            if line.endswith(".mp4") and os.path.exists(line):
                return line
        # Fallback: find newest mp4 in out_dir
        files = [
            os.path.join(out_dir, f)
            for f in os.listdir(out_dir)
            if f.endswith(".mp4")
        ]
        if files:
            return max(files, key=os.path.getmtime)
        return None
    except Exception as e:
        print(f"Download error: {e}")
        return None


def get_video_duration(path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception:
        return 0.0


def detect_highlight_times(
    video_path: str,
    num_clips: int = 8,
    sample_every: int = 60,
) -> list[float]:
    """
    Detect scene changes to find highlight start times.
    Returns list of timestamps in seconds.
    """
    import cv2

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps

    scores = {}
    prev_gray = None
    frame_idx = 0
    sample_interval = int(fps * sample_every)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % max(1, int(fps)) == 0:  # check every second
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if prev_gray is not None:
                diff = cv2.absdiff(gray, prev_gray)
                score = float(np.mean(diff))
                timestamp = frame_idx / fps
                scores[timestamp] = score
            prev_gray = gray
        frame_idx += 1

    cap.release()

    if not scores:
        # Fallback: evenly spaced
        step = max(1, duration / (num_clips + 1))
        return [step * i for i in range(1, num_clips + 1)]

    # Sort by score descending, pick top timestamps
    sorted_times = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    highlights = []
    min_gap = 60  # minimum seconds between clips

    for ts, _ in sorted_times:
        if len(highlights) >= num_clips:
            break
        # Ensure clips don't overlap
        too_close = any(abs(ts - h) < min_gap for h in highlights)
        if not too_close and ts < duration - 60:
            highlights.append(ts)

    # If not enough highlights, fill with evenly spaced
    if len(highlights) < num_clips:
        step = duration / (num_clips + 1)
        for i in range(1, num_clips + 1):
            t = step * i
            if t < duration - 60 and not any(abs(t - h) < min_gap for h in highlights):
                highlights.append(t)
            if len(highlights) >= num_clips:
                break

    return sorted(highlights[:num_clips])


def cut_clip(
    video_path: str,
    start: float,
    duration: float = 60,
    out_path: str = "",
) -> Optional[str]:
    """Cut a clip using ffmpeg. Returns output path or None."""
    if not out_path:
        os.makedirs("clips", exist_ok=True)
        out_path = f"clips/clip_{int(start)}_{int(time.time())}.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", video_path,
        "-t", str(duration),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-preset", "fast",
        "-movflags", "+faststart",
        out_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode == 0 and os.path.exists(out_path):
            return out_path
        return None
    except Exception as e:
        print(f"Cut error: {e}")
        return None


def generate_clips(
    video_path: str,
    num_clips: int = 8,
    clip_duration: int = 60,
    progress_callback=None,
) -> list[str]:
    """
    Main function: detect highlights and cut clips.
    Returns list of clip file paths.
    """
    os.makedirs("clips", exist_ok=True)
    duration = get_video_duration(video_path)

    if duration < clip_duration:
        return []

    if progress_callback:
        progress_callback(0.1, "Analyzing video for highlights...")

    highlight_times = detect_highlight_times(video_path, num_clips)

    clips = []
    for i, start in enumerate(highlight_times):
        if progress_callback:
            pct = 0.1 + (0.85 * (i / len(highlight_times)))
            progress_callback(pct, f"Cutting clip {i+1}/{len(highlight_times)}...")

        out_path = f"clips/clip_{i+1}_{int(time.time())}.mp4"
        result = cut_clip(video_path, start, clip_duration, out_path)
        if result:
            clips.append(result)

    if progress_callback:
        progress_callback(1.0, "Done!")

    return clips
