from os import sep
from os.path import relpath
from pathlib import Path, PurePath

from ..state.types import State


def display_path(path: PurePath, state: State) -> str:
    raw = relpath(path, start=state.root.path)
    name = raw.encode("unicode_escape").decode("utf-8")
    if Path(path).is_dir():
        return f"{name}{sep}"
    else:
        return name
