#!/usr/bin/env python
"""
Florian Dheer Pipeline - Enhanced Dependency Installer
-----------------------------------------------------
This script installs all required dependencies for both the desktop and web versions
of the Florian Dheer Pipeline application.

Usage:
    python install_dependencies.py [--web-only] [--desktop-only]
"""

import sys
import subprocess
import importlib.util
import os
import time
import argparse
from pathlib import Path

# Core dependencies (always needed)
CORE_PACKAGES = [
    {"name": "Pillow", "pip_name": "pillow>=10.0.0", "description": "Image processing and logo display"}
]

# Desktop-specific dependencies (tkinter app)
# Note: tkinter is included with Python by default
DESKTOP_PACKAGES = []

# Web-specific dependencies (not currently used)
WEB_PACKAGES = []

def is_package_installed(package_name):
    """Check if a Python package is installed"""
    # Handle packages with special characters
    import_name = package_name.lower().replace("-", "_")
    return importlib.util.find_spec(import_name) is not None

def install_package(package_name):
    """Install a package using pip"""
    print(f"Installing {package_name}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install {package_name}. Error: {e}")
        return False

def check_requirements_txt():
    """Check if requirements.txt exists and offer to use it"""
    requirements_path = Path("requirements.txt")
    if requirements_path.exists():
        print(f"Found requirements.txt at: {requirements_path}")
        use_requirements = input("Would you like to install from requirements.txt instead? (y/n): ")
        if use_requirements.lower() in ('y', 'yes'):
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements_path)])
                print("Successfully installed all packages from requirements.txt!")
                return True
            except subprocess.CalledProcessError as e:
                print(f"Failed to install from requirements.txt: {e}")
                print("Falling back to individual package installation...")
                return False
    return False

def main():
    parser = argparse.ArgumentParser(description="Install Florian Dheer Pipeline dependencies")
    parser.add_argument("--web-only", action="store_true", help="Install only web interface dependencies")
    parser.add_argument("--desktop-only", action="store_true", help="Install only desktop application dependencies")
    parser.add_argument("--skip-optional", action="store_true", help="Skip optional packages")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Florian Dheer Pipeline - Enhanced Dependency Installer")
    print("=" * 60)
    print(f"Python version: {sys.version}")
    print(f"Pip executable: {sys.executable} -m pip")
    print("=" * 60)
    
    # Check if we should use requirements.txt
    if not (args.web_only or args.desktop_only) and check_requirements_txt():
        return
    
    # Determine which packages to install
    packages_to_check = CORE_PACKAGES.copy()
    
    if args.web_only:
        packages_to_check.extend(WEB_PACKAGES)
        print("Mode: Web interface only")
    elif args.desktop_only:
        packages_to_check.extend(DESKTOP_PACKAGES)
        print("Mode: Desktop application only")
    else:
        packages_to_check.extend(DESKTOP_PACKAGES)
        packages_to_check.extend(WEB_PACKAGES)
        print("Mode: Full installation (both desktop and web)")
    
    if args.skip_optional:
        packages_to_check = [p for p in packages_to_check if not p.get("optional", False)]
        print("Skipping optional packages")
    
    print("=" * 60)
    
    missing_packages = []
    optional_missing = []
    
    # Check for required packages
    print("Checking for required packages...")
    for package in packages_to_check:
        sys.stdout.write(f"  - {package['name']} ({package['description']}): ")
        
        # Extract package name for import check (remove version constraints)
        import_name = package['pip_name'].split('>=')[0].split('==')[0].split('[')[0]
        
        if is_package_installed(import_name):
            sys.stdout.write("Already installed ✓\n")
        else:
            sys.stdout.write("Missing ✗\n")
            if package.get("optional", False):
                optional_missing.append(package)
            else:
                missing_packages.append(package)
    
    # Handle missing packages
    total_missing = len(missing_packages) + len(optional_missing)
    
    if total_missing == 0:
        print("\nAll required packages are already installed!")
    else:
        print(f"\nFound {total_missing} missing packages:")
        
        if missing_packages:
            print("\nRequired packages:")
            for package in missing_packages:
                print(f"  - {package['name']} ({package['pip_name']})")
        
        if optional_missing:
            print("\nOptional packages:")
            for package in optional_missing:
                print(f"  - {package['name']} ({package['pip_name']}) - {package['description']}")
        
        install_confirmation = input("\nWould you like to install these packages now? (y/n): ")
        
        if install_confirmation.lower() in ('y', 'yes'):
            print("\nInstalling packages...")
            
            all_packages = missing_packages + optional_missing
            failed_packages = []
            
            for package in all_packages:
                success = install_package(package['pip_name'])
                if success:
                    print(f"  - {package['name']} installed successfully ✓")
                else:
                    failed_packages.append(package)
                    status = "(optional - continuing)" if package.get("optional", False) else "(required - may cause issues)"
                    print(f"  - {package['name']} installation failed ✗ {status}")
            
            if failed_packages:
                print(f"\nWarning: {len(failed_packages)} packages failed to install:")
                for package in failed_packages:
                    print(f"  - {package['name']}")
                print("\nThe application may have limited functionality.")
            else:
                print("\nAll packages installed successfully!")
        else:
            print("\nInstallation cancelled by user.")
            if missing_packages:
                print("Warning: Required packages are missing. The application may not function correctly.")
    
    # Provide usage information
    print("\n" + "=" * 60)
    print("USAGE INFORMATION")
    print("=" * 60)
    
    if not args.desktop_only:
        print("To start the web interface:")
        print("  python web_pipeline_server.py")
        print("  Then open: http://127.0.0.1:8000")
        print()
    
    if not args.web_only:
        print("To start the desktop application:")
        print("  python fastrak_hub.py")
        print()
    
    print("Dependency installation complete!")
    
    # Keep console window open on Windows if double-clicked
    if os.name == 'nt' and not sys.stdin.isatty():
        print("\nPress Enter to exit...")
        input()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInstallation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        print("Please try running this script with administrator privileges or manually install the required packages.")
        if os.name == 'nt' and not sys.stdin.isatty():
            print("\nPress Enter to exit...")
            input()
        sys.exit(1)