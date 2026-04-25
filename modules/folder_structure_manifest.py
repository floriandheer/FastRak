"""
Folder Structure Manifest

Single source of truth for category/subtype folder-structure creators.
Each entry describes what varies between creators; the GenericFolderStructureCreator
handles everything that's the same.

Manifest fields:
    key, category               — identity
    display_name, icon          — UI labels (mirrored into shared_creator_registry)
    title                       — standalone-window title
    tree_template               — filename in templates/ for the folder tree
    folder_prefix               — inserted between date and client/project (e.g. "GD"); None = no prefix
    project_type                — string written to project_db
    autocomplete_category       — category passed to AutocompleteEntry; None disables autocomplete
    work_path_category          — category passed to settings.get_work_path()
    software_defaults_args      — args passed to settings.get_software_defaults() as a tuple
    software_chips              — [(label, defaults_key, fallback_default), ...]
    extra_fields                — list of {kind, name, label, choices, default_key, default_fallback,
                                  metadata_key} dicts for simple combobox/entry rows that don't justify
                                  a full extension class
    supports_personal           — render Personal checkbox + _Personal/ subfolder logic
    supports_sandbox            — render Sandbox checkbox + _Sandbox/ subfolder logic
    creates_specs_file          — write project_specifications.txt after structure creation
    specs_in_library            — place specs file under _LIBRARY/Documents/ (else project root)
    extension                   — dotted import "module:Class" for genuinely divergent forms (Photo, Physical)
"""

# Standard subtypes — covered fully by GenericFolderStructureCreator
MANIFEST = {
    ("Visual", "GD"): {
        "key": "GD",
        "category": "Visual",
        "display_name": "Graphic Design",
        "icon": "GD",
        "title": "Graphic Design Folder Structure",
        "tree_template": "visual_gd_structure.txt",
        "folder_prefix": "GD",
        "project_type": "Visual-Graphic Design",
        "autocomplete_category": "Visual",
        "work_path_category": "Visual",
        "software_defaults_args": ("Visual", "GD"),
        "software_chips": [
            ("Houdini", "houdini", "20.5"),
            ("Blender", "blender", "4.4"),
            ("Fusion", "fusion", "19"),
        ],
        "extra_fields": [],
        "supports_personal": True,
        "supports_sandbox": True,
        "creates_specs_file": True,
        "specs_in_library": True,
        "extension": None,
    },
    ("Visual", "FX"): {
        "key": "FX",
        "category": "Visual",
        "display_name": "Visual Effects",
        "icon": "FX",
        "title": "FX Folder Structure",
        "tree_template": "visual_fx_structure.txt",
        "folder_prefix": "FX",
        "project_type": "Visual-Visual Effects",
        "autocomplete_category": "Visual",
        "work_path_category": "Visual",
        "software_defaults_args": ("Visual", "FX"),
        "software_chips": [
            ("Houdini", "houdini", "20.5"),
            ("Blender", "blender", "4.4"),
            ("Fusion", "fusion", "19"),
        ],
        "extra_fields": [],
        "supports_personal": True,
        "supports_sandbox": True,
        "creates_specs_file": True,
        "specs_in_library": True,
        "extension": None,
    },
    ("Visual", "VJ"): {
        "key": "VJ",
        "category": "Visual",
        "display_name": "Live Video",
        "icon": "VJ",
        "title": "Live Video Folder Structure",
        "tree_template": "visual_vj_structure.txt",
        "folder_prefix": "VJ",
        "project_type": "Visual-Live Video",
        "autocomplete_category": "Visual",
        "work_path_category": "Visual",
        "software_defaults_args": ("Visual", "VJ"),
        "software_chips": [
            ("Resolume", "resolume", "Arena 7"),
            ("After Effects", "after_effects", "2024"),
            ("TouchDesigner", "touchdesigner", ""),
        ],
        "extra_fields": [],
        "supports_personal": True,
        "supports_sandbox": True,
        "creates_specs_file": True,
        "specs_in_library": True,
        "extension": None,
    },
    ("RealTime", "Godot"): {
        "key": "Godot",
        "category": "RealTime",
        "display_name": "Godot",
        "icon": "Godot",
        "title": "Godot Folder Structure",
        "tree_template": "realtime_godot_structure.txt",
        "folder_prefix": "Godot",
        "project_type": "Godot",
        "autocomplete_category": "RealTime",
        "work_path_category": "RealTime",
        "software_defaults_args": ("RealTime", "Godot"),
        "software_chips": [
            ("Godot", "godot", "4.3"),
        ],
        "extra_fields": [
            {
                "kind": "combobox",
                "name": "platform",
                "label": "Platform",
                "choices": ["PC/Desktop", "Mobile", "Web", "Console", "Multi-platform"],
                "default_key": "platform",
                "default_fallback": "PC/Desktop",
                "metadata_key": "platform",
                "width": 12,
            },
            {
                "kind": "combobox",
                "name": "renderer",
                "label": "Renderer",
                "choices": ["Forward+", "Mobile", "Compatibility"],
                "default_key": "renderer",
                "default_fallback": "Forward+",
                "metadata_key": "renderer",
                "width": 12,
            },
        ],
        "supports_personal": True,
        "supports_sandbox": True,
        "creates_specs_file": True,
        "specs_in_library": True,
        "extension": None,
    },
    ("RealTime", "TD"): {
        "key": "TD",
        "category": "RealTime",
        "display_name": "TouchDesigner",
        "icon": "TD",
        "title": "TouchDesigner Folder Structure",
        "tree_template": "realtime_touchdesigner_structure.txt",
        "folder_prefix": "TD",
        "project_type": "TD",
        "autocomplete_category": "RealTime",
        "work_path_category": "RealTime",
        "software_defaults_args": ("RealTime", "TD"),
        "software_chips": [
            ("TouchDesigner", "touchdesigner", "2023.11760"),
            ("Python", "python", "3.11"),
        ],
        "extra_fields": [
            {
                "kind": "combobox",
                "name": "resolution",
                "label": "Resolution",
                "choices": ["1920x1080", "2560x1440", "3840x2160", "1280x720"],
                "default_key": "resolution",
                "default_fallback": "1920x1080",
                "metadata_key": "resolution",
                "width": 12,
            },
        ],
        "supports_personal": True,
        "supports_sandbox": True,
        "creates_specs_file": True,
        "specs_in_library": True,
        "extension": None,
    },
    ("Audio", "Audio"): {
        "key": "Audio",
        "category": "Audio",
        "display_name": "Audio Production",
        "icon": "Audio",
        "title": "Audio Folder Structure",
        "tree_template": "audio_production_structure.txt",
        "folder_prefix": None,
        "project_type": "Audio",
        "autocomplete_category": "Audio",
        "work_path_category": "Audio",
        "software_defaults_args": ("Audio",),
        "software_chips": [
            ("Ableton", "ableton", "12"),
            ("Reaper", "reaper", "7"),
        ],
        "extra_fields": [],
        "supports_personal": True,
        "supports_sandbox": True,
        "creates_specs_file": True,
        "specs_in_library": True,
        "extension": None,
    },
    ("Web", "Web"): {
        "key": "Web",
        "category": "Web",
        "display_name": "Web Development",
        "icon": "Web",
        "title": "Web Folder Structure",
        "tree_template": "web_structure.txt",
        "folder_prefix": None,
        "project_type": "Web",
        "autocomplete_category": "Web",
        "work_path_category": "Web",
        "software_defaults_args": ("Web",),
        "software_chips": [
            ("Wordpress", "wordpress", "6.7"),
            ("Bricks", "bricks", "1.12"),
            ("Vitepress", "vitepress", "1.6"),
            ("Polygonjs", "polygonjs", "1.8"),
        ],
        "extra_fields": [],
        "supports_personal": True,
        "supports_sandbox": True,
        "creates_specs_file": True,
        "specs_in_library": True,
        "extension": None,
    },

    # Outlier subtypes — manifest points at an extension class that overrides
    # form construction, folder naming, and/or metadata
    ("Photo", "Photo"): {
        "key": "Photo",
        "category": "Photo",
        "display_name": "Photography",
        "icon": "Photo",
        "title": "Photo Folder Structure",
        "tree_template": "photo_structure.txt",
        "folder_prefix": None,
        "project_type": "Photo",
        "autocomplete_category": None,
        "work_path_category": "Photo",
        "software_defaults_args": None,
        "software_chips": [],
        "extra_fields": [],
        "supports_personal": True,
        "supports_sandbox": True,
        "creates_specs_file": False,
        "specs_in_library": False,
        "extension": "folder_structure_extensions.photo:PhotoExtension",
    },
    ("Physical", "Physical"): {
        "key": "Physical",
        "category": "Physical",
        "display_name": "3D Print / Physical",
        "icon": "3D",
        "title": "3D Printing Folder Structure",
        "tree_template": "physical_3dprint_structure.txt",
        "folder_prefix": "3DPrint",
        "project_type": "Physical",
        "autocomplete_category": "Physical",
        "work_path_category": "Physical",
        "software_defaults_args": ("Physical",),
        "software_chips": [
            ("Houdini", "houdini", "20.5"),
            ("Blender", "blender", "4.4"),
            ("FreeCAD", "freecad", ""),
            ("Alibre", "alibre", ""),
            ("Affinity", "affinity", ""),
        ],
        "extra_fields": [],
        "supports_personal": False,  # extension provides 3-way radio instead
        "supports_sandbox": False,
        "creates_specs_file": True,
        "specs_in_library": False,  # specs path is conditional on _LIBRARY toggle
        "extension": "folder_structure_extensions.physical:PhysicalExtension",
    },
}


def get_manifest(category, subtype):
    """Return the manifest entry for a (category, subtype), or None if unknown."""
    return MANIFEST.get((category, subtype))


def all_manifests():
    """Iterate (category, subtype, manifest) tuples."""
    for (cat, sub), m in MANIFEST.items():
        yield cat, sub, m
