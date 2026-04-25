"""
Photo extension for GenericFolderStructureCreator.

Photo projects are named by date/location/activity rather than client/project,
so this extension replaces the primary input row entirely and provides a
custom folder-name builder. There are no software chips and no specs file.
"""

import re
import tkinter as tk

from shared_form_keyboard import (
    create_styled_entry, create_styled_label,
)
from . import FolderStructureExtension


def _sanitize(name):
    """Strip path-illegal characters and collapse whitespace."""
    cleaned = re.sub(r'[<>:"/\\|?*]', '', name)
    cleaned = re.sub(r'[^\w\s\-_.,&()]+', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()


class PhotoExtension(FolderStructureExtension):
    def __init__(self, creator):
        super().__init__(creator)
        self.location_var = None
        self.activity_var = None

    def build_main_inputs(self, parent_frame):
        parent_frame.columnconfigure(1, weight=1)
        parent_frame.columnconfigure(3, weight=1)
        parent_frame.columnconfigure(5, weight=1)

        create_styled_label(parent_frame, "Date:").grid(row=0, column=0, sticky="e", padx=(0, 5))
        date_entry = create_styled_entry(parent_frame, textvariable=self.creator.date_var, width=12)
        date_entry.grid(row=0, column=1, sticky="w", padx=(0, 20))

        create_styled_label(parent_frame, "Location:").grid(row=0, column=2, sticky="e", padx=(0, 5))
        self.location_var = tk.StringVar()
        location_entry = create_styled_entry(parent_frame, textvariable=self.location_var, width=20)
        location_entry.grid(row=0, column=3, sticky="ew", padx=(0, 20))

        create_styled_label(parent_frame, "Activity/People:").grid(row=0, column=4, sticky="e", padx=(0, 5))
        self.activity_var = tk.StringVar()
        activity_entry = create_styled_entry(parent_frame, textvariable=self.activity_var, width=20)
        activity_entry.grid(row=0, column=5, sticky="ew")

        for var in (self.location_var, self.activity_var):
            var.trace_add("write", lambda *a: self.creator.update_preview())

        # Photo doesn't have a project_name in the standard sense; use activity
        # so DB writes still get a useful project name. We synthesize via project
        # data overrides rather than sharing a StringVar.
        return [date_entry, location_entry, activity_entry]

    def build_folder_name(self):
        date = _sanitize(self.creator.date_var.get())
        location = _sanitize(self.location_var.get() if self.location_var else "")
        activity = _sanitize(self.activity_var.get() if self.activity_var else "")
        return f"{date}_{location}_{activity}"

    def validate_inputs(self):
        if not self.creator.date_var.get().strip():
            return "Please enter a date."
        if not self.location_var or not self.location_var.get().strip():
            return "Please enter a location."
        if not self.activity_var or not self.activity_var.get().strip():
            return "Please enter activity & people information."
        return None

    def build_metadata(self):
        return {
            "location": self.location_var.get().strip() if self.location_var else "",
            "activity": self.activity_var.get().strip() if self.activity_var else "",
        }

    def build_project_data_overrides(self):
        is_personal = self.creator.personal_var is not None and self.creator.personal_var.get()
        return {
            "client_name": "Personal" if is_personal else "Photo",
            "project_name": self.activity_var.get().strip() if self.activity_var else "",
        }
