"""
Creator Registry Module

Maps categories to their folder structure creator scripts.
Provides utilities for dynamic loading and subtype discovery.

Subtypes listed in folder_structure_manifest.MANIFEST are routed to
GenericFolderStructureCreator; legacy entries fall back to the per-script
creator class declared below.
"""

import importlib
from functools import partial
from typing import Dict, List, Optional, Callable, Any

from folder_structure_manifest import get_manifest as _get_manifest

# Subtypes that have been validated against GenericFolderStructureCreator.
# Add (category, subtype) tuples here as each migration is verified; once all
# 9 are listed, the legacy CREATOR_REGISTRY below can be deleted entirely.
MIGRATED_SUBTYPES = {
    ("Visual", "GD"),
    ("Visual", "FX"),
    ("Visual", "VJ"),
    ("RealTime", "Godot"),
    ("RealTime", "TD"),
    ("Audio", "Audio"),
    ("Web", "Web"),
    ("Photo", "Photo"),
    ("Physical", "Physical"),
}


# Registry mapping categories to their subtypes and creator modules
CREATOR_REGISTRY: Dict[str, Dict[str, Dict[str, Any]]] = {
    "Visual": {
        "GD": {
            "module": "PipelineScript_Visual_FolderStructure_GD",
            "class": "FolderStructureCreator",
            "display_name": "Graphic Design",
            "icon": "GD",
        },
        "FX": {
            "module": "PipelineScript_Visual_FolderStructure_FX",
            "class": "FolderStructureCreator",
            "display_name": "Visual Effects",
            "icon": "FX",
        },
        "VJ": {
            "module": "PipelineScript_Visual_FolderStructure_VJ",
            "class": "VJFolderStructureCreator",
            "display_name": "Live Video",
            "icon": "VJ",
        },
    },
    "RealTime": {
        "Godot": {
            "module": "PipelineScript_RealTime_FolderStructure_Godot",
            "class": "FolderStructureCreator",
            "display_name": "Godot",
            "icon": "Godot",
        },
        "TD": {
            "module": "PipelineScript_RealTime_FolderStructure_TouchDesigner",
            "class": "FolderStructureCreator",
            "display_name": "TouchDesigner",
            "icon": "TD",
        },
    },
    "Audio": {
        "Audio": {
            "module": "PipelineScript_Audio_FolderStructure",
            "class": "FolderStructureCreator",
            "display_name": "Audio Production",
            "icon": "Audio",
        },
    },
    "Physical": {
        "Physical": {
            "module": "PipelineScript_Physical_FolderStructure",
            "class": "FolderStructureCreator",
            "display_name": "3D Print / Physical",
            "icon": "3D",
        },
    },
    "Photo": {
        "Photo": {
            "module": "PipelineScript_Photo_FolderStructure",
            "class": "PhotoFolderStructureCreator",
            "display_name": "Photography",
            "icon": "Photo",
        },
    },
    "Web": {
        "Web": {
            "module": "PipelineScript_Web_FolderStructure",
            "class": "FolderStructureCreator",
            "display_name": "Web Development",
            "icon": "Web",
        },
    },
}

# Human-readable display names for subtypes (used in buttons)
SUBTYPE_DISPLAY_NAMES: Dict[str, str] = {
    "GD": "Graphic Design",
    "FX": "Visual Effects",
    "VJ": "Live Video",
    "Godot": "Godot",
    "TD": "TouchDesigner",
    "Audio": "Audio",
    "Physical": "3D Print",
    "Photo": "Photo",
    "Web": "Web",
}

# Categories that support project creation (not Business/Global)
CREATIVE_CATEGORIES = ["Visual", "RealTime", "Audio", "Physical", "Photo", "Web"]


def get_subtypes_for_category(category: str) -> List[str]:
    """
    Get list of subtypes for a category.

    Args:
        category: Category name (e.g., "Visual", "RealTime")

    Returns:
        List of subtype keys. Empty list if category not found or has no subtypes.
    """
    if category not in CREATOR_REGISTRY:
        return []
    return list(CREATOR_REGISTRY[category].keys())


def get_subtype_display_name(subtype: str) -> str:
    """
    Get human-readable display name for a subtype.

    Args:
        subtype: Subtype key (e.g., "GD", "VFX")

    Returns:
        Display name or the subtype itself if not found.
    """
    return SUBTYPE_DISPLAY_NAMES.get(subtype, subtype)


def has_multiple_subtypes(category: str) -> bool:
    """
    Check if a category has multiple subtypes.

    Args:
        category: Category name

    Returns:
        True if category has more than one subtype.
    """
    subtypes = get_subtypes_for_category(category)
    return len(subtypes) > 1


def get_creator_class(category: str, subtype: str) -> Optional[Callable]:
    """
    Return a callable that instantiates the creator for a category/subtype.

    For subtypes registered in folder_structure_manifest.MANIFEST, this
    returns a partial that injects the manifest into GenericFolderStructureCreator.
    Otherwise it falls back to the legacy per-script class.

    The returned callable has the same calling convention as the old per-script
    class constructors: ``creator(parent, embedded=..., on_project_created=...,
    on_cancel=..., project_db=...)``.
    """
    manifest = _get_manifest(category, subtype)
    if manifest is not None and (category, subtype) in MIGRATED_SUBTYPES:
        try:
            module = importlib.import_module("shared_folder_structure_creator")
            generic = getattr(module, "GenericFolderStructureCreator")
            return partial(generic, manifest=manifest)
        except (ImportError, AttributeError) as e:
            print(f"Failed to import GenericFolderStructureCreator: {e}")
            return None

    if category not in CREATOR_REGISTRY:
        return None
    if subtype not in CREATOR_REGISTRY[category]:
        return None

    info = CREATOR_REGISTRY[category][subtype]
    module_name = info["module"]
    class_name = info["class"]

    try:
        module = importlib.import_module(module_name)
        creator_class = getattr(module, class_name)
        return creator_class
    except (ImportError, AttributeError) as e:
        print(f"Failed to import creator class: {e}")
        return None


def get_creator_info(category: str, subtype: str) -> Optional[Dict[str, Any]]:
    """
    Get the full info dictionary for a creator.

    Args:
        category: Category name
        subtype: Subtype name

    Returns:
        Info dictionary or None if not found.
    """
    if category not in CREATOR_REGISTRY:
        return None
    return CREATOR_REGISTRY[category].get(subtype)


def is_creative_category(category: str) -> bool:
    """
    Check if a category supports project creation.

    Args:
        category: Category name

    Returns:
        True if category is a creative category (not Business/Global).
    """
    return category in CREATIVE_CATEGORIES
