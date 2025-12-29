"""
Shared Project Database Module

Centralized project and client tracking using JSON storage.
Handles project registration, client management, archiving, and path normalization.
"""

import json
import uuid
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import shutil

from shared_logging import get_logger

logger = get_logger(__name__)


def _get_appdata_path() -> Path:
    """Get the appropriate AppData path for the platform."""
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Local" / "PipelineManager"
    else:
        # WSL/Linux: use Windows user profile via /mnt/c
        windows_appdata = Path("/mnt/c/Users")
        if windows_appdata.exists():
            username = os.environ.get("USER", "")
            user_path = windows_appdata / username
            if user_path.exists():
                return user_path / "AppData" / "Local" / "PipelineManager"
        # Fallback to Linux standard location
        return Path.home() / ".local" / "share" / "PipelineManager"


class ProjectDatabase:
    """
    Manages project and client data in JSON format.

    Database schema:
    {
        "version": "1.0.0",
        "clients": [{id, name, first_seen, project_count}],
        "projects": [{id, client_id, client_name, project_name, project_type,
                      date_created, path, base_directory, status, archived_date,
                      archived_from, notes, metadata, created_at, updated_at}],
        "archive_history": [{project_id, action, timestamp, from_path, to_path}]
    }
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the project database.

        Args:
            db_path: Path to database file. If None, uses default location
                    ~/AppData/Local/PipelineManager/project_database.json
        """
        if db_path is None:
            # Default location (handles WSL path translation)
            app_data = _get_appdata_path()
            app_data.mkdir(parents=True, exist_ok=True)
            self.db_path = app_data / "project_database.json"
        else:
            self.db_path = Path(db_path)

        self.data = self._load_or_create()
        logger.info(f"Project database loaded: {self.db_path}")

    def _create_empty_db(self) -> Dict:
        """Create an empty database structure."""
        return {
            "version": "1.0.0",
            "clients": [],
            "projects": [],
            "archive_history": []
        }

    def _validate_schema(self, data: Dict) -> bool:
        """Validate database schema."""
        required_keys = ["version", "clients", "projects", "archive_history"]
        return all(key in data for key in required_keys)

    def _backup_corrupt_db(self):
        """Backup corrupt database file."""
        if self.db_path.exists():
            backup_path = self.db_path.with_suffix('.json.bak')
            shutil.copy2(self.db_path, backup_path)
            logger.warning(f"Backed up corrupt database to: {backup_path}")

    def _load_or_create(self) -> Dict:
        """Load database from file or create new one."""
        try:
            if self.db_path.exists():
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if self._validate_schema(data):
                        return data
                    else:
                        logger.error("Invalid database schema, creating new database")
                        self._backup_corrupt_db()
                        return self._create_empty_db()
            else:
                logger.info("Database file not found, creating new database")
                return self._create_empty_db()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse database JSON: {e}")
            self._backup_corrupt_db()
            return self._create_empty_db()
        except Exception as e:
            logger.error(f"Error loading database: {e}")
            return self._create_empty_db()

    def _save(self):
        """Save database to file."""
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            logger.debug("Database saved successfully")
        except Exception as e:
            logger.error(f"Failed to save database: {e}")
            raise

    # ==================== PATH MANAGEMENT ====================

    def normalize_path(self, path: str) -> str:
        """
        Normalize path to D:\\_work format (Windows style for database storage).

        Converts:
        - WSL paths (/mnt/d/...) to Windows format (D:\\...)
        - I:/ and P:/ drive letters to D:\\_work (since they are mirrors)
        - Forward slashes to backslashes

        Args:
            path: Path to normalize (e.g., "I:/Visual", "/mnt/d/_work/Active/Visual")

        Returns:
            Normalized Windows path (e.g., "D:\\_work\\Active\\Visual")
        """
        if not path:
            return path

        # Handle WSL paths first (e.g., /mnt/d/_work/...)
        if path.startswith('/mnt/'):
            # Extract drive letter and rest of path
            # /mnt/d/_work/... -> D:\_work\...
            parts = path.split('/')
            if len(parts) >= 3:
                drive_letter = parts[2].upper()  # 'd' -> 'D'
                rest_of_path = '\\'.join(parts[3:])  # '_work/...' -> '_work\...'
                path = f'{drive_letter}:\\{rest_of_path}'

        # Normalize slashes
        path = path.replace('/', '\\')

        # Handle I:/ and P:/ drive mappings (mapped network drives)
        if path.upper().startswith('I:\\'):
            path = 'D:\\_work\\Active\\' + path[3:]
        elif path.upper().startswith('P:\\'):
            path = 'D:\\_work\\Active\\' + path[3:]

        return path

    def translate_to_drive_letter(self, path: str, drive: str = "I") -> str:
        """
        Translate D:\\_work path back to drive letter (I: or P:).

        Args:
            path: Normalized path (e.g., "D:\\\_work\\Visual")
            drive: Drive letter to use (I or P)

        Returns:
            Path with drive letter (e.g., "I:\\Visual")
        """
        if not path:
            return path

        path = path.replace('/', '\\')

        if path.upper().startswith('D:\\_WORK\\'):
            return f'{drive}:\\{path[9:]}'

        return path

    # ==================== CLIENT MANAGEMENT ====================

    def get_all_clients(self, exclude_personal: bool = False) -> List[Dict]:
        """
        Get all clients.

        Args:
            exclude_personal: If True, exclude clients named "Personal"

        Returns:
            List of client dictionaries
        """
        clients = self.data.get("clients", [])

        if exclude_personal:
            clients = [c for c in clients if c.get("name", "").lower() != "personal"]

        # Sort by name
        return sorted(clients, key=lambda x: x.get("name", "").lower())

    def add_or_update_client(self, client_name: str, is_personal: bool = False, auto_save: bool = True) -> str:
        """
        Add a new client or update existing client.

        Args:
            client_name: Name of the client
            is_personal: Whether this is a personal project
            auto_save: Whether to save after changes (set False for bulk operations)

        Returns:
            Client ID (uuid)
        """
        # Check if client already exists
        for client in self.data["clients"]:
            if client["name"].lower() == client_name.lower():
                # Update project count
                client["project_count"] = client.get("project_count", 0) + 1
                if auto_save:
                    self._save()
                return client["id"]

        # Create new client
        client_id = str(uuid.uuid4())
        new_client = {
            "id": client_id,
            "name": client_name,
            "first_seen": datetime.now().isoformat(),
            "project_count": 1,
            "is_personal": is_personal
        }

        self.data["clients"].append(new_client)
        if auto_save:
            self._save()

        return client_id

    def get_client_projects(self, client_id: str) -> List[Dict]:
        """
        Get all projects for a specific client.

        Args:
            client_id: Client UUID

        Returns:
            List of project dictionaries
        """
        return [p for p in self.data["projects"] if p.get("client_id") == client_id]

    # ==================== PROJECT MANAGEMENT ====================

    def register_project(self, project_data: Dict, auto_save: bool = True) -> str:
        """
        Register a new project.

        Args:
            project_data: Dictionary with keys:
                - client_name: str
                - project_name: str
                - project_type: str (GD, VFX, Audio, Physical, Godot, TD, Photo)
                - date_created: str (YYYY-MM-DD)
                - path: str
                - base_directory: str
                - status: str (default: "active")
                - notes: str (optional)
                - metadata: dict (optional)
            auto_save: Whether to save after changes (set False for bulk operations)

        Returns:
            Project ID (uuid)
        """
        # Normalize paths
        path = self.normalize_path(project_data.get("path", ""))
        base_dir = self.normalize_path(project_data.get("base_directory", ""))

        # Check if project already exists
        for project in self.data["projects"]:
            if project["path"] == path:
                return project["id"]

        # Add or update client (don't save yet if we're batching)
        client_name = project_data.get("client_name", "")
        is_personal = client_name.lower() == "personal"
        client_id = self.add_or_update_client(client_name, is_personal, auto_save=False)

        # Create new project
        project_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        new_project = {
            "id": project_id,
            "client_id": client_id,
            "client_name": client_name,
            "project_name": project_data.get("project_name", ""),
            "project_type": project_data.get("project_type", ""),
            "date_created": project_data.get("date_created", ""),
            "path": path,
            "base_directory": base_dir,
            "status": project_data.get("status", "active"),
            "archived_date": None,
            "archived_from": None,
            "notes": project_data.get("notes", ""),
            "metadata": project_data.get("metadata", {}),
            "created_at": now,
            "updated_at": now
        }

        self.data["projects"].append(new_project)

        if auto_save:
            self._save()

        return project_id

    def save(self):
        """Public method to manually save the database (for bulk operations)."""
        self._save()

    def get_all_projects(self, status: str = "active") -> List[Dict]:
        """
        Get all projects with specified status.

        Args:
            status: Filter by status ("active", "archived", or "all")

        Returns:
            List of project dictionaries
        """
        projects = self.data.get("projects", [])

        if status == "all":
            return projects
        else:
            return [p for p in projects if p.get("status") == status]

    def get_project_by_id(self, project_id: str) -> Optional[Dict]:
        """
        Get project by ID.

        Args:
            project_id: Project UUID

        Returns:
            Project dictionary or None if not found
        """
        for project in self.data["projects"]:
            if project["id"] == project_id:
                return project
        return None

    def get_project_by_path(self, path: str) -> Optional[Dict]:
        """
        Get project by path.

        Args:
            path: Project path

        Returns:
            Project dictionary or None if not found
        """
        normalized_path = self.normalize_path(path)

        for project in self.data["projects"]:
            if project["path"] == normalized_path:
                return project
        return None

    def update_project_status(self, project_id: str, status: str):
        """
        Update project status.

        Args:
            project_id: Project UUID
            status: New status ("active" or "archived")
        """
        project = self.get_project_by_id(project_id)
        if project:
            project["status"] = status
            project["updated_at"] = datetime.now().isoformat()
            self._save()
            logger.info(f"Updated project status: {project_id} -> {status}")
        else:
            logger.warning(f"Project not found: {project_id}")

    def update_project_notes(self, project_id: str, notes: str):
        """
        Update project notes.

        Args:
            project_id: Project UUID
            notes: New notes text
        """
        project = self.get_project_by_id(project_id)
        if project:
            project["notes"] = notes
            project["updated_at"] = datetime.now().isoformat()
            self._save()
            logger.debug(f"Updated project notes: {project_id}")
        else:
            logger.warning(f"Project not found: {project_id}")

    def search_projects(self, query: str, include_archived: bool = False) -> List[Dict]:
        """
        Search projects by client or project name.

        Args:
            query: Search query (case-insensitive)
            include_archived: Include archived projects in results

        Returns:
            List of matching project dictionaries
        """
        query_lower = query.lower()
        projects = self.data.get("projects", [])

        if not include_archived:
            projects = [p for p in projects if p.get("status") == "active"]

        # Search in client_name and project_name
        results = []
        for project in projects:
            client_name = project.get("client_name", "").lower()
            project_name = project.get("project_name", "").lower()

            if query_lower in client_name or query_lower in project_name:
                results.append(project)

        return results

    # ==================== ARCHIVE OPERATIONS ====================

    def archive_project(self, project_id: str, archive_path: str):
        """
        Mark project as archived and record new path.

        Args:
            project_id: Project UUID
            archive_path: New path in archive
        """
        project = self.get_project_by_id(project_id)
        if not project:
            logger.warning(f"Project not found: {project_id}")
            return

        # Store original path for un-archiving
        original_path = project["path"]

        # Update project
        project["status"] = "archived"
        project["archived_date"] = datetime.now().isoformat()
        project["archived_from"] = original_path
        project["path"] = self.normalize_path(archive_path)
        project["updated_at"] = datetime.now().isoformat()

        # Record in archive history
        self.data["archive_history"].append({
            "project_id": project_id,
            "action": "archived",
            "timestamp": datetime.now().isoformat(),
            "from_path": original_path,
            "to_path": project["path"]
        })

        self._save()
        logger.info(f"Archived project: {project_id}")

    def unarchive_project(self, project_id: str, restored_path: str):
        """
        Mark project as active and record restored path.

        Args:
            project_id: Project UUID
            restored_path: Restored path (typically from archived_from)
        """
        project = self.get_project_by_id(project_id)
        if not project:
            logger.warning(f"Project not found: {project_id}")
            return

        archive_path = project["path"]

        # Update project
        project["status"] = "active"
        project["archived_date"] = None
        project["path"] = self.normalize_path(restored_path)
        project["updated_at"] = datetime.now().isoformat()

        # Record in archive history
        self.data["archive_history"].append({
            "project_id": project_id,
            "action": "unarchived",
            "timestamp": datetime.now().isoformat(),
            "from_path": archive_path,
            "to_path": project["path"]
        })

        self._save()
        logger.info(f"Un-archived project: {project_id}")

    def get_archive_history(self, project_id: Optional[str] = None) -> List[Dict]:
        """
        Get archive history.

        Args:
            project_id: Optional project UUID to filter by

        Returns:
            List of archive history entries
        """
        history = self.data.get("archive_history", [])

        if project_id:
            history = [h for h in history if h.get("project_id") == project_id]

        return history


# Example usage
if __name__ == "__main__":
    # Test the database
    db = ProjectDatabase()

    # Test adding a project
    project_id = db.register_project({
        "client_name": "TestClient",
        "project_name": "TestProject",
        "project_type": "GD",
        "date_created": "2025-12-29",
        "path": "I:/Visual/2025-12-29_TestClient_TestProject",
        "base_directory": "I:/Visual",
        "notes": "Test notes"
    })

    print(f"Created project: {project_id}")
    print(f"All clients: {db.get_all_clients()}")
    print(f"All projects: {db.get_all_projects()}")
