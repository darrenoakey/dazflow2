"""Tags management for agent capability-based routing."""

import json
from pathlib import Path

from .config import get_config


# ##################################################################
# list all tags
# returns list of tag strings from tags file
def list_tags() -> list[str]:
    config = get_config()
    tags_file = Path(config.tags_file)

    if not tags_file.exists():
        return []

    with open(tags_file) as f:
        return json.load(f)


# ##################################################################
# save tags to file
# writes list of tags to tags file
def _save_tags(tags: list[str]) -> None:
    config = get_config()
    tags_file = Path(config.tags_file)
    tags_file.parent.mkdir(parents=True, exist_ok=True)

    with open(tags_file, "w") as f:
        json.dump(tags, f, indent=2)


# ##################################################################
# create new tag
# adds tag to list if not already present
def create_tag(name: str) -> bool:
    tags = list_tags()

    if name in tags:
        return False

    tags.append(name)
    _save_tags(tags)
    return True


# ##################################################################
# delete tag
# removes tag from list if present
def delete_tag(name: str) -> bool:
    tags = list_tags()

    if name not in tags:
        return False

    tags.remove(name)
    _save_tags(tags)
    return True
