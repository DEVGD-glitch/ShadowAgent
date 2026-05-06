"""
Page SOP (Standard Operating Procedures) pour l'interface Qt GenericAgent.

Contient un panneau latéral listant les fichiers Markdown du dossier memory/
et une zone de visualisation qui affiche le contenu rendu en HTML.

Extrait de ChatPanel._build_sop_page (Phase 3).
"""
from __future__ import annotations

import os
import glob
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QSplitter, QListWidget, QListWidgetItem,
    QTextBrowser, QMessageBox,
)
from PySide6.QtCore import Qt, QUrl

from frontends.qt.constants import _SVG_FILE
from frontends.qt.theme import C, SCROLLBAR_STYLE, _MD_CSS, md_css, scrollbar_css, current_theme
from frontends.qt.utils import _md_to_html, _svg_icon
from frontends.qt.widgets import _safe_open_url


class SOPPage(QWidget):
    """
    Widget autonome pour la page de visionneuse SOP.

    Affiche un panneau latéral avec la liste des fichiers Markdown
    disponibles dans le dossier memory/, et une zone de visualisation
    qui rend le contenu sélectionné en HTML.

    Parameters
    ----------
    parent : QWidget | None
        Widget parent (typiquement le ChatPanel).

    Notes
    -----
    Le chemin du dossier memory est calculé relativement au répertoire
    parent du module frontends. Par défaut : ``../../memory/``.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._build_ui()

    # ════════════════════════════════════════════════════════════════════════
    # Construction de l'interface
    # ════════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        """Construit le séparateur avec la liste SOP et la zone de visualisation."""
        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)

        # ── Liste des fichiers SOP ──────────────────────────────────────────
        self._sop_list = QListWidget()
        self._sop_list.setMaximumWidth(175)
        self._sop_list.setStyleSheet(f"""
            QListWidget {{ background: rgba(10,10,14,0.7); border: none;
                border-right: 1px solid {C['border']}; outline: none; }}
            QListWidget::item {{ color: {C['muted']}; padding: 7px 10px;
                border-radius: 4px; margin: 1px 4px; }}
            QListWidget::item:hover {{ background: rgba(55,55,65,0.7); color: {C['text']}; }}
            QListWidget::item:selected {{ background: rgba(124,58,237,0.28); color: white; }}
            {SCROLLBAR_STYLE}
        """)
        self._sop_list.currentItemChanged.connect(self._load_sop)
        splitter.addWidget(self._sop_list)

        # ── Zone de visualisation ───────────────────────────────────────────
        self._sop_viewer = QTextBrowser()
        self._sop_viewer.setOpenExternalLinks(False)
        self._sop_viewer.anchorClicked.connect(_safe_open_url)
        self._sop_viewer.document().setDefaultStyleSheet(_MD_CSS)
        self._sop_viewer.setStyleSheet(f"""
            QTextBrowser {{ background: transparent; color: {C['text']};
                border: none; padding: 10px 14px;
                font-family: "Arial", "Microsoft YaHei", sans-serif;
                font-size: 13px; }}
            {SCROLLBAR_STYLE}
        """)
        splitter.addWidget(self._sop_viewer)
        splitter.setSizes([165, 340])
        ly.addWidget(splitter)

    # ════════════════════════════════════════════════════════════════════════
    # Rafraîchissement de la liste SOP
    # ════════════════════════════════════════════════════════════════════════

    def refresh(self) -> None:
        """
        Recharge la liste des fichiers Markdown du dossier memory/.

        Parcourt le dossier ``memory/`` (relatif au répertoire parent
        du module frontends) et ajoute chaque fichier ``*.md`` à la liste.
        """
        self._sop_list.clear()
        file_icon = _svg_icon("sop_file_item", _SVG_FILE, C["muted"])
        memory_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "memory",
        )
        for path in sorted(glob.glob(os.path.join(memory_dir, "*.md"))):
            name = os.path.basename(path)
            size = os.path.getsize(path)
            it = QListWidgetItem(name)
            it.setIcon(file_icon)
            it.setData(Qt.UserRole, path)
            it.setToolTip(f"{size:,} octets")
            self._sop_list.addItem(it)

    # ════════════════════════════════════════════════════════════════════════
    # Chargement d'un fichier SOP
    # ════════════════════════════════════════════════════════════════════════

    def _load_sop(self, item: Optional[QListWidgetItem]) -> None:
        """
        Charge et affiche le contenu d'un fichier SOP sélectionné.

        Parameters
        ----------
        item : QListWidgetItem | None
            Élément sélectionné dans la liste. Si None, ne fait rien.
        """
        if not item:
            return
        path = item.data(Qt.UserRole)
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._sop_viewer.setHtml(_md_to_html(f.read()))
        except Exception as e:
            self._sop_viewer.setPlainText(f"Échec de lecture : {e}")

    # ════════════════════════════════════════════════════════════════════════
    # Accès interne (pour compatibilité ChatPanel)
    # ════════════════════════════════════════════════════════════════════════

    @property
    def sop_list(self) -> QListWidget:
        """Liste des fichiers SOP."""
        return self._sop_list

    @property
    def sop_viewer(self) -> QTextBrowser:
        """Zone de visualisation du contenu SOP."""
        return self._sop_viewer
