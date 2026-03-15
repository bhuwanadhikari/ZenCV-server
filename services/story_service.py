import json
from pathlib import Path
from typing import Any


def load_story_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as story_file:
        return json.load(story_file)
