"""
Page de chat pour l'interface Qt GenericAgent.

Contient la zone d'affichage des messages, la zone de saisie,
la gestion des pièces jointes, le streaming UI et la recherche
dans la conversation courante.

Signaux émis :
- send_message(text, files)  : L'utilisateur envoie un message
- stop_stream()              : L'utilisateur arrête le streaming
- regenerate_response()      : L'utilisateur demande la régénération
- files_dropped(files)       : Des fichiers ont été déposés par drag-and-drop

Extrait de ChatPanel._build_chat_page / _build_input_area (Phase 3).
"""
from __future__ import annotations

import logging
import os
from typing import Optional, Callable

logger = logging.getLogger(__name__)

try:
    from i18n import t
except ImportError:
    def t(key, *args, **kwargs):
        return key

# Maximum size for a single file attachment (10 MB)
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MB

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QTextEdit, QFileDialog, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, QSize, Signal, QMimeData
from PySide6.QtGui import QCursor, QDragEnterEvent, QDropEvent

from frontends.qt.constants import TEXT_FILE_EXTS, _SVG_CLIP, _SVG_STOP, _SVG_SEND
from frontends.qt.theme import C, SCROLLBAR_STYLE, current_theme
from frontends.qt.utils import _svg_icon
from frontends.qt.widgets import (
    _Separator, _MsgRow, _StreamingBadge,
    ToolCallWidget, ThinkingSection,
)
from frontends.qt.error_mapper import map_exception_to_user_message


class ChatPage(QWidget):
    """
    Widget autonome pour la page de chat.

    Gère l'affichage des messages, la saisie utilisateur, les pièces jointes,
    les modes envoi/arrêt du streaming et la recherche dans la conversation.

    Parameters
    ----------
    parent : QWidget | None
        Widget parent (typiquement le ChatPanel).

    Signaux
    -------
    send_message : Signal(str, list)
        Émis quand l'utilisateur envoie un message. Arguments : (texte, fichiers).
    stop_stream : Signal
        Émis quand l'utilisateur clique sur le bouton d'arrêt du streaming.
    regenerate_response : Signal
        Émis quand l'utilisateur demande la régénération de la dernière réponse.
    files_dropped : Signal(list)
        Émis quand des fichiers sont déposés par drag-and-drop.
    """

    # ── Signaux ─────────────────────────────────────────────────────────────
    send_message = Signal(str, list)    # (text: str, files: list[dict])
    stop_stream = Signal()
    regenerate_response = Signal()
    files_dropped = Signal(list)        # (files: list[str]) — list of file paths

    # ── Styles du bouton envoi/arrêt ────────────────────────────────────────
    _SEND_BTN_STYLE: str = """
        QPushButton { background: #e4e4e7; border: none; border-radius: 17px; }
        QPushButton:hover { background: #f4f4f5; }
        QPushButton:pressed { background: #d4d4d8; }
    """
    _STOP_BTN_STYLE: str = """
        QPushButton { background: rgba(239,68,68,0.85); border: none; border-radius: 17px; }
        QPushButton:hover { background: rgba(248,113,113,0.9); }
        QPushButton:pressed { background: rgba(220,38,38,0.9); }
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        # ── État des messages ───────────────────────────────────────────────
        self._user_scrolled_up: bool = False

        # ── État des pièces jointes ─────────────────────────────────────────
        self._pending_files: list[dict] = []  # {'name', 'type', 'raw'}

        # ── État du streaming UI ────────────────────────────────────────────
        self._is_streaming: bool = False
        self._streaming_row: Optional[_MsgRow] = None

        # ── Drag-and-drop ──────────────────────────────────────────────────
        self.setAcceptDrops(True)
        self._drag_overlay: Optional[QWidget] = None

        # ── Construction de l'interface ─────────────────────────────────────
        self._build_ui()

    # ════════════════════════════════════════════════════════════════════════
    # Construction de l'interface
    # ════════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        """Construit la zone de défilement des messages et la zone de saisie."""
        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(0)

        # ── Zone de défilement des messages ─────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }} {SCROLLBAR_STYLE}"
        )

        self._msg_container = QWidget()
        self._msg_container.setStyleSheet("background: transparent;")
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(0, 12, 0, 12)
        self._msg_layout.setSpacing(4)
        self._msg_layout.addStretch()

        self._scroll.setWidget(self._msg_container)
        self._scroll.verticalScrollBar().valueChanged.connect(self._on_scroll)
        ly.addWidget(self._scroll, 1)

        ly.addWidget(_Separator())

        # ── Zone de saisie ──────────────────────────────────────────────────
        ly.addWidget(self._build_input_area())

    def _build_input_area(self) -> QWidget:
        """
        Construit la zone de saisie avec pièces jointes, compteur de caractères
        et bouton envoi/arrêt.

        Returns
        -------
        QWidget
            Le widget conteneur de la zone de saisie.
        """
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent;")
        ly = QVBoxLayout(wrap)
        ly.setContentsMargins(20, 6, 20, 0)
        ly.setSpacing(0)

        # ── Ligne de puces (pièces jointes) ────────────────────────────────
        self._chips_row = QWidget()
        self._chips_row.setStyleSheet("background: transparent;")
        self._chips_ly = QHBoxLayout(self._chips_row)
        self._chips_ly.setContentsMargins(0, 0, 0, 6)
        self._chips_ly.setSpacing(6)
        self._chips_row.hide()
        ly.addWidget(self._chips_row)

        # ── Carte de saisie ─────────────────────────────────────────────────
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget#inputCard {{
                background: rgba(32,32,38,0.85);
                border: 1px solid {C['border']};
                border-radius: 16px;
            }}
            QWidget#inputCard:focus-within {{
                border-color: rgba(124,58,237,0.55);
            }}
        """)
        card.setObjectName("inputCard")
        card_ly = QVBoxLayout(card)
        card_ly.setContentsMargins(14, 10, 10, 10)
        card_ly.setSpacing(6)

        # Champ de texte
        self._input = QTextEdit()
        self._input.setMinimumHeight(48)
        self._input.setMaximumHeight(120)
        self._input.setPlaceholderText(t("qt.input_placeholder"))
        self._input.setStyleSheet(f"""
            QTextEdit {{
                background: transparent; color: {C['text']};
                border: none; padding: 0; font-size: 14px;
                selection-background-color: rgba(124,58,237,0.4);
            }}
        """)
        self._input.textChanged.connect(self._on_text_changed)
        card_ly.addWidget(self._input)

        # Barre inférieure (pièce jointe, compteurs, bouton envoi)
        bottom = QHBoxLayout()
        bottom.setSpacing(6)

        # Bouton pièce jointe
        attach = QPushButton()
        attach.setIcon(_svg_icon("clip", _SVG_CLIP, "#a1a1aa"))
        attach.setIconSize(QSize(17, 17))
        attach_sz = max(30, self.fontMetrics().height() + 10)
        attach.setFixedSize(attach_sz, attach_sz)
        attach.setToolTip(t("qt.file_attach_tooltip"))
        attach.setCursor(QCursor(Qt.PointingHandCursor))
        attach.setStyleSheet("""
            QPushButton { background: transparent; border: none; border-radius: 15px; }
            QPushButton:hover { background: rgba(63,63,70,0.6); }
        """)
        attach.clicked.connect(self._attach_files)
        bottom.addWidget(attach)

        # Compteur de caractères
        self._char_lbl = QLabel("0 / 2000")
        self._char_lbl.setStyleSheet(f"color: {C['muted']}; font-size: 11px;")
        bottom.addWidget(self._char_lbl)

        # Label de tokens
        self._token_lbl = QLabel("")
        self._token_lbl.setStyleSheet(
            f"color: {C['muted']}; font-size: 11px; margin-left: 10px;"
        )
        bottom.addWidget(self._token_lbl)

        bottom.addStretch()

        # Badge de streaming
        self._streaming_badge = _StreamingBadge()
        bottom.addWidget(self._streaming_badge)

        # Bouton envoi / arrêt
        self._send_btn = QPushButton()
        send_btn_sz = max(34, self.fontMetrics().height() + 16)
        self._send_btn.setFixedSize(send_btn_sz, send_btn_sz)
        self._send_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._send_btn.clicked.connect(self._on_send_btn_click)
        self._set_send_mode()
        bottom.addWidget(self._send_btn)

        card_ly.addLayout(bottom)
        ly.addWidget(card)
        return wrap

    # ════════════════════════════════════════════════════════════════════════
    # Gestion des messages
    # ════════════════════════════════════════════════════════════════════════

    def add_msg_row(self, role: str, text: str,
                    on_resend: Optional[Callable[[], None]] = None) -> _MsgRow:
        """
        Ajoute une ligne de message à la zone de chat.

        Parameters
        ----------
        role : str
            Rôle du message ('user' ou 'assistant').
        text : str
            Contenu du message.
        on_resend : Callable | None
            Fonction de rappel pour la régénération (messages assistant uniquement).

        Returns
        -------
        _MsgRow
            Le widget de ligne de message créé.
        """
        # Si on_resend n'est pas fourni, utiliser le signal pour les messages assistant
        if on_resend is None and role != "user":
            on_resend = self.regenerate_response.emit

        row = _MsgRow(text, role, on_resend=on_resend)
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, row)
        self.scroll_bottom()
        return row

    def clear_messages(self) -> None:
        """Supprime toutes les lignes de messages de la zone de chat."""
        while self._msg_layout.count() > 1:
            it = self._msg_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def add_system_notice(self, text: str) -> None:
        """
        Insère un label de notification système (non suivi comme message).

        Parameters
        ----------
        text : str
            Texte de la notification.
        """
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            "QLabel { background: transparent; color: #71717a;"
            " border: none; padding: 6px 20px; font-size: 12px; }"
        )
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, lbl)
        self.scroll_bottom()

    # ════════════════════════════════════════════════════════════════════════
    # Phase 7 — ToolCall & Thinking widgets
    # ════════════════════════════════════════════════════════════════════════

    def add_tool_call(self, tool_name: str, args_summary: str = "",
                      status: str = "pending", result: str = "") -> ToolCallWidget:
        """Ajoute un widget ToolCallWidget à la zone de chat.

        Parameters
        ----------
        tool_name : str
            Nom de l'outil appelé.
        args_summary : str
            Résumé des arguments de l'appel.
        status : str
            Statut de l'appel : 'pending', 'success', ou 'error'.
        result : str
            Résultat de l'appel (markdown).

        Returns
        -------
        ToolCallWidget
            Le widget créé.
        """
        widget = ToolCallWidget(tool_name, args_summary, status, result)
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, widget)
        self.scroll_bottom()
        return widget

    def add_thinking_section(self, content: str = "",
                             duration_seconds: float | None = None) -> ThinkingSection:
        """Ajoute un widget ThinkingSection à la zone de chat.

        Parameters
        ----------
        content : str
            Contenu du raisonnement.
        duration_seconds : float | None
            Durée du raisonnement en secondes (optionnel).

        Returns
        -------
        ThinkingSection
            Le widget créé.
        """
        widget = ThinkingSection(content, duration_seconds)
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, widget)
        self.scroll_bottom()
        return widget

    # ════════════════════════════════════════════════════════════════════════
    # Drag-and-Drop
    # ════════════════════════════════════════════════════════════════════════

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accepte le drag-and-drop de fichiers."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._show_drag_overlay()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        """Maintient l'overlay pendant le déplacement."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        """Retire l'overlay quand le drag quitte la zone."""
        self._hide_drag_overlay()

    def dropEvent(self, event: QDropEvent) -> None:
        """Traite les fichiers déposés par drag-and-drop."""
        self._hide_drag_overlay()
        urls = event.mimeData().urls()
        if not urls:
            event.ignore()
            return

        file_paths = []
        for url in urls:
            path = url.toLocalFile()
            if path and os.path.isfile(path):
                file_paths.append(path)

        if file_paths:
            # Add files as pending attachments
            for path in file_paths:
                name = os.path.basename(path)
                if any(f["name"] == name for f in self._pending_files):
                    continue
                ext = os.path.splitext(path)[1].lower()
                img_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
                mime = (
                    f"image/{ext[1:]}" if ext in img_exts else
                    "text/plain" if ext in TEXT_FILE_EXTS else
                    "application/octet-stream"
                )
                try:
                    file_size = os.path.getsize(path)
                    if file_size > MAX_ATTACHMENT_SIZE:
                        size_mb = file_size / (1024 * 1024)
                        limit_mb = MAX_ATTACHMENT_SIZE / (1024 * 1024)
                        logger.warning(
                            "File '%s' is %.1f MB, exceeds limit of %.0f MB",
                            name, size_mb, limit_mb,
                        )
                        self.add_system_notice(
                            t("qt.file_too_large", name, size_mb, limit_mb)
                        )
                        continue
                    with open(path, "rb") as fh:
                        raw = fh.read()
                    self._pending_files.append({"name": name, "type": mime, "raw": raw})
                except Exception as e:
                    logger.warning("Failed to attach file '%s': %s", name, e)
                    self.add_system_notice(
                        t("qt.file_attach_failed", name, e)
                    )
            self._refresh_chips()
            self.files_dropped.emit(file_paths)
            event.acceptProposedAction()
        else:
            event.ignore()

    def _show_drag_overlay(self) -> None:
        """Affiche un overlay visuel pendant le drag-and-drop."""
        if self._drag_overlay is not None:
            return
        self._drag_overlay = QWidget(self._scroll)
        self._drag_overlay.setStyleSheet(
            "background: rgba(124,58,237,0.08); border: 2px dashed rgba(124,58,237,0.4);"
            " border-radius: 8px;"
        )
        self._drag_overlay.setGeometry(self._scroll.viewport().rect())
        self._drag_overlay.show()

        # Label au centre
        lbl = QLabel(t("qt.file_drop_here"), self._drag_overlay)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            "color: #a78bfa; font-size: 16px; font-weight: 600; background: transparent;"
        )
        lbl.setGeometry(self._drag_overlay.rect())

    def _hide_drag_overlay(self) -> None:
        """Retire l'overlay de drag-and-drop."""
        if self._drag_overlay is not None:
            self._drag_overlay.deleteLater()
            self._drag_overlay = None

    # ════════════════════════════════════════════════════════════════════════
    # Défilement
    # ════════════════════════════════════════════════════════════════════════

    def _on_scroll(self, value: int) -> None:
        """
        Détecte si l'utilisateur a fait défiler vers le haut.

        Parameters
        ----------
        value : int
            Position actuelle de la barre de défilement.
        """
        sb = self._scroll.verticalScrollBar()
        self._user_scrolled_up = value < sb.maximum() - 30

    def scroll_bottom(self) -> None:
        """Fait défiler vers le bas si l'utilisateur n'a pas fait défiler vers le haut."""
        if self._user_scrolled_up:
            return
        QTimer.singleShot(60, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    def _scroll_to_widget(self, w: QWidget, keyword_y: int = 0) -> None:
        """
        Fait défiler jusqu'à un widget spécifique dans la zone de messages.

        Parameters
        ----------
        w : QWidget
            Widget cible à afficher.
        keyword_y : int
            Décalage vertical optionnel pour le mot-clé trouvé.
        """
        self._user_scrolled_up = True
        self._msg_container.layout().activate()

        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

        sb = self._scroll.verticalScrollBar()
        vp_h = self._scroll.viewport().height()
        keyword_screen_y = w.y() + keyword_y
        target = keyword_screen_y - vp_h // 3
        target = max(0, min(target, sb.maximum()))
        sb.setValue(target)
        QApplication.processEvents()
        self._scroll.viewport().repaint()

    # ════════════════════════════════════════════════════════════════════════
    # Zone de saisie
    # ════════════════════════════════════════════════════════════════════════

    def _on_text_changed(self) -> None:
        """Met à jour le compteur de caractères lors de la modification du texte."""
        n = len(self._input.toPlainText())
        self._char_lbl.setText(f"{n} / 2000")

    def get_input_text(self) -> str:
        """
        Retourne le texte actuel de la zone de saisie.

        Returns
        -------
        str
            Texte saisie, sans les espaces de début/fin.
        """
        return self._input.toPlainText().strip()

    def set_input_text(self, text: str) -> None:
        """
        Définit le texte de la zone de saisie.

        Parameters
        ----------
        text : str
            Texte à insérer.
        """
        self._input.setPlainText(text)

    def clear_input(self) -> None:
        """Efface la zone de saisie."""
        self._input.clear()

    def set_input_event_filter(self, filter_obj: object) -> None:
        """
        Installe un filtre d'événements sur la zone de saisie.

        Parameters
        ----------
        filter_obj : object
            Objet filtre d'événements (typiquement le ChatPanel parent).
        """
        self._input.installEventFilter(filter_obj)

    # ════════════════════════════════════════════════════════════════════════
    # Pièces jointes
    # ════════════════════════════════════════════════════════════════════════

    def _attach_files(self) -> None:
        """Ouvre une boîte de dialogue pour sélectionner des fichiers à joindre."""
        paths, _ = QFileDialog.getOpenFileNames(
            self, t("qt.file_select"), "",
            t("qt.file_dialog_filter_all")+";;"
            +t("qt.file_dialog_filter_images")+";;"
            +t("qt.file_dialog_filter_text"),
        )
        for path in paths:
            name = os.path.basename(path)
            if any(f["name"] == name for f in self._pending_files):
                continue
            ext = os.path.splitext(path)[1].lower()
            img_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
            mime = (
                f"image/{ext[1:]}" if ext in img_exts else
                "text/plain" if ext in TEXT_FILE_EXTS else
                "application/octet-stream"
            )
            try:
                file_size = os.path.getsize(path)
                if file_size > MAX_ATTACHMENT_SIZE:
                    size_mb = file_size / (1024 * 1024)
                    limit_mb = MAX_ATTACHMENT_SIZE / (1024 * 1024)
                    logger.warning(
                        "File '%s' is %.1f MB, exceeds limit of %.0f MB",
                        name, size_mb, limit_mb,
                    )
                    self.add_system_notice(
                        t("qt.file_too_large", name, size_mb, limit_mb)
                    )
                    continue
                with open(path, "rb") as fh:
                    raw = fh.read()
                self._pending_files.append({"name": name, "type": mime, "raw": raw})
            except Exception as e:
                logger.warning("Failed to attach file '%s': %s", name, e)
                self.add_system_notice(
                    t("qt.file_attach_failed", name, e)
                )
        self._refresh_chips()

    def _refresh_chips(self) -> None:
        """Met à jour l'affichage des puces de pièces jointes."""
        while self._chips_ly.count():
            item = self._chips_ly.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self._pending_files:
            self._chips_row.hide()
            return
        for f in self._pending_files:
            chip = QLabel(f['name'])
            chip.setStyleSheet(f"""
                QLabel {{ background: rgba(55,55,65,0.7); color: {C['text']};
                    border: 1px solid {C['border']}; border-radius: 6px;
                    padding: 3px 8px; font-size: 11px; }}
            """)
            self._chips_ly.addWidget(chip)
        self._chips_ly.addStretch()
        self._chips_row.show()

    def get_pending_files(self) -> list[dict]:
        """
        Retourne la liste des fichiers en attente.

        Returns
        -------
        list[dict]
            Liste de dictionnaires {'name', 'type', 'raw'}.
        """
        return self._pending_files.copy()

    def clear_pending_files(self) -> None:
        """Supprime tous les fichiers en attente et rafraîchit l'affichage."""
        self._pending_files.clear()
        self._refresh_chips()

    # ════════════════════════════════════════════════════════════════════════
    # Modes envoi / arrêt du streaming
    # ════════════════════════════════════════════════════════════════════════

    def _set_send_mode(self) -> None:
        """Passe le bouton en mode envoi (flèche)."""
        self._is_streaming = False
        self._send_btn.setText("")
        self._send_btn.setIcon(_svg_icon("send_arrow", _SVG_SEND, "#18181b"))
        self._send_btn.setIconSize(QSize(18, 18))
        self._send_btn.setStyleSheet(self._SEND_BTN_STYLE)

    def _set_stop_mode(self) -> None:
        """Passe le bouton en mode arrêt (carré rouge)."""
        self._is_streaming = True
        self._send_btn.setText("")
        self._send_btn.setIcon(_svg_icon("stop_circle", _SVG_STOP, "#ffffff"))
        self._send_btn.setIconSize(QSize(16, 16))
        self._send_btn.setStyleSheet(self._STOP_BTN_STYLE)

    def set_send_mode(self) -> None:
        """API publique : passe le bouton en mode envoi."""
        self._set_send_mode()

    def set_stop_mode(self) -> None:
        """API publique : passe le bouton en mode arrêt."""
        self._set_stop_mode()

    def _on_send_btn_click(self) -> None:
        """Gère le clic sur le bouton envoi/arrêt."""
        if self._is_streaming:
            self.stop_stream.emit()
        else:
            text = self.get_input_text()
            files = self._pending_files.copy()
            if not text and not files:
                return
            # Effacer l'entrée et les pièces jointes avant d'émettre le signal
            self._input.clear()
            self._pending_files.clear()
            self._refresh_chips()
            self.send_message.emit(text, files)

    # ════════════════════════════════════════════════════════════════════════
    # État du streaming
    # ════════════════════════════════════════════════════════════════════════

    @property
    def streaming_row(self) -> Optional[_MsgRow]:
        """Ligne de message en cours de streaming (ou None)."""
        return self._streaming_row

    @streaming_row.setter
    def streaming_row(self, row: Optional[_MsgRow]) -> None:
        self._streaming_row = row

    @property
    def is_streaming(self) -> bool:
        """Indique si un streaming est en cours."""
        return self._is_streaming

    @property
    def user_scrolled_up(self) -> bool:
        """Indique si l'utilisateur a fait défiler vers le haut."""
        return self._user_scrolled_up

    @user_scrolled_up.setter
    def user_scrolled_up(self, value: bool) -> None:
        self._user_scrolled_up = value

    def show_streaming_badge(self) -> None:
        """Affiche le badge de streaming."""
        self._streaming_badge.show()

    def hide_streaming_badge(self) -> None:
        """Cache le badge de streaming."""
        self._streaming_badge.hide()

    def update_token_label(self, text: str) -> None:
        """
        Met à jour le label d'utilisation de tokens.

        Parameters
        ----------
        text : str
            Texte à afficher dans le label de tokens.
        """
        self._token_lbl.setText(text)

    # ════════════════════════════════════════════════════════════════════════
    # Recherche dans la conversation
    # ════════════════════════════════════════════════════════════════════════

    def search_current_chat(self, keyword: str) -> None:
        """
        Recherche un mot-clé dans les messages de la conversation courante
        et surligne les occurrences.

        Parameters
        ----------
        keyword : str
            Mot-clé à rechercher.
        """
        first_found: Optional[_MsgRow] = None
        first_keyword_y: Optional[int] = None
        for i in range(self._msg_layout.count() - 1):
            w = self._msg_layout.itemAt(i).widget()
            if isinstance(w, _MsgRow):
                if keyword.lower() in w._text.lower():
                    kw_y = w.highlight(keyword)
                    if first_found is None:
                        first_found = w
                        first_keyword_y = kw_y
                else:
                    w.clear_highlight()
        # Scroller vers le premier résultat
        if first_found:
            self._scroll_to_widget(first_found, first_keyword_y or 0)

    def clear_all_highlights(self) -> None:
        """Supprime tous les surlignages de recherche dans la conversation."""
        for i in range(self._msg_layout.count() - 1):
            w = self._msg_layout.itemAt(i).widget()
            if isinstance(w, _MsgRow):
                w.clear_highlight()

    # ════════════════════════════════════════════════════════════════════════
    # User-friendly error display
    # ════════════════════════════════════════════════════════════════════════

    def show_user_error(self, exc: Exception) -> None:
        """Display a user-friendly error message using the error mapper.

        Instead of showing raw Python exception text, this method maps
        the exception to a user-friendly title, message, and action.

        Parameters
        ----------
        exc : Exception
            The exception to display.
        """
        info = map_exception_to_user_message(exc)
        title = info.get("title", t("error_mapper.generic_title", "Erreur"))
        message = info.get("message", str(exc))
        action = info.get("action", "OK")

        # Create a styled error notice in the chat
        from PySide6.QtWidgets import QHBoxLayout as _HBL
        th = current_theme()

        error_widget = QWidget()
        error_widget.setStyleSheet(f"""
            QWidget {{
                background: rgba(239,68,68,0.08);
                border: 1px solid rgba(239,68,68,0.3);
                border-left: 3px solid {th.red};
                border-radius: 6px;
            }}
        """)
        err_ly = QVBoxLayout(error_widget)
        err_ly.setContentsMargins(12, 8, 12, 8)
        err_ly.setSpacing(4)

        # Title row with action button
        title_row = _HBL()
        title_row.setSpacing(8)
        title_lbl = QLabel(f"⚠ {title}")
        title_lbl.setStyleSheet(
            f"color: {th.red}; font-size: 13px; font-weight: 700; background: transparent;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()

        action_btn = QPushButton(action)
        action_btn.setCursor(QCursor(Qt.PointingHandCursor))
        action_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(239,68,68,0.15); color: {th.red};
                border: 1px solid rgba(239,68,68,0.3); border-radius: 4px;
                padding: 3px 10px; font-size: 11px; font-weight: 600;
            }}
            QPushButton:hover {{ background: rgba(239,68,68,0.25); }}
        """)
        action_type = info.get("action_type", "dismiss")
        if action_type == "retry":
            action_btn.clicked.connect(lambda: self._on_error_retry(exc))
        elif action_type == "settings":
            action_btn.clicked.connect(self._on_error_open_settings)
        else:
            action_btn.clicked.connect(lambda: error_widget.deleteLater())
        title_row.addWidget(action_btn)
        err_ly.addLayout(title_row)

        # Message
        msg_lbl = QLabel(message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(
            f"color: {th.text_secondary}; font-size: 12px; background: transparent;"
        )
        err_ly.addWidget(msg_lbl)

        self._msg_layout.insertWidget(self._msg_layout.count() - 1, error_widget)
        self.scroll_bottom()

    def _on_error_retry(self, exc: Exception):
        """Handle retry action from error notice."""
        # Emit regenerate signal to retry the last message
        self.regenerate_response.emit()

    def _on_error_open_settings(self):
        """Handle settings action from error notice — switch to settings tab."""
        # Find the ChatPanel parent and switch to settings
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, '_switch_tab'):
                parent._switch_tab(3)  # Settings tab
                break
            parent = parent.parent()

    # ════════════════════════════════════════════════════════════════════════
    # Accès interne (pour compatibilité ChatPanel)
    # ════════════════════════════════════════════════════════════════════════

    @property
    def msg_layout(self) -> QVBoxLayout:
        """Layout des messages (accès pour insertion programmatique)."""
        return self._msg_layout

    @property
    def scroll_area(self) -> QScrollArea:
        """Zone de défilement des messages."""
        return self._scroll
