# Pipeline-Manager

A professional pipeline management system for creative and business workflows with GUI.

## Overview

The Pipeline-Manager is a toolkit designed to streamline various creative and business processes. It provides an intuitive interface for managing projects across multiple domains including audio production, visual design, web development, photography, and business operations.

### Key Features

- **Professional GUI Interface** - Dark-themed interface built with tkinter
- **Multi-Domain Support** - Handles audio, visual, web, photography, and business workflows
- **Automated Folder Structures** - Create standardized project folders for each domain
- **Backup & Sync Tools** - Automated backup and synchronization utilities
- **Extensible Architecture** - Modular design for easy additions and customizations

## Screenshots

![Pipeline Manager Interface](docs/screenshot-2025-10-28.png)
## Requirements

### System Requirements
- **Python**: 3.8 or higher
- **Operating System**: Windows, macOS, or Linux
- **Dependencies**: See `requirements.txt`

### Python Dependencies
- `pillow>=10.0.0` - Image processing and logo display
- `pyexiv2>=2.8.0` - EXIF metadata handling for images
- `tkinter` - GUI framework (included with Python)

## Installation

### Quick Start

1. **Clone or download this repository**
   ```bash
   cd /path/to/floriandheer
   ```

2. **Install dependencies**

   **Option A: Automatic installation (recommended)**
   ```bash
   python install_dependencies.py
   ```

   **Option B: Manual installation**
   ```bash
   pip install -r requirements.txt
   ```


## Usage

### Launching the Pipeline Manager

**Method 1: Python script**
```bash
python floriandheer_pipeline.py
```

**Method 2: VBS Launcher (Windows only)**
- Double-click `floriandheer_pipeline_launcher.vbs`
- This method hides the console window for a cleaner experience

### Creating a Taskbar Shortcut (Windows)

To pin a VBS launcher shortcut to your Windows taskbar:

1. Create a shortcut to the VBS file
2. Right-click the shortcut and select **Properties**
3. In the **Target** field, add `explorer` before the path:
   ```
   explorer C:\path\to\floriandheer_pipeline_launcher.vbs
   ```
4. Click **OK** to save
5. Right-click the shortcut and select **Pin to taskbar**
6. After pinning, right-click the taskbar icon → **Properties** to change the icon back to your preferred icon

**Example:** `explorer C:\iTunes.VBS`

**Note:** You'll need to reapply the custom icon after adding the `explorer` prefix, as Windows may reset it.

### Available Pipeline Scripts

The Pipeline Manager includes 14+ specialized scripts organized by category:

#### 🎵 Audio Production
- **New DJ Project** - Create standardized DJ project structure
- **Backup MusicBee to OneDrive** - Incremental backup of MusicBee library
- **Sync iTunes Playlists to DJ Library** - Synchronize playlists with WAV conversion

#### 📸 Photography
- **New Photo Project** - Create standardized photography project folders

#### 🎨 Visual Design
- **New CG Project** - Computer graphics project structure
- **New GD Project** - Graphic design project structure
- [**Add Text to Image Metadata**](README_ADD_TEXT_TO_IMAGE_METADATA.md) - Embed text descriptions in image EXIF data

#### 🌐 Web Development
- **New Web Project** - Standardized web development structure
- **Backup Laragon** - Backup local web development environment

#### 🖨️ 3D Printing
- **New 3D Printing Project** - Organize 3D printing files and iterations
- [**WooCommerce Order Monitor**](README_ORDER_MONITOR.md) - Monitor WooCommerce orders and organize folders with packing slips, labels, invoices and details

#### 📊 Business & Bookkeeping
- **Create Bookkeeping Folder Structure** - Financial organization structure
- **Invoice Renamer** - Automatically rename and organize invoices

#### 🔧 Global Utilities
- **Cleanup Tool** - System-wide cleanup and maintenance utilities

## Project Structure

```
floriandheer/
├── README.md                              # Main documentation
├── LICENSE                                # License information
├── CHANGELOG.md                           # Version history
├── requirements.txt                       # Python dependencies
├── .gitignore                            # Git ignore patterns
│
├── floriandheer_pipeline.py              # Main application launcher
├── install_dependencies.py                # Dependency installer
├── floriandheer_pipeline_launcher.vbs    # Windows silent launcher
│
├── assets/                                # Images and icons
│   ├── Logo_FlorianDheer_LogoWhite.png
│   └── Favicon_FlorianDheer_WebWhite.ico
│
├── modules/                               # Pipeline script modules
│   ├── PipelineScript_Audio_*.py
│   ├── PipelineScript_Photo_*.py
│   ├── PipelineScript_Visual_*.py
│   ├── PipelineScript_Web_*.py
│   ├── PipelineScript_Physical_*.py
│   ├── PipelineScript_Bookkeeping_*.py
│   └── PipelineScript_Global_*.py
│
├── docs/                                  # Documentation
│   ├── INSTALLATION.md                   # Installation guide
│   ├── CONFIGURATION.md                  # Configuration guide
│   └── CONTRIBUTING.md                   # Contribution guidelines
│
├── config/                                # Configuration files
│   └── README.md                         # Config documentation
│
└── tests/                                 # Test files
    └── README.md                         # Testing documentation
```

## Configuration

### Customizing Base Paths

Edit the category definitions in `floriandheer_pipeline.py` to customize base folder paths:

```python
CREATIVE_CATEGORIES = {
    "AUDIO": {
        "folder_path": "I:\\Audio",  # Change to your audio base path
        # ...
    },
    # ...
}
```

### Adding Custom Scripts

1. Create your script in the `modules/` directory
2. Follow the naming convention: `PipelineScript_Category_Name.py`
3. Add the script reference in `floriandheer_pipeline.py` under the appropriate category

## Troubleshooting

### Common Issues

**Issue: "Module not found" errors**
- Solution: Run `python install_dependencies.py` to install missing dependencies

**Issue: pyexiv2 installation fails**
- Solution: pyexiv2 requires system libraries. On Linux: `sudo apt-get install libexiv2-dev`
- On Windows: Download pre-built wheels from PyPI

**Issue: Scripts don't launch**
- Solution: Verify script paths in the main configuration match your system
- Check that base folder paths exist or script can create them


## Contributing

This is a personal pipeline management system, but suggestions and improvements are welcome!

## License

Copyright © 2025 Florian Dheer. All rights reserved.

This is proprietary software for personal use.

## Author

**Florian Dheer**

For questions or support, please refer to the inline documentation or contact the author.

---

*Last updated: 2025-01-27*
