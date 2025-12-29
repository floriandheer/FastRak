"""
Shared Autocomplete Widget Module

Provides a reusable Tkinter Entry widget with dropdown autocomplete functionality.
"""

import tkinter as tk
from tkinter import ttk
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from shared_project_db import ProjectDatabase

from shared_logging import get_logger

logger = get_logger(__name__)


class AutocompleteComboEntry(tk.Frame):
    """
    Entry widget with dropdown autocomplete suggestions and toggle arrow.

    Features:
    - Filters client names as user types (case-insensitive)
    - Shows top 10 matches in dropdown listbox
    - Arrow button to show all clients
    - Arrow keys to navigate dropdown
    - Enter or Click to select
    - Escape to close dropdown
    - Automatically queries ProjectDatabase for client names
    """

    def __init__(self, parent, db: 'ProjectDatabase', exclude_personal: bool = False,
                 textvariable: tk.StringVar = None, width: int = 20, **kwargs):
        """
        Initialize autocomplete entry with dropdown arrow.

        Args:
            parent: Parent widget
            db: ProjectDatabase instance
            exclude_personal: If True, exclude "Personal" from suggestions
            textvariable: StringVar to bind to entry
            width: Entry width in characters
            **kwargs: Additional arguments passed to Frame
        """
        super().__init__(parent, **kwargs)

        self.db = db
        self.exclude_personal = exclude_personal
        self.textvariable = textvariable or tk.StringVar()

        # Create entry and arrow button side by side
        self.entry = ttk.Entry(self, textvariable=self.textvariable, width=width)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Arrow button to toggle dropdown
        self.arrow_btn = tk.Label(self, text="▼", cursor="hand2", padx=5,
                                  relief=tk.FLAT, bg="#e0e0e0")
        self.arrow_btn.pack(side=tk.RIGHT)
        self.arrow_btn.bind('<Button-1>', self._toggle_listbox)

        # Listbox for dropdown (created on demand)
        self.listbox = None
        self.listbox_frame = None
        self.dropdown_visible = False

        # All available client names (loaded from database)
        self.all_clients = []
        self._load_clients()

        # Event bindings on entry
        self.entry.bind('<KeyRelease>', self._on_key_release)
        self.entry.bind('<Down>', self._on_down_arrow)
        self.entry.bind('<Up>', self._on_up_arrow)
        self.entry.bind('<Return>', self._on_return)
        self.entry.bind('<Escape>', self._hide_listbox)
        self.entry.bind('<FocusOut>', self._on_focus_out)

        logger.debug(f"AutocompleteComboEntry initialized with {len(self.all_clients)} clients")

    def get(self):
        """Get current entry value."""
        return self.textvariable.get()

    def delete(self, first, last=None):
        """Delete text from entry."""
        self.entry.delete(first, last)

    def insert(self, index, string):
        """Insert text into entry."""
        self.entry.insert(index, string)

    def focus_set(self):
        """Set focus to entry."""
        self.entry.focus_set()

    def _load_clients(self):
        """Load client names from database."""
        try:
            clients = self.db.get_all_clients(exclude_personal=self.exclude_personal)
            self.all_clients = [c["name"] for c in clients]
            logger.debug(f"Loaded {len(self.all_clients)} clients for autocomplete")
        except Exception as e:
            logger.error(f"Failed to load clients: {e}")
            self.all_clients = []

    def reload_clients(self):
        """Reload client names from database (call after new clients added)."""
        self._load_clients()

    def _get_matches(self, query: str) -> List[str]:
        """
        Get matching client names for query.

        Args:
            query: Search query (case-insensitive)

        Returns:
            List of matching client names (max 10)
        """
        if not query:
            return []

        query_lower = query.lower()

        # Find matches (case-insensitive, starts with or contains)
        starts_with = []
        contains = []

        for client in self.all_clients:
            client_lower = client.lower()
            if client_lower.startswith(query_lower):
                starts_with.append(client)
            elif query_lower in client_lower:
                contains.append(client)

        # Prioritize starts_with matches, then contains
        matches = starts_with + contains

        # Return top 10 unique matches
        return list(dict.fromkeys(matches))[:10]

    def _toggle_listbox(self, event=None):
        """Toggle dropdown listbox visibility (for arrow button)."""
        if self.dropdown_visible:
            self._hide_listbox()
        else:
            # Show all clients when clicking arrow
            self._show_listbox(self.all_clients[:15])  # Show first 15
            self.entry.focus_set()

    def _show_listbox(self, matches: List[str]):
        """
        Show dropdown listbox with matches.

        Args:
            matches: List of matching client names
        """
        if not matches:
            self._hide_listbox()
            return

        # Create listbox if it doesn't exist
        if self.listbox is None:
            self._create_listbox()

        # Update listbox content
        self.listbox.delete(0, tk.END)
        for match in matches:
            self.listbox.insert(tk.END, match)

        # Calculate position relative to toplevel window
        # Use winfo_rootx/y to get screen coordinates, then subtract toplevel position
        toplevel = self.winfo_toplevel()
        entry_x = self.entry.winfo_rootx() - toplevel.winfo_rootx()
        entry_y = self.entry.winfo_rooty() - toplevel.winfo_rooty()
        entry_width = self.winfo_width()
        entry_height = self.entry.winfo_height()

        # Show listbox below the entry
        self.listbox_frame.lift()
        self.listbox_frame.place(
            x=entry_x,
            y=entry_y + entry_height,
            width=entry_width
        )

        self.dropdown_visible = True
        self.arrow_btn.config(text="▲")

        logger.debug(f"Showing {len(matches)} autocomplete suggestions")

    def _hide_listbox(self, event=None):
        """Hide dropdown listbox."""
        if self.listbox_frame:
            self.listbox_frame.place_forget()
        self.dropdown_visible = False
        self.arrow_btn.config(text="▼")

    def _create_listbox(self):
        """Create the dropdown listbox."""
        # Get parent that can handle place geometry
        parent = self.winfo_toplevel()

        # Frame to hold listbox with border
        self.listbox_frame = tk.Frame(parent, relief=tk.SOLID, borderwidth=1)

        # Scrollbar
        scrollbar = ttk.Scrollbar(self.listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Listbox
        self.listbox = tk.Listbox(
            self.listbox_frame,
            height=min(10, 5),  # Show max 10 items, default 5
            yscrollcommand=scrollbar.set,
            exportselection=False
        )
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar.config(command=self.listbox.yview)

        # Listbox event bindings
        self.listbox.bind('<Button-1>', self._on_listbox_click)
        self.listbox.bind('<Return>', self._on_listbox_select)
        self.listbox.bind('<Escape>', self._hide_listbox)

    def _on_key_release(self, event):
        """Handle key release in entry."""
        # Ignore special keys
        if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Escape',
                            'Shift_L', 'Shift_R', 'Control_L', 'Control_R',
                            'Alt_L', 'Alt_R', 'Tab'):
            return

        # Get current text
        text = self.get()

        # Get matches
        matches = self._get_matches(text)

        # Show or hide listbox
        if matches and text:
            self._show_listbox(matches)
        else:
            self._hide_listbox()

    def _on_down_arrow(self, event):
        """Handle down arrow key."""
        if self.listbox and self.listbox.winfo_viewable():
            # Move selection down in listbox
            current = self.listbox.curselection()
            if current:
                index = current[0]
                if index < self.listbox.size() - 1:
                    self.listbox.selection_clear(index)
                    self.listbox.selection_set(index + 1)
                    self.listbox.see(index + 1)
            else:
                # Select first item
                self.listbox.selection_set(0)
                self.listbox.see(0)

            # Prevent default behavior
            return 'break'

    def _on_up_arrow(self, event):
        """Handle up arrow key."""
        if self.listbox and self.listbox.winfo_viewable():
            # Move selection up in listbox
            current = self.listbox.curselection()
            if current:
                index = current[0]
                if index > 0:
                    self.listbox.selection_clear(index)
                    self.listbox.selection_set(index - 1)
                    self.listbox.see(index - 1)

            # Prevent default behavior
            return 'break'

    def _on_return(self, event):
        """Handle Return key in entry."""
        if self.listbox and self.listbox.winfo_viewable():
            # Select from listbox if visible
            self._on_listbox_select()
            return 'break'

    def _on_listbox_click(self, event):
        """Handle click in listbox."""
        # Select item under cursor
        index = self.listbox.nearest(event.y)
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(index)
        self._on_listbox_select()

    def _on_listbox_select(self, event=None):
        """Handle selection from listbox."""
        if not self.listbox:
            return

        selection = self.listbox.curselection()
        if selection:
            # Get selected value
            value = self.listbox.get(selection[0])

            # Update entry
            self.delete(0, tk.END)
            self.insert(0, value)

            # Hide listbox
            self._hide_listbox()

            # Return focus to entry
            self.focus_set()

            logger.debug(f"Selected client: {value}")

    def _on_focus_out(self, event):
        """Handle focus out event."""
        # Hide listbox after a short delay (to allow clicks)
        self.after(200, self._hide_listbox)


# Backward compatibility alias
AutocompleteEntry = AutocompleteComboEntry


# Example usage / test
if __name__ == "__main__":
    from shared_project_db import ProjectDatabase

    # Test window
    root = tk.Tk()
    root.title("Autocomplete Test")
    root.geometry("400x300")

    # Initialize database
    db = ProjectDatabase()

    # Add some test clients
    db.add_or_update_client("Nike")
    db.add_or_update_client("Adidas")
    db.add_or_update_client("Apple")
    db.add_or_update_client("Amazon")
    db.add_or_update_client("Personal")
    db.add_or_update_client("Microsoft")
    db.add_or_update_client("Google")

    # Label
    label = ttk.Label(root, text="Type to search clients (or click ▼ to see all):")
    label.pack(pady=20)

    # Autocomplete entry with arrow
    entry_var = tk.StringVar()
    autocomplete = AutocompleteComboEntry(
        root,
        db=db,
        textvariable=entry_var,
        width=30
    )
    autocomplete.pack(pady=10, padx=50)

    # Result label
    result_label = ttk.Label(root, text="")
    result_label.pack(pady=20)

    def show_result():
        result_label.config(text=f"Selected: {entry_var.get()}")

    # Button
    button = ttk.Button(root, text="Show Selection", command=show_result)
    button.pack(pady=10)

    root.mainloop()
