from __future__ import annotations

from dataclasses import dataclass
from os import listdir, stat
from os.path import basename, join, splitext
from stat import S_ISDIR, S_ISLNK
from typing import List, cast

from .types import Dir, File, Index, Node, Selection


@dataclass
class FSStat:
    is_link: bool
    is_dir: bool


def fs_stat(path: str) -> FSStat:
    info = stat(path, follow_symlinks=False)
    is_link = S_ISLNK(info.st_mode)
    if is_link:
        link_info = stat(path, follow_symlinks=True)
        is_dir = S_ISDIR(link_info.st_mode)
        return FSStat(is_link=True, is_dir=is_dir)
    else:
        is_dir = S_ISDIR(info.st_mode)
        return FSStat(is_link=False, is_dir=is_dir)


def parse(root: str, *, index: Selection) -> Node:
    info = fs_stat(root)
    name = basename(root)
    if not info.is_dir:
        _, ext = splitext(name)
        return File(path=root, is_link=info.is_link, name=name, ext=ext[1:])

    elif root in index:
        files: List[File] = []
        children: List[Dir] = []
        for el in listdir(root):
            child = parse(join(root, el), index=index)
            if type(child) is File:
                files.append(cast(File, child))
            else:
                children.append(cast(Dir, child))
        return Dir(
            path=root, is_link=info.is_link, name=name, files=files, children=children
        )

    else:
        return Dir(
            path=root, is_link=info.is_link, name=name, files=None, children=None,
        )


def new(root: str, index: Selection) -> Index:
    node = parse(root, index=index)
    assert type(node) == Dir
    return Index(index=index, root=cast(Dir, node))


def add(index: Index, path: str) -> Index:
    if path in index.index:
        return index
    else:
        return index


def remove(index: Index, path: str) -> Index:
    if path not in index.index:
        return index
    else:
        return index
