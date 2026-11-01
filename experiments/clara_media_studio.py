"""Offline-first Clara video job specifications. No rendering or paid API calls."""
from dataclasses import asdict, dataclass
from pathlib import Path
import json
import re

ALLOWED_IMAGES = {
    "clara-blonde-body.webp",
    "clara-standing-business.webp",
    "clara-outfit-business.webp",
}
MAX_SCRIPT = 700

@dataclass(frozen=True)
class VideoJob:
    engine: str
    image: str
    script: str
    aspect_ratio: str
    status: str
    requires_owner_approval: bool
    production_enabled: bool

def prepare_video_job(image: str, script: str) -> dict:
    """Prepare a reviewed LTX-oriented storyboard, not a rendered video."""
    if image not in ALLOWED_IMAGES:
        raise ValueError("Image must be an approved existing Clara asset")
    if not isinstance(script, str) or not 1 <= len(script.strip()) <= MAX_SCRIPT:
        raise ValueError("English script length must be 1–700 characters")
    if re.search(r"[\u0600-\u06ff]", script):
        raise ValueError("Clara video scripts must be English")
    if any(ord(c) < 32 and c not in "\n\t" for c in script):
        raise ValueError("Invalid control character")
    return asdict(VideoJob(
        engine="LTX-2 (external inference not configured)",
        image="static/" + image,
        script=script.strip(),
        aspect_ratio="9:16",
        status="prepared_not_rendered",
        requires_owner_approval=True,
        production_enabled=False,
    ))

if __name__ == "__main__":
    example = prepare_video_job(
        "clara-standing-business.webp",
        "Hi, I'm Clara. AgentVault is under development. Follow our progress.")
    print(json.dumps(example, indent=2))
