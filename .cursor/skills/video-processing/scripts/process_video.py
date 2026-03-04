#!/usr/bin/env python3
"""
Processes video from JSON instructions. Maps ops to FFmpeg commands.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def check_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
    return shutil.which("ffmpeg") is not None


def run_ffmpeg(args: list[str]) -> bool:
    """Run ffmpeg with given args."""
    cmd = ["ffmpeg", "-y"] + args
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error: {e.stderr.decode()}", file=sys.stderr)
        return False


def op_concat(inputs: list[str], output: str, workdir: Path) -> str | None:
    """Concatenate videos using concat demuxer."""
    if not inputs:
        print("Concat: no input files provided", file=sys.stderr)
        return None
    for p in inputs:
        if not Path(p).exists():
            print(f"Concat: input file not found: {p}", file=sys.stderr)
            return None
    if len(inputs) < 2:
        return inputs[0]
    list_file = workdir / "concat_list.txt"
    with open(list_file, "w") as f:
        for p in inputs:
            abs_p = Path(p).resolve()
            f.write(f"file '{abs_p}'\n")
    args = ["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", output]
    if run_ffmpeg(args):
        return output
    return None


def op_scale(input_path: str, output: str, width: int = 720, height: int = 1280) -> str | None:
    """Scale video to target resolution."""
    args = [
        "-i", input_path,
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "-c:a", "copy",
        output
    ]
    if run_ffmpeg(args):
        return output
    return None


def op_overlay(input_path: str, image_path: str, output: str, position: str = "top-right") -> str | None:
    """Overlay image on video."""
    if not Path(image_path).exists():
        print(f"Overlay: image not found: {image_path}", file=sys.stderr)
        return None
    pos_map = {
        "top-right": "main_w-overlay_w-10:10",
        "top-left": "10:10",
        "bottom-right": "main_w-overlay_w-10:main_h-overlay_h-10",
        "bottom-left": "10:main_h-overlay_h-10",
        "center": "(main_w-overlay_w)/2:(main_h-overlay_h)/2",
    }
    overlay_pos = pos_map.get(position, pos_map["top-right"])
    filter_str = f"[0:v][1:v]scale2ref=iw/4:ow/iw*ih[ov][base];[base][ov]overlay={overlay_pos}"
    args = ["-i", input_path, "-i", image_path, "-filter_complex", filter_str, "-c:a", "copy", output]
    if run_ffmpeg(args):
        return output
    return None


def op_watermark(input_path: str, output: str, text: str) -> str | None:
    """Add text watermark using drawtext filter."""
    escaped = text.replace(":", "\\:").replace("'", "\\'")
    filter_str = f"drawtext=text='{escaped}':fontsize=24:fontcolor=white@0.7:x=w-tw-20:y=h-th-20"
    args = ["-i", input_path, "-vf", filter_str, "-c:a", "copy", output]
    if run_ffmpeg(args):
        return output
    return None


def op_trim(input_path: str, output: str, start: float, end: float) -> str | None:
    """Trim video by seconds."""
    args = [
        "-ss", str(start), "-i", input_path, "-t", str(end - start),
        "-c", "copy", "-avoid_negative_ts", "make_zero", output
    ]
    if run_ffmpeg(args):
        return output
    return None


def process_instructions(instructions: dict, workdir: Path, output_path: str) -> bool:
    """Process all ops in sequence."""
    ops = instructions.get("ops", [])
    if not ops:
        print("No ops in instructions", file=sys.stderr)
        return False

    current = None
    for i, op in enumerate(ops):
        op_type = op.get("type")
        if op_type == "concat":
            inputs = op.get("inputs", [])
            current = op_concat(inputs, str(workdir / f"step_{i}.mp4"), workdir)
        elif op_type == "scale":
            if not current:
                print("Scale needs prior output", file=sys.stderr)
                return False
            w = op.get("width", 720)
            h = op.get("height", 1280)
            current = op_scale(current, str(workdir / f"step_{i}.mp4"), w, h)
        elif op_type == "overlay":
            if not current:
                print("Overlay needs prior output", file=sys.stderr)
                return False
            img = op.get("image", "")
            pos = op.get("position", "top-right")
            current = op_overlay(current, img, str(workdir / f"step_{i}.mp4"), pos)
        elif op_type == "watermark":
            if not current:
                print("Watermark needs prior output", file=sys.stderr)
                return False
            text = op.get("text", "@account")
            current = op_watermark(current, str(workdir / f"step_{i}.mp4"), text)
        elif op_type == "trim":
            if not current:
                print("Trim needs prior output", file=sys.stderr)
                return False
            start = op.get("start", 0)
            end = op.get("end", 30)
            current = op_trim(current, str(workdir / f"step_{i}.mp4"), start, end)
        elif op_type == "export":
            if current:
                fmt = op.get("format", "mp4")
                res = op.get("resolution", "720x1280")
                parts = res.split("x")
                w, h = int(parts[0]), int(parts[1]) if len(parts) > 1 else 1280
                final = op_scale(current, output_path, w, h) if w and h else None
                if not final and current:
                    shutil.copy(current, output_path)
            break

    return current is not None


def main():
    if len(sys.argv) < 2:
        print("Usage: process_video.py <instructions.json> [--output output.mp4]", file=sys.stderr)
        sys.exit(1)

    if not check_ffmpeg():
        print("FFmpeg not found. Install: https://ffmpeg.org/", file=sys.stderr)
        sys.exit(1)

    instr_path = sys.argv[1]
    output_path = "output.mp4"
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_path = sys.argv[idx + 1]

    with open(instr_path, encoding="utf-8") as f:
        instructions = json.load(f)

    with tempfile.TemporaryDirectory() as workdir:
        success = process_instructions(instructions, Path(workdir), output_path)

    if success:
        print(f"Output: {output_path}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
