#!/usr/bin/env python3
"""
Generates illustration from text. Supports 通义万相, Blotato API, or OpenAI DALL-E as fallback.
"""

import json
import os
import sys
from pathlib import Path

# Load .env from project root
try:
    from dotenv import load_dotenv
    _project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    load_dotenv(_project_root / ".env")
except ImportError:
    pass

try:
    import requests
except ImportError:
    requests = None


def load_config(project_root: Path) -> dict:
    """Load image gen config."""
    cfg_path = project_root / "config" / "image_gen.json"
    if cfg_path.exists():
        with open(cfg_path, encoding="utf-8") as f:
            return json.load(f)
    return {"provider": "openai", "fallback": None}


def generate_tongyi(prompt: str, output_path: str, config: dict) -> bool:
    """Generate via 通义万相 (阿里云 DashScope)."""
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        print("Set DASHSCOPE_API_KEY (阿里云控制台获取)", file=sys.stderr)
        return False
    cfg = config.get("tongyi", {})
    base_url = cfg.get("base_url") or os.environ.get("DASHSCOPE_HTTP_BASE_URL")
    if base_url:
        os.environ["DASHSCOPE_HTTP_BASE_URL"] = base_url.rstrip("/")
    try:
        from dashscope import ImageSynthesis
    except ImportError:
        print("Install: pip install dashscope", file=sys.stderr)
        return False
    model = cfg.get("model", "wanx2.1-t2i-turbo")
    size = cfg.get("size", "1024*1024")
    template = config.get("prompt_template", "{prompt}")
    full_prompt = template.format(prompt=prompt) if "{prompt}" in template else prompt
    rsp = ImageSynthesis.call(
        api_key=key,
        model=model,
        prompt=full_prompt,
        n=1,
        size=size,
    )
    if rsp.status_code != 200 or not rsp.output or not rsp.output.results:
        print(f"通义万相 API 错误: {getattr(rsp, 'message', rsp)}", file=sys.stderr)
        return False
    url = rsp.output.results[0].url
    if requests:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(r.content)
        return True
    print("Install requests to save image", file=sys.stderr)
    return False


def generate_openai(prompt: str, output_path: str) -> bool:
    """Generate via OpenAI DALL-E 3."""
    try:
        from openai import OpenAI
    except ImportError:
        print("Install: pip install openai", file=sys.stderr)
        return False
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("Set OPENAI_API_KEY", file=sys.stderr)
        return False
    client = OpenAI(api_key=key)
    resp = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        n=1,
    )
    url = resp.data[0].url
    if requests:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(r.content)
        return True
    print("Install requests to save image", file=sys.stderr)
    return False


def generate_placeholder(prompt: str, output_path: str) -> bool:
    """Create placeholder when no API available."""
    try:
        from PIL import Image
    except ImportError:
        print("No image API configured. Set DASHSCOPE_API_KEY or OPENAI_API_KEY.", file=sys.stderr)
        return False
    img = Image.new("RGB", (1024, 1024), color=(30, 60, 120))
    img.save(output_path)
    print(f"Placeholder saved (no API): {output_path}", file=sys.stderr)
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: generate_image.py <prompt> [--output path.png]", file=sys.stderr)
        sys.exit(1)

    prompt = sys.argv[1]
    output_path = "outputs/drafts/illustration.png"
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_path = sys.argv[idx + 1]

    script_dir = Path(__file__).resolve().parent
    # scripts/ -> image-gen-blotato/ -> skills/ -> .cursor/ -> project_root
    project_root = script_dir.parent.parent.parent.parent
    config = load_config(project_root)
    provider = config.get("provider", "openai")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    success = False
    if provider == "tongyi" and os.environ.get("DASHSCOPE_API_KEY"):
        success = generate_tongyi(prompt, output_path, config)
    if not success and os.environ.get("OPENAI_API_KEY"):
        success = generate_openai(prompt, output_path)
    if not success:
        success = generate_placeholder(prompt, output_path)

    if success:
        print(f"Saved: {output_path}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
