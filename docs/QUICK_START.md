# Quick Start Guide

Get up and running with the Pipeline Manager in 5 minutes!

## 1. Install Dependencies (2 minutes)

Open a terminal in the project directory and run:

```bash
python install_dependencies.py
```

Press `y` when asked to install packages.

## 2. Launch the Application (1 minute)

**Windows (Easy Way):**
- Double-click `fastrak_launcher.vbs`

**Any Platform:**
```bash
python fastrak_hub.py
```

## 3. Use Your First Script (2 minutes)

1. **Select a category** from the top tabs (Audio, Photo, Visual, Web, etc.)
2. **Click a script** from the left sidebar
3. **Click "Run Script"** at the bottom
4. **Follow the prompts** in the script output area

## Common First Scripts

### Create a New Project Folder

1. Go to the relevant category (Audio DJ, Photo, Visual CG, etc.)
2. Click "New [Category] Project"
3. Choose a location when prompted
4. Enter a project name
5. Done! Your folder structure is created

### Backup MusicBee Library

1. Go to **Audio** tab
2. Click **"Backup MusicBee to OneDrive"**
3. Click **"Run Script"**
4. Wait for the backup to complete

### Rename Invoices

1. Go to **Business** tab
2. Click **"Invoice Renamer"**
3. Click **"Run Script"**
4. Select the folder containing invoices
5. Follow prompts to rename

## Customization

### Change Base Paths

Edit the paths in `fastrak_hub.py`:

```python
"folder_path": "I:\\Audio",  # ← Change to your path
```

See [CONFIGURATION.md](CONFIGURATION.md) for more options.

## Troubleshooting

### Script won't run?
- Check that the path in the script exists
- Verify you have write permissions
- Look at the output area for error messages

### Missing dependencies?
- Re-run: `python install_dependencies.py`
- Check [INSTALLATION.md](INSTALLATION.md)

### Can't find a script?
- Check it's in the correct category tab
- Some scripts are in subcategories (expand the section)

## Next Steps

- Read the full [README.md](../README.md)
- Explore [CONFIGURATION.md](CONFIGURATION.md) for customization
- Check [INSTALLATION.md](INSTALLATION.md) for advanced setup

## Help

All scripts have descriptions. Hover or click to see what they do before running!

---

**That's it! You're ready to use the Pipeline Manager.**
