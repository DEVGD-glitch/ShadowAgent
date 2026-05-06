"""
Palette de commandes — VS Code-style command palette accessible via Ctrl+K.

Recherche floue parmi une liste de commandes organisées par catégorie.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QLabel, QWidget, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

from frontends.qt.theme import C


# ── Command definition ────────────────────────────────────────────────────────

class Command:
    """A single command in the palette."""

    def __init__(self, name: str, category: str, shortcut: str = "", action_id: str = ""):
        self.name = name
        self.category = category
        self.shortcut = shortcut
        self.action_id = action_id or name.lower().replace(" ", "_")

    def matches(self, query: str) -> bool:
        """Check if this command matches a fuzzy query."""
        q = query.lower()
        n = self.name.lower()
        # Direct substring match
        if q in n:
            return True
        # Fuzzy match: all query chars must appear in order
        idx = 0
        for ch in q:
            idx = n.find(ch, idx)
            if idx == -1:
                return False
            idx += 1
        return True

    def __repr__(self):
        return f"Command({self.name!r}, {self.category!r})"


# ── Default commands ──────────────────────────────────────────────────────────

def _default_commands() -> list[Command]:
    """Return the default set of commands for GenericAgent."""
    return [
        # Actions
        Command("Nouvelle conversation", "Actions", "Ctrl+N", "new_conversation"),
        Command("Exporter la conversation", "Actions", "", "export_conversation"),
        Command("Effacer la conversation", "Actions", "", "clear_conversation"),
        # Navigation
        Command("Basculer vers Chat", "Navigation", "Ctrl+1", "switch_chat"),
        Command("Basculer vers Historique", "Navigation", "Ctrl+2", "switch_history"),
        Command("Basculer vers SOP", "Navigation", "Ctrl+3", "switch_sop"),
        Command("Basculer vers Paramètres", "Navigation", "Ctrl+4", "switch_settings"),
        # Settings
        Command("Changer de modèle IA", "Paramètres", "", "switch_model"),
        Command("Toggle thème dark/light", "Paramètres", "Ctrl+T", "toggle_theme"),
        Command("Toggle mode autonome", "Paramètres", "", "toggle_autonomous"),
        Command("Ouvrir les paramètres", "Paramètres", "Ctrl+,", "open_settings"),
        # Search
        Command("Rechercher dans l'historique", "Recherche", "Ctrl+H", "search_history"),
    ]


# ── CommandPalette ────────────────────────────────────────────────────────────

class CommandPalette(QDialog):
    """VS Code-style command palette. Ctrl+K to open.

    Fuzzy-searchable list of commands.
    Categories: Actions, Navigation, Paramètres, Recherche
    """

    command_selected = Signal(str)  # emits action_id

    def __init__(self, parent=None, commands: list[Command] | None = None):
        super().__init__(parent)
        self._all_commands = commands or _default_commands()
        self._filtered_commands: list[Command] = list(self._all_commands)

        self.setWindowTitle("Palette de commandes")
        self.setModal(False)  # Non-modal so it doesn't block the main window
        self.setMinimumSize(420, 320)
        self.setMaximumSize(520, 480)

        self._build_ui()

    def _build_ui(self):
        bg = C["bg"]
        border = C["border"]

        self.setStyleSheet(f"""
            QDialog {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
        """)

        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(0)

        # ── Search input ──
        self._input = QLineEdit()
        self._input.setPlaceholderText("Tapez une commande...")
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(32,32,38,0.9);
                color: {C['text']};
                border: none; border-bottom: 1px solid {border};
                border-radius: 8px 8px 0 0;
                padding: 12px 16px; font-size: 14px;
            }}
            QLineEdit::placeholder {{ color: {C['muted']}; }}
        """)
        self._input.textChanged.connect(self._on_text_changed)
        self._input.returnPressed.connect(self._select_current)
        ly.addWidget(self._input)

        # ── Command list ──
        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{
                background: {bg};
                border: none;
                border-radius: 0 0 8px 8px;
                padding: 4px;
                outline: none;
            }}
            QListWidget::item {{
                color: {C['text']};
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 13px;
            }}
            QListWidget::item:selected {{
                background: rgba(124,58,237,0.25);
                color: #c4b5fd;
            }}
            QListWidget::item:hover {{
                background: rgba(63,63,70,0.4);
            }}
        """)
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.itemDoubleClicked.connect(lambda item: self._select_current())
        ly.addWidget(self._list, 1)

        # Populate
        self._populate_list()

    def _populate_list(self):
        """Fill the list widget with current filtered commands."""
        self._list.clear()
        last_category = ""
        for cmd in self._filtered_commands:
            if cmd.category != last_category:
                # Category header
                header = QListWidgetItem(f"  ── {cmd.category} ──")
                header.setFlags(Qt.ItemIsEnabled)  # Not selectable
                header.setForeground(
                    __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(113, 113, 122)
                )
                font = header.font()
                font.setBold(True)
                font.setPointSize(9)
                header.setFont(font)
                self._list.addItem(header)
                last_category = cmd.category

            shortcut_str = f"  [{cmd.shortcut}]" if cmd.shortcut else ""
            item = QListWidgetItem(f"  {cmd.name}{shortcut_str}")
            item.setData(Qt.UserRole, cmd.action_id)
            self._list.addItem(item)

        # Select first selectable item
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.flags() & Qt.ItemIsSelectable:
                self._list.setCurrentRow(i)
                break

    def _on_text_changed(self, text: str):
        """Filter commands based on search text."""
        query = text.strip()
        if not query:
            self._filtered_commands = list(self._all_commands)
        else:
            self._filtered_commands = [c for c in self._all_commands if c.matches(query)]
        self._populate_list()

    def _on_row_changed(self, row: int):
        """Handle row selection change."""
        pass  # Visual feedback is handled by stylesheet

    def _select_current(self):
        """Emit the selected command's action_id and close."""
        item = self._list.currentItem()
        if item and (item.flags() & Qt.ItemIsSelectable):
            action_id = item.data(Qt.UserRole)
            if action_id:
                self.command_selected.emit(action_id)
        self.hide()
        self._input.clear()

    def show_palette(self):
        """Show the palette and focus the search input."""
        self._filtered_commands = list(self._all_commands)
        self._populate_list()
        self._input.clear()
        self.show()
        self.raise_()
        self._input.setFocus()

    def keyPressEvent(self, event):
        """Handle keyboard navigation."""
        key = event.key()
        if key == Qt.Key_Escape:
            self.hide()
            self._input.clear()
            return
        if key == Qt.Key_Up:
            row = self._list.currentRow()
            # Skip category headers
            while row > 0:
                row -= 1
                item = self._list.item(row)
                if item.flags() & Qt.ItemIsSelectable:
                    self._list.setCurrentRow(row)
                    break
            return
        if key == Qt.Key_Down:
            row = self._list.currentRow()
            while row < self._list.count() - 1:
                row += 1
                item = self._list.item(row)
                if item.flags() & Qt.ItemIsSelectable:
                    self._list.setCurrentRow(row)
                    break
            return
        super().keyPressEvent(event)
