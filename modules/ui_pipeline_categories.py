"""
UI Pipeline Categories - Category definitions and metadata for the Pipeline Manager.
"""

import os
from rak_settings import get_rak_settings

# Base script directory (relative to the main pipeline file)
SCRIPT_FILE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(SCRIPT_FILE_DIR, "modules")

# Application constants
APP_NAME = "Pipeline Manager"
APP_VERSION = "0.5.0"
APP_ICON = None  # Add path to icon file if available

# Logo path
LOGO_PATH = os.path.join(SCRIPT_FILE_DIR, "assets", "Logo_FlorianDheer_LogoWhite.png")

# Default configuration path
DEFAULT_CONFIG_PATH = os.path.join(os.path.expanduser("~"), "AppData", "Local", "PipelineManager", "config.json")


def _work_path(category: str) -> str:
    """Get work path for a category from settings."""
    return get_rak_settings().get_work_path(category)


# Pipeline categories organized by main sections
# Order: Visual, RealTime, Audio, Physical, Photo, Web
CREATIVE_CATEGORIES = {
    "VISUAL": {
        "name": "Visual",
        "description": "Visual effects, graphics and animation tools",
        "icon": "🎬",
        "folder_path": _work_path("Visual"),
        "scripts": {
            "add_txt_to_metadata": {
                "name": "Add Text to Image Metadata",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Visual_AddTxtToMetadata.py"),
                "description": "Add text from matching .txt files to JPEG image metadata",
                "icon": "🏷"
            }
        },
        "subcategories": {
            "GD": {
                "name": "Graphic Design",
                "icon": "🖼️",
                "scripts": {}
            },
            "FX": {
                "name": "Visual Effects",
                "icon": "🎬",
                "scripts": {}
            },
            "VJ": {
                "name": "Live Video",
                "icon": "💫",
                "scripts": {}
            }
        }
    },
    "REALTIME": {
        "name": "RealTime",
        "description": "Real-time processing and performance tools",
        "icon": "⚡",
        "folder_path": _work_path("RealTime"),
        "scripts": {},
        "subcategories": {
            "GODOT": {
                "name": "Godot Engine",
                "icon": "🔵",
                "scripts": {}
            },
            "TD": {
                "name": "TouchDesigner",
                "icon": "🟠",
                "scripts": {}
            }
        }
    },
    "AUDIO": {
        "name": "Audio",
        "description": "Audio processing tools for DJs and producers",
        "icon": "🎵",
        "folder_path": _work_path("Audio"),
        "scripts": {
            "backup_musicbee": {
                "name": "Backup Music to OneDrive",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Audio_Backup.py"),
                "description": "Backup MusicBee library to OneDrive, only transferring changed or new files",
                "icon": "💾"
            }
        },
        "subcategories": {
            "DJ": {
                "name": "DJ Tools",
                "icon": "🎧",
                "scripts": {
                    "sync_playlists": {
                        "name": "Sync Playlists to Traktor",
                        "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Audio_TraktorSync.py"),
                        "description": "Synchronize iTunes playlists to Traktor DJ library with WAV conversion",
                        "icon": "🔄"
                    },
                    "poweramp_sync": {
                        "name": "Sync Playlists to PowerAmp",
                        "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Audio_PowerAmpSync.py"),
                        "description": "Export MusicBee playlists to M3U8 format for PowerAmp on Android",
                        "icon": "📱"
                    }
                }
            },
            "PROD": {
                "name": "Production Tools",
                "icon": "🎛️",
                "scripts": {}
            }
        }
    },
    "PHYSICAL": {
        "name": "Physical",
        "description": "Physical workflow automation",
        "icon": "🔧",
        "folder_path": _work_path("Physical"),
        "scripts": {},
        "subcategories": {
            "3DPRINTING": {
                "name": "3D Printing",
                "icon": "🖨️",
                "scripts": {
                    "woocommerce_monitor": {
                        "name": "WooCommerce Order Monitor",
                        "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Physical_WooCommerceOrderMonitor.py"),
                        "description": "Automatically monitor WooCommerce orders and organize folders with invoices, labels, and details",
                        "icon": "📦"
                    }
                }
            }
        }
    },
    "PHOTO": {
        "name": "Photo",
        "description": "Photography workflow automation",
        "icon": "📷",
        "folder_path": _work_path("Photo"),
        "scripts": {
            "new_collection": {
                "name": "New Photo Collection",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Photo_NewCollection.py"),
                "description": "Create a photo collection folder in E:/_photo with date, location, and activity",
                "icon": "📸"
            },
            "raw_cleanup": {
                "name": "RAW Cleanup",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Photo_RawCleanup.py"),
                "description": "Delete orphaned RAW files that have no matching JPG in the same folder",
                "icon": "🧹"
            }
        },
        "subcategories": {}
    },
    "WEB": {
        "name": "Web",
        "description": "Web development and publishing tools",
        "icon": "🌐",
        "folder_path": _work_path("Web"),
        "scripts": {
            "backup_laragon": {
                "name": "Laragon Workspace Manager",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Web_LaragonWorkspace.py"),
                "description": "Manage Laragon project junctions to work drive",
                "icon": "🔗"
            },
            "publish_static": {
                "name": "Publish Static Site",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Web_PublishStatic.py"),
                "description": "Upload Staatic exports to FTP, sync DokuWiki, and create dated archives",
                "icon": "🚀"
            }
        },
        "subcategories": {}
    }
}

BUSINESS_CATEGORIES = {
    "BUSINESS": {
        "name": "Business",
        "description": "Business and financial management tools",
        "icon": "💼",
        "folder_path": get_rak_settings().get_work_drive() + "\\_LIBRARY",
        "scripts": {
            "bookkeeping_structure": {
                "name": "Create Bookkeeping Folder Structure",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Bookkeeping_FolderStructure.py"),
                "description": "Create folder structure for bookkeeping and financial records",
                "icon": "📋"
            },
            "invoice_renamer": {
                "name": "Invoice Renamer",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Bookkeeping_InvoiceRenamer.py"),
                "description": "Automatically rename invoices to standardized format: FAC_YY-MM-DD_CompanyName",
                "icon": "📄"
            },
            "inside_tracker": {
                "name": "Inside Tracker",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Business_InsideTracker.py"),
                "description": "Monitor and download politician stock trade filings (PTR) from House Clerk",
                "icon": "📊"
            }
        },
        "subcategories": {}
    },
    "GLOBAL": {
        "name": "Global Tools",
        "description": "General-purpose utilities",
        "icon": "🛠️",
        # No folder_path for Global Tools as requested
        "scripts": {
            "global_cleanup": {
                "name": "Global Cleanup",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Global_Cleanup.py"),
                "description": "Clean up temporary files and folders",
                "icon": "🧹"
            },
            "software_sync": {
                "name": "Software Config Sync",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Global_SoftwareSync.py"),
                "description": "Auto-detect software versions, back up/restore configs to NAS, and migrate configs to new versions",
                "icon": "🔄"
            },
            "software_launcher": {
                "name": "Software Launcher",
                "path": os.path.join(SCRIPTS_DIR, "PipelineScript_Global_SoftwareLauncher.py"),
                "description": "Download, update, and launch portable software tools from GitHub releases",
                "icon": "🚀"
            },
            "homebox": {
                "name": "Homebox",
                "url": "http://169.254.132.127:3100/home",
                "description": "Personal inventory management",
                "icon": "📦"
            },
            "inventree": {
                "name": "InvenTree",
                "url": "http://169.254.132.127:8080/web/home",
                "description": "Work inventory management",
                "icon": "🏭"
            }
        },
        "subcategories": {}
    }
}

# Combine all categories
PIPELINE_CATEGORIES = {**CREATIVE_CATEGORIES, **BUSINESS_CATEGORIES}
