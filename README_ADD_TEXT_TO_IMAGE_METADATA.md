# Reference Library: Add Text to Image Metadata

## 🎯 What It Does

**Adds generated metadata from separate text files to image metadata**

This workflow manages reference image collections using broad categories as folders, with detailed information stored in filenames and metadata.

## 🛠️ Tools Used

- [Advanced Renamer](https://www.advancedrenamer.com/) - Batch file renaming
- [Allusion](https://allusion-app.github.io/) - Visual library management
- Python - Automation scripting
- [TagGUI](https://github.com/jhc13/taggui) - AI-powered image captioning

## 📋 Workflow

### Step 1: Rename Files
Use Advanced Renamer to standardize filenames according to the naming convention.

### Step 2: Generate Captions
Use TagGUI to automatically generate captions and save them as separate text files. Each text file is named after the corresponding image it describes.

### Step 3: Add Metadata
Run the Python script to:
- Read the information from each text file
- Add the caption data to the corresponding image's metadata
- Convert all files to `.jpg` format for consistent metadata display

## 📝 File Naming Convention

```
CATEGORY_SUBJECT_inc Nr
```

**Example:** `Landscape_MountainSunset_inc 001.jpg`

## 🏷️ Metadata Structure

The script populates the following EXIF/IPTC fields:

- **Title field**: Contains the generated description/caption
- **Subject field**: Contains the generated description/caption

This ensures the metadata is displayed cleanly across different applications and platforms.

## 💡 Why JPG?

All files are converted to `.jpg` format to ensure metadata consistency and clean display across various image viewing and management tools.
