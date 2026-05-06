"""
Icône de barre système avec notifications et menu contextuel.

Fonctionnalités :
- Notification de fin de tâche
- Notification d'approbation requise
- Menu contextuel : Ouvrir, Nouvelle conversation, Toggle autonome, Quitter
- Icône SVG par défaut embarquée (GenericAgent logo)
"""
from __future__ import annotations

from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtSvg import QSvgRenderer


# ══════════════════════════════════════════════════════════════════════════════
# Default SVG icon — GenericAgent logo embedded in code
# ══════════════════════════════════════════════════════════════════════════════

_DEFAULT_SVG_ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#4f46e5"/>
      <stop offset="100%" style="stop-color:#7c3aed"/>
    </linearGradient>
  </defs>
  <!-- Rounded square background -->
  <rect x="2" y="2" width="60" height="60" rx="14" ry="14" fill="url(#bg)"/>
  <!-- Letter G -->
  <text x="32" y="46" font-family="Arial,Helvetica,sans-serif" font-size="38" font-weight="bold"
        fill="white" text-anchor="middle" dominant-baseline="central">G</text>
  <!-- Small dot (agent indicator) -->
  <circle cx="50" cy="14" r="5" fill="#22c55e"/>
</svg>"""


def _create_default_icon() -> QIcon:
    """Create the default GenericAgent tray icon from the embedded SVG.

    Falls back to a simple colored circle if SVG rendering fails.
    """
    try:
        renderer = QSvgRenderer(_DEFAULT_SVG_ICON.encode("utf-8"))
        if renderer.isValid():
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            return QIcon(pixmap)
    except Exception:
        pass

    # Fallback: simple colored circle
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(124, 58, 237))  # accent purple
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(4, 4, 56, 56)
    painter.setBrush(QColor(255, 255, 255))
    font = painter.font()
    font.setPixelSize(36)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "G")
    painter.end()
    return QIcon(pixmap)


class TrayManager(QObject):
    """System tray icon with notifications and context menu.

    Signals
    -------
    show_panel : Signal
        Emitted when the user clicks "Ouvrir" or double-clicks the tray icon.
    new_conversation : Signal
        Emitted when the user clicks "Nouvelle conversation".
    toggle_autonomous : Signal
        Emitted when the user clicks "Toggle mode autonome".
    quit_app : Signal
        Emitted when the user clicks "Quitter".
    """

    show_panel = Signal()
    new_conversation = Signal()
    toggle_autonomous = Signal()
    quit_app = Signal()

    def __init__(self, app_icon: QIcon | None = None, parent=None):
        super().__init__(parent)
        self._icon = app_icon
        self._tray = QSystemTrayIcon()
        # Always set a visible icon — never show an invisible tray icon
        if app_icon and not app_icon.isNull():
            self._tray.setIcon(app_icon)
        else:
            self._tray.setIcon(_create_default_icon())
        self._tray.setToolTip("GenericAgent")

        self._build_menu()
        self._tray.activated.connect(self._on_activated)

    def _build_menu(self):
        """Build the context menu for the tray icon."""
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background: #14141a;
                color: #e4e4e7;
                border: 1px solid #2d2d32;
                padding: 4px 0;
            }
            QMenu::item {
                padding: 6px 20px 6px 12px;
                font-size: 12px;
            }
            QMenu::item:selected {
                background: rgba(63,63,70,0.6);
            }
            QMenu::separator {
                height: 1px;
                background: #2d2d32;
                margin: 4px 8px;
            }
        """)

        open_action = QAction("Ouvrir", self)
        open_action.triggered.connect(self.show_panel.emit)
        menu.addAction(open_action)

        new_conv_action = QAction("Nouvelle conversation", self)
        new_conv_action.triggered.connect(self.new_conversation.emit)
        menu.addAction(new_conv_action)

        menu.addSeparator()

        toggle_auto_action = QAction("Toggle mode autonome", self)
        toggle_auto_action.triggered.connect(self.toggle_autonomous.emit)
        menu.addAction(toggle_auto_action)

        menu.addSeparator()

        quit_action = QAction("Quitter", self)
        quit_action.triggered.connect(self.quit_app.emit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)

    def _on_activated(self, reason):
        """Handle tray icon activation (double-click, etc.)."""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_panel.emit()

    def show(self):
        """Show the tray icon."""
        self._tray.show()

    def hide(self):
        """Hide the tray icon."""
        self._tray.hide()

    def notify_task_complete(self, title: str = "Tâche terminée",
                             message: str = "L'agent a terminé sa tâche."):
        """Show a task completion notification.

        Parameters
        ----------
        title : str
            Notification title.
        message : str
            Notification body text.
        """
        self._tray.showMessage(title, message, QSystemTrayIcon.Information, 3000)

    def notify_approval_needed(self, title: str = "Approbation requise",
                               message: str = "L'agent demande votre approbation."):
        """Show an approval needed notification.

        Parameters
        ----------
        title : str
            Notification title.
        message : str
            Notification body text.
        """
        self._tray.showMessage(title, message, QSystemTrayIcon.Warning, 5000)

    def set_icon(self, icon: QIcon):
        """Update the tray icon."""
        self._icon = icon
        self._tray.setIcon(icon)

    @property
    def is_visible(self) -> bool:
        """Check if the tray icon is visible."""
        return self._tray.isVisible()
