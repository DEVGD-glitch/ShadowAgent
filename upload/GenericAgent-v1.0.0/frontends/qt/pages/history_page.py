"""
Page d'historique pour l'interface Qt GenericAgent.

Contient la liste des sessions passées avec recherche, restauration
et suppression.

Signaux émis :
- restore_session(session_dict)  : L'utilisateur restaure une session
- delete_session(session_id)     : L'utilisateur supprime une session

Extrait de ChatPanel._build_history_page (Phase 3).
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from frontends.qt.theme import C, SCROLLBAR_STYLE
from frontends.qt.utils import _load_history, _save_history, _small_btn_style


class HistoryPage(QWidget):
    """
    Widget autonome pour la page d'historique des sessions.

    Affiche la liste des sessions sauvegardées et permet de les
    restaurer, supprimer ou rechercher.

    Parameters
    ----------
    parent : QWidget | None
        Widget parent (typiquement le ChatPanel).

    Signaux
    -------
    restore_session : Signal(dict)
        Émis quand l'utilisateur restaure une session. Argument : dictionnaire session.
    delete_session : Signal(str)
        Émis quand l'utilisateur supprime une session. Argument : identifiant de session.
    """

    # ── Signaux ─────────────────────────────────────────────────────────────
    restore_session = Signal(dict)     # session_dict
    delete_session = Signal(str)       # session_id

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._history: list[dict] = []
        self._build_ui()

    # ════════════════════════════════════════════════════════════════════════
    # Construction de l'interface
    # ════════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        """Construit la liste d'historique avec en-tête et boutons d'action."""
        ly = QVBoxLayout(self)
        ly.setContentsMargins(12, 12, 12, 12)
        ly.setSpacing(8)

        # ── En-tête ─────────────────────────────────────────────────────────
        header = QHBoxLayout()
        lbl = QLabel("Historique")
        lbl.setStyleSheet("color: #f4f4f5; font-weight: 600; font-size: 14px;")
        header.addWidget(lbl)
        header.addStretch()

        # Bouton Restaurer
        restore_btn = QPushButton("Restaurer")
        restore_btn.setStyleSheet(_small_btn_style(C["accent"]))
        restore_btn.clicked.connect(self._on_restore)
        header.addWidget(restore_btn)

        # Bouton Supprimer
        del_btn = QPushButton("Supprimer")
        del_btn.setStyleSheet(_small_btn_style("#dc2626"))
        del_btn.clicked.connect(self._on_delete)
        header.addWidget(del_btn)
        ly.addLayout(header)

        # ── Liste des sessions ──────────────────────────────────────────────
        self._hist_list = QListWidget()
        self._hist_list.setStyleSheet(f"""
            QListWidget {{ background: transparent; border: none; outline: none; }}
            QListWidget::item {{
                background: rgba(35,35,42,0.6); color: {C['text']};
                border: 1px solid {C['border']}; border-radius: 8px;
                padding: 8px 12px; margin: 2px 0;
            }}
            QListWidget::item:hover {{ background: rgba(55,55,65,0.8);
                border-color: rgba(124,58,237,0.4); }}
            QListWidget::item:selected {{ background: rgba(124,58,237,0.25);
                border-color: rgba(124,58,237,0.6); }}
            {SCROLLBAR_STYLE}
        """)
        self._hist_list.itemDoubleClicked.connect(self._on_restore)
        ly.addWidget(self._hist_list)

    # ════════════════════════════════════════════════════════════════════════
    # Rafraîchissement de l'historique
    # ════════════════════════════════════════════════════════════════════════

    def refresh(self) -> None:
        """
        Recharge l'historique depuis le fichier et met à jour la liste.

        Charge les 20 dernières sessions et les affiche dans l'ordre
        anti-chronologique.
        """
        self._history = _load_history()
        self._hist_list.clear()
        for s in reversed(self._history[-20:]):
            n = len(s.get("messages", []))
            item = QListWidgetItem(f"  {s.get('title', 'Sans titre')}   ({n} msg)")
            item.setData(Qt.UserRole, s)
            self._hist_list.addItem(item)

    # ════════════════════════════════════════════════════════════════════════
    # Actions utilisateur
    # ════════════════════════════════════════════════════════════════════════

    def _on_restore(self, item: Optional[QListWidgetItem] = None) -> None:
        """
        Émet le signal restore_session avec la session sélectionnée.

        Parameters
        ----------
        item : QListWidgetItem | None
            Élément sélectionné (fourni par le signal itemDoubleClicked).
        """
        item = item or self._hist_list.currentItem()
        if not item:
            return
        s = item.data(Qt.UserRole)
        if s:
            self.restore_session.emit(s)

    def _on_delete(self) -> None:
        """Émet le signal delete_session avec l'identifiant de la session sélectionnée."""
        item = self._hist_list.currentItem()
        if not item:
            return
        s = item.data(Qt.UserRole)
        if s:
            session_id = s.get("id", "")
            # Mettre à jour l'historique local et sauvegarder
            self._history = [h for h in self._history if h.get("id") != session_id]
            _save_history(self._history)
            self.delete_session.emit(session_id)
            self.refresh()

    # ════════════════════════════════════════════════════════════════════════
    # Recherche dans l'historique
    # ════════════════════════════════════════════════════════════════════════

    def search(self, keyword: str) -> None:
        """
        Recherche un mot-clé dans les sessions de l'historique.

        Masque les sessions ne contenant pas le mot-clé et surligne
        les sessions correspondantes.

        Parameters
        ----------
        keyword : str
            Mot-clé à rechercher dans le contenu des messages.
        """
        kw_lower = keyword.lower()
        for i in range(self._hist_list.count()):
            item = self._hist_list.item(i)
            session = item.data(Qt.UserRole)
            messages = session.get("messages", []) if session else []
            content_text = " ".join(
                m.get("content", "") for m in messages
                if isinstance(m.get("content"), str)
            )
            match = kw_lower in content_text.lower()
            item.setHidden(not match)
            if match:
                item.setBackground(QColor(251, 191, 36, 50))
                item.setForeground(QColor(251, 191, 36))
            else:
                item.setBackground(QColor(0, 0, 0, 0))
                item.setForeground(QColor(255, 255, 255))

    def reset_search_style(self) -> None:
        """Réinitialise le style de tous les éléments de la liste d'historique."""
        for i in range(self._hist_list.count()):
            item = self._hist_list.item(i)
            item.setHidden(False)
            item.setBackground(QColor(0, 0, 0, 0))
            item.setForeground(QColor(255, 255, 255))
            w = self._hist_list.itemWidget(item)
            if w:
                w.setStyleSheet(
                    f"background: rgba(35,35,42,0.6); color: {C['text']};"
                    " border: 1px solid #3f3f46; border-radius: 8px;"
                    " padding: 8px 12px; margin: 2px 0;"
                )

    # ════════════════════════════════════════════════════════════════════════
    # Accès interne (pour compatibilité ChatPanel)
    # ════════════════════════════════════════════════════════════════════════

    @property
    def hist_list(self) -> QListWidget:
        """Liste des sessions de l'historique."""
        return self._hist_list

    @property
    def history(self) -> list[dict]:
        """Liste interne des sessions chargées."""
        return self._history

    @history.setter
    def history(self, value: list[dict]) -> None:
        self._history = value
