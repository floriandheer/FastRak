# Installation Guide

## Prerequisites

### Python Installation

1. **Download Python 3.8 or higher** from [python.org](https://www.python.org/downloads/)
2. During installation, **check "Add Python to PATH"**
3. Verify installation:
   ```bash
   python --version
   ```

### System-Specific Requirements

#### Windows
- No additional requirements for basic functionality
- For pyexiv2: May require Visual C++ Redistributable

#### macOS
- Xcode Command Line Tools may be required:
  ```bash
  xcode-select --install
  ```

#### Linux (Ubuntu/Debian)
- Install required system libraries:
  ```bash
  sudo apt-get update
  sudo apt-get install python3-tk python3-pip libexiv2-dev
  ```

## Installation Methods

### Method 1: Automatic Installation (Recommended)

1. **Navigate to the project directory**
   ```bash
   cd /path/to/floriandheer
   ```

2. **Run the installer**
   ```bash
   python install_dependencies.py
   ```

3. **Follow the prompts** - The installer will:
   - Check for existing packages
   - Show which dependencies are missing
   - Ask for confirmation before installing
   - Provide installation status for each package

### Method 2: Manual Installation

1. **Using pip with requirements.txt**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install packages individually** (if needed)
   ```bash
   pip install pillow>=10.0.0
   pip install pyexiv2>=2.8.0
   ```

### Method 3: Virtual Environment (Advanced)

1. **Create a virtual environment**
   ```bash
   python -m venv venv
   ```

2. **Activate the virtual environment**
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## New PC Setup

The `setup_new_pc.py` script automates the one-time provisioning steps for a new workstation.

### What it automates

| Step | Description |
|------|-------------|
| Folder structure | Creates `Active`, `Archive`, and `_PIPELINE` directories with all category/subcategory folders |
| Drive mappings | Runs `subst` to map virtual drive letters (e.g. `I:` -> `D:\_work\Active`) and writes `HKCU\...\Run` registry entries so they persist after reboot |
| Synology Drive | Checks whether the Synology Drive client is installed and running, and verifies expected sync folders are populated |
| Pipeline config | Creates or updates `rak_config.json` with your paths via the existing `RakSettings` class |

### Prerequisites

- **Windows** (native, not WSL) - drive mappings and registry entries require Win32
- **Python 3.8+**
- **Synology Drive Client** installed (for sync checks; download from [synology.com](https://www.synology.com/en-global/dsm/feature/drive))

### Step-by-step

1. **Copy the config template**
   ```bash
   copy setup_config.json.example setup_config.json
   ```

2. **Edit `setup_config.json`** - adjust drive letters, base paths, and Synology sync folders to match your system.

3. **Run the setup script**
   ```bash
   python setup_new_pc.py
   ```
   The script walks through each step, shows what it will do, and asks for confirmation.

4. **Manual steps after running:**
   - Open Synology Drive Client and create sync tasks for each expected folder
   - Reboot and verify that mapped drives (`I:`, `P:`, etc.) are auto-mounted

### CLI flags

| Flag | Description |
|------|-------------|
| `--config PATH` | Path to config file (default: `./setup_config.json`) |
| `--dry-run` | Show what would happen without making any changes |
| `--yes` | Skip all confirmation prompts |
| `--step STEP` | Run only one step: `folders`, `drives`, `synology`, `config`, or `all` |

### How drive mapping works

The script uses the built-in Windows `subst` command to create virtual drive letters that point to real directories. For example:

```
subst I: "D:\_work\Active"
```

To make this survive reboots, the script writes a registry entry under:

```
HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
```

This does **not** require administrator rights (it's per-user, under HKCU) and does not require VisualSubst or any third-party tool.

### Synology Drive

The script **checks** whether Synology Drive is installed, running, and whether expected sync folders exist and are populated. It **cannot** create sync tasks automatically (Synology Drive has no CLI or API for this). Any missing sync tasks are listed as manual action items.

### Re-running the script

The script is idempotent - safe to run multiple times:

- Existing folders are skipped (`os.makedirs(exist_ok=True)`)
- Already-mapped drives are detected via `subst` output
- Registry values are only written when different from expected
- `RakSettings` merges config with defaults
- Synology checks are read-only

## Troubleshooting Installation

### Issue: pyexiv2 installation fails

**On Windows:**
```bash
pip install pyexiv2 --only-binary :all:
```

**On Linux:**
```bash
sudo apt-get install libexiv2-dev libboost-python-dev
pip install pyexiv2
```

**On macOS:**
```bash
brew install exiv2 boost-python3
pip install pyexiv2
```

### Issue: tkinter not found

- **Windows/macOS**: tkinter is included with Python by default
- **Linux**: Install tkinter separately
  ```bash
  sudo apt-get install python3-tk
  ```

### Issue: Permission denied

**On Linux/macOS:**
```bash
pip install --user -r requirements.txt
```

Or use sudo (not recommended):
```bash
sudo pip install -r requirements.txt
```

### Issue: Old pip version

Update pip to the latest version:
```bash
python -m pip install --upgrade pip
```

## Verification

After installation, verify everything is working:

1. **Test the main application**
   ```bash
   python floriandheer_pipeline.py
   ```

2. **Check installed packages**
   ```bash
   pip list | grep -E "(pillow|pyexiv2)"
   ```

3. **Verify Python version**
   ```bash
   python --version
   ```
   Should show Python 3.8.0 or higher

## Next Steps

- See [README.md](../README.md) for usage instructions
- Check [CONFIGURATION.md](CONFIGURATION.md) for customization options
- Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
