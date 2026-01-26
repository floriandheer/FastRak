"""
Creator Registry Module

Maps categories to their folder structure creator scripts.
Provides utilities for dynamic loading and subtype discovery.
"""

import importlib
from typing import Dict, List, Optional, Type, Any


# Registry mapping categories to their subtypes and creator modules
CREATOR_REGISTRY: Dict[str, Dict[str, Dict[str, Any]]] = {
    "Visual": {
        "GD": {
            "module": "PipelineScript_Visual_FolderStructure_GD",
            "class": "FolderStructureCreator",
            "display_name": "Graphic Design",
            "icon": "GD",
        },
        "VFX": {
            "module": "PipelineScript_Visual_FolderStructure_VFX",
            "class": "FolderStructureCreator",
            "display_name": "VFX / CG",
            "icon": "VFX",
        },
        "VJ": {
            "module": "PipelineScript_Visual_FolderStructure_VJ",
            "class": "VJFolderStructureCreator",
            "display_name": "VJ / Resolume",
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
    "VFX": "VFX / CG",
    "VJ": "VJ / Resolume",
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


def get_creator_class(category: str, subtype: str) -> Optional[Type]:
    """
    Dynamically import and return the creator class for a category/subtype.

    Args:
        category: Category name (e.g., "Visual")
        subtype: Subtype name (e.g., "GD")

    Returns:
        Creator class or None if not found/failed to import.
    """
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
