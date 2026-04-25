"""
Creator Registry Module

Thin facade over pipeline_categories. The registry itself no longer holds
data; callers use these helpers to discover subtypes and build creator
instances. The folder-creator dispatch funnels everything through
GenericFolderStructureCreator using a manifest pulled from the unified tree.
"""

import importlib
from functools import partial
from typing import Dict, List, Optional, Callable, Any

from pipeline_categories import (
    creative_categories as _creative_categories,
    is_creative_category as _is_creative_category,
    get_creative_subtypes as _get_creative_subtypes,
    has_multiple_creative_subtypes as _has_multiple_creative_subtypes,
    subtype_manifest as _subtype_manifest,
    subtype_display_name as _subtype_display_name,
)


# Backwards-compatible export — some callers iterate this list.
CREATIVE_CATEGORIES: List[str] = _creative_categories()


def get_subtypes_for_category(category: str) -> List[str]:
    return _get_creative_subtypes(category)


def get_subtype_display_name(subtype: str) -> str:
    return _subtype_display_name(subtype)


def has_multiple_subtypes(category: str) -> bool:
    return _has_multiple_creative_subtypes(category)


def is_creative_category(category: str) -> bool:
    return _is_creative_category(category)


def get_creator_class(category: str, subtype: str) -> Optional[Callable]:
    """Return a callable that instantiates the folder creator for (category, subtype).

    Calling convention matches the legacy per-script constructors:
    ``creator(parent, embedded=..., on_project_created=..., on_cancel=...,
    project_db=...)``.
    """
    manifest = _subtype_manifest(category, subtype)
    if manifest is None or not manifest.get("tree_template"):
        return None
    try:
        module = importlib.import_module("shared_folder_structure_creator")
        generic = getattr(module, "GenericFolderStructureCreator")
        return partial(generic, manifest=manifest)
    except (ImportError, AttributeError) as e:
        print(f"Failed to import GenericFolderStructureCreator: {e}")
        return None


def get_creator_info(category: str, subtype: str) -> Optional[Dict[str, Any]]:
    return _subtype_manifest(category, subtype)
