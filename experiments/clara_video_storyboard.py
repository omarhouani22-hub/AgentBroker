"""Clara LTX-2 storyboard and preview manifest; no external inference."""
from dataclasses import dataclass, asdict
from pathlib import Path
import json
from experiments.clara_media_studio import prepare_video_job

@dataclass(frozen=True)
class Shot:
    start_seconds: int
    duration_seconds: int
    camera: str
    motion: str
    dialogue: str

def build_storyboard(image="clara-standing-business.webp"):
    dialogue = "Hi, I'm Clara. AgentVault is under development. Follow our progress."
    job = prepare_video_job(image, dialogue)
    shots = [
        Shot(0, 2, "medium shot", "natural blink and subtle head turn", "Hi, I'm Clara."),
        Shot(2, 3, "medium shot", "small welcoming hand gesture", "AgentVault is under development."),
        Shot(5, 2, "medium shot", "soft smile and eye contact", "Follow our progress."),
    ]
    return {
        "job": job,
        "duration_seconds": 7,
        "shots": [asdict(shot) for shot in shots],
        "identity_rule": "Use approved Clara image. No face, skin, hairstyle, or outfit changes.",
        "marketing_rule": "Do not claim that AgentVault is live or accepting payments.",
        "status": "storyboard_only_no_video_rendered",
    }

if __name__ == "__main__":
    print(json.dumps(build_storyboard(), indent=2))
