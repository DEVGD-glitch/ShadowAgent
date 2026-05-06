"""
Page de paramètres pour l'interface Qt GenericAgent.

Contient le panneau de contrôle avec la liste des modèles LLM,
les vérifications de santé, les boutons d'action (réinitialiser,
sauvegarder, effacer) et le mode autonome.

Signaux émis :
- switch_model(idx)       : L'utilisateur change de modèle actif
- reset_prompt()          : L'utilisateur réinitialise le prompt
- save_session()          : L'utilisateur sauvegarde la session
- clear_conversation()    : L'utilisateur efface la conversation
- toggle_autonomous()     : L'utilisateur active/désactive le mode autonome
- trigger_autonomous()    : L'utilisateur déclenche le mode autonome manuellement

Extrait de ChatPanel._build_settings_page (Phase 3).
"""
from __future__ import annotations

import threading
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QGridLayout, QFrame,
)
from PySide6.QtCore import Qt, QTimer, QSize, Signal
from PySide6.QtGui import QCursor, QFont

from frontends.qt.constants import (
    _SVG_RESET, _SVG_SAVE, _SVG_TRASH, _SVG_BOLT, _SVG_PLAY,
)
from frontends.qt.theme import C
from frontends.qt.utils import (
    _svg_icon, _check_backend_health, MODEL_ROW_STYLE, MODEL_ROW_ACTIVE,
)
from frontends.qt.widgets import _action_btn


class SettingsPage(QWidget):
    """
    Widget autonome pour la page de paramètres.

    Gère la liste des modèles LLM, les vérifications de santé des backends,
    les actions de session et le mode autonome.

    Parameters
    ----------
    parent : QWidget | None
        Widget parent (typiquement le ChatPanel).

    Signaux
    -------
    switch_model : Signal(int)
        Émis quand l'utilisateur change de modèle. Argument : index du modèle.
    reset_prompt : Signal
        Émis quand l'utilisateur réinitialise le prompt du modèle courant.
    save_session : Signal
        Émis quand l'utilisateur demande la sauvegarde de la session.
    clear_conversation : Signal
        Émis quand l'utilisateur demande l'effacement de la conversation.
    toggle_autonomous : Signal
        Émis quand l'utilisateur active/désactive le mode autonome.
    trigger_autonomous : Signal
        Émis quand l'utilisateur déclenche manuellement le mode autonome.
    """

    # ── Signaux ─────────────────────────────────────────────────────────────
    switch_model = Signal(int)            # idx
    reset_prompt = Signal()
    save_session = Signal()
    clear_conversation = Signal()
    toggle_autonomous = Signal()
    trigger_autonomous = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        # ── État des modèles ────────────────────────────────────────────────
        self._model_row_widgets: list[dict] = []
        self._health_results: dict[int, bool | None] = {}
        self._health_pending: int = 0
        self._health_poll_timer: Optional[QTimer] = None
        self._current_model_idx: int = 0
        self._model_name: str = "Inconnu"
        self._llmclients: list = []

        # ── État du mode autonome ───────────────────────────────────────────
        self._autonomous_enabled: bool = False

        self._build_ui()

    # ════════════════════════════════════════════════════════════════════════
    # Construction de l'interface
    # ════════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        """Construit le panneau de contrôle avec modèles, actions et mode autonome."""
        ly = QVBoxLayout(self)
        ly.setContentsMargins(16, 16, 16, 16)
        ly.setSpacing(8)

        # ── Titre ───────────────────────────────────────────────────────────
        lbl = QLabel("Panneau de contrôle")
        lbl.setStyleSheet("color: #f4f4f5; font-weight: 600; font-size: 14px;")
        ly.addWidget(lbl)

        # ── Tab widget: Settings + Health ───────────────────────────────────
        self._tab_widget = QTabWidget()
        self._tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #27272a; background: transparent; }
            QTabBar::tab { color: #a1a1aa; padding: 6px 14px; font-size: 12px;
                           border: 1px solid #27272a; border-bottom: none; }
            QTabBar::tab:selected { color: #f4f4f5; background: rgba(63,63,70,0.4); }
        """)

        # ── Settings Tab ────────────────────────────────────────────────────
        settings_tab = QWidget()
        settings_tab.setStyleSheet("background: transparent;")
        sly = QVBoxLayout(settings_tab)
        sly.setContentsMargins(0, 8, 0, 0)
        sly.setSpacing(8)

        # ── Info modèle courant ─────────────────────────────────────────────
        self._model_info = QLabel(
            f"Modèle actuel : {self._model_name} (#{self._current_model_idx})"
        )
        self._model_info.setStyleSheet(f"color: {C['muted']}; font-size: 12px;")
        sly.addWidget(self._model_info)
        sly.addSpacing(4)

        # ── En-tête liste des modèles ──────────────────────────────────────
        model_hdr = QLabel("Liste des modèles")
        model_hdr.setStyleSheet("color: #d4d4d8; font-weight: 600; font-size: 13px;")
        sly.addWidget(model_hdr)

        # ── Conteneur des lignes de modèles ─────────────────────────────────
        self._model_rows_container = QWidget()
        self._model_rows_container.setStyleSheet("background: transparent;")
        self._model_rows_layout = QVBoxLayout(self._model_rows_container)
        self._model_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._model_rows_layout.setSpacing(3)
        sly.addWidget(self._model_rows_container)

        sly.addSpacing(6)

        # ── Boutons d'action ────────────────────────────────────────────────
        action_defs = [
            ("Réinitialiser le prompt", "#059669", self.reset_prompt.emit, _SVG_RESET),
            ("Sauvegarder la session", "#0ea5e9", self.save_session.emit, _SVG_SAVE),
            ("Effacer la conversation", "#78716c", self.clear_conversation.emit, _SVG_TRASH),
        ]
        for lbl_text, color, handler, svg in action_defs:
            b = _action_btn(lbl_text, color, _svg_icon(lbl_text, svg))
            b.clicked.connect(handler)
            sly.addWidget(b)

        sly.addSpacing(10)

        # ── Mode autonome ───────────────────────────────────────────────────
        sep = QLabel("Mode autonome")
        sep.setStyleSheet("color: #f4f4f5; font-weight: 600; font-size: 13px;")
        sly.addWidget(sep)

        self._auto_btn = _action_btn(
            "Activer le mode autonome (inactivité > 30 min)", "#f59e0b",
            _svg_icon("bolt", _SVG_BOLT),
        )
        self._auto_btn.setCheckable(True)
        self._auto_btn.clicked.connect(self._on_toggle_auto)
        sly.addWidget(self._auto_btn)

        trigger_btn = _action_btn(
            "Déclencher maintenant", "#f59e0b",
            _svg_icon("play", _SVG_PLAY),
        )
        trigger_btn.clicked.connect(self.trigger_autonomous.emit)
        sly.addWidget(trigger_btn)
        sly.addStretch()

        self._tab_widget.addTab(settings_tab, "Paramètres")

        # ── Health Tab ──────────────────────────────────────────────────────
        health_tab = QWidget()
        health_tab.setStyleSheet("background: transparent;")
        hly = QVBoxLayout(health_tab)
        hly.setContentsMargins(0, 8, 0, 0)
        hly.setSpacing(6)

        health_title = QLabel("🩺 Santé du système")
        health_title.setStyleSheet("color: #f4f4f5; font-weight: 600; font-size: 14px;")
        hly.addWidget(health_title)

        # Health grid
        grid = QGridLayout()
        grid.setSpacing(8)

        self._health_labels: dict[str, QLabel] = {}
        health_items = [
            ("uptime", "⏱ Uptime", "—"),
            ("llm_calls", "🤖 Appels LLM", "0"),
            ("token_usage", "📊 Tokens utilisés", "0"),
            ("error_count", "❌ Erreurs", "0"),
            ("error_rate", "⚠ Taux d'erreur", "0.0%"),
            ("platform", "💻 Plateforme", "—"),
            ("python_version", "🐍 Python", "—"),
            ("memory_usage", "💾 Mémoire (est.)", "—"),
        ]
        for row, (key, label_text, default) in enumerate(health_items):
            label = QLabel(label_text)
            label.setStyleSheet("color: #a1a1aa; font-size: 12px;")
            value = QLabel(default)
            value.setStyleSheet("color: #f4f4f5; font-size: 12px; font-weight: 600;")
            grid.addWidget(label, row, 0)
            grid.addWidget(value, row, 1)
            self._health_labels[key] = value

        hly.addLayout(grid)

        # Refresh button
        refresh_btn = QPushButton("🔄 Actualiser")
        refresh_btn.setStyleSheet(
            "QPushButton{background:rgba(63,63,70,0.6);color:#a1a1aa;border:none;"
            "border-radius:7px;padding:6px 14px;font-size:12px}"
            "QPushButton:hover{background:rgba(63,63,70,0.9);color:white}"
        )
        refresh_btn.clicked.connect(self._refresh_health)
        hly.addWidget(refresh_btn)

        # Note
        note = QLabel("Toutes les données sont locales — rien n'est envoyé.")
        note.setStyleSheet("color: #71717a; font-size: 11px; font-style: italic;")
        note.setWordWrap(True)
        hly.addWidget(note)
        hly.addStretch()

        self._tab_widget.addTab(health_tab, "Santé")

        ly.addWidget(self._tab_widget)

        # ── Health refresh timer ─────────────────────────────────────────────
        self._health_refresh_timer = QTimer(self)
        self._health_refresh_timer.timeout.connect(self._refresh_health)
        self._health_refresh_timer.start(5000)  # Refresh every 5 seconds

    # ── Health dashboard (Task 9.3.3) ──────────────────────────────────────

    def _refresh_health(self) -> None:
        """Refresh the health dashboard with current metrics."""
        try:
            from agentmain.health_check import get_health_monitor
            monitor = get_health_monitor()
            status = monitor.get_status()

            self._health_labels["uptime"].setText(
                self._format_uptime(status.get("uptime_seconds", 0))
            )
            self._health_labels["llm_calls"].setText(
                str(status.get("llm_calls", 0))
            )
            self._health_labels["token_usage"].setText(
                f"{status.get('token_usage', 0):,}"
            )
            self._health_labels["error_count"].setText(
                str(status.get("error_count", 0))
            )
            self._health_labels["error_rate"].setText(
                f"{status.get('error_rate', 0) * 100:.1f}%"
            )
            self._health_labels["platform"].setText(
                status.get("platform", "—")
            )
            self._health_labels["python_version"].setText(
                status.get("python_version", "—")
            )
        except Exception:
            pass

        # Memory usage estimate
        try:
            import sys
            mem_mb = sys.getsizeof(object())  # rough baseline
            # More useful: get process RSS
            try:
                import resource
                # ru_maxrss is in KB on Linux, bytes on macOS
                rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                if rss > 1024 * 1024:  # macOS (bytes)
                    mem_mb = rss / (1024 * 1024)
                else:  # Linux (KB)
                    mem_mb = rss / 1024
            except (ImportError, AttributeError):
                mem_mb = 0
            self._health_labels["memory_usage"].setText(
                f"~{mem_mb:.0f} Mo" if mem_mb > 0 else "—"
            )
        except Exception:
            self._health_labels["memory_usage"].setText("—")

    @staticmethod
    def _format_uptime(seconds: float) -> str:
        """Format uptime seconds into a human-readable string."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds / 60:.1f} min"
        else:
            return f"{seconds / 3600:.1f}h"

    # ════════════════════════════════════════════════════════════════════════
    # Configuration des modèles
    # ════════════════════════════════════════════════════════════════════════

    def set_model_info(self, model_name: str, model_idx: int,
                       llmclients: list) -> None:
        """
        Configure les informations sur les modèles LLM disponibles.

        Parameters
        ----------
        model_name : str
            Nom du modèle actuellement actif.
        model_idx : int
            Index du modèle actuellement actif.
        llmclients : list
            Liste des clients LLM (objets avec attribut backend).
        """
        self._model_name = model_name
        self._current_model_idx = model_idx
        self._llmclients = llmclients
        self._model_info.setText(
            f"Modèle actuel : {model_name} (#{model_idx})"
        )
        self._build_model_rows()

    def _build_model_rows(self) -> None:
        """
        Construit les lignes de la liste des modèles à partir des clients LLM.

        Chaque ligne contient un indicateur de santé (point coloré) et un
        bouton avec le nom du modèle. Le modèle actif est visuellement
        différencié.
        """
        while self._model_rows_layout.count():
            w = self._model_rows_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._model_row_widgets.clear()

        for idx, tc in enumerate(self._llmclients):
            b = tc.backend
            name = f"{type(b).__name__}/{b.model}"
            is_current = idx == self._current_model_idx

            row = QWidget()
            row.setStyleSheet("background: transparent;")
            rlay = QHBoxLayout(row)
            rlay.setContentsMargins(0, 0, 0, 0)
            rlay.setSpacing(6)

            dot = QLabel("●")
            dot.setFixedWidth(14)
            dot.setAlignment(Qt.AlignCenter)
            dot.setStyleSheet("color: #71717a; font-size: 11px;")
            rlay.addWidget(dot)

            btn = QPushButton(f"  #{idx}  {name}")
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setStyleSheet(MODEL_ROW_ACTIVE if is_current else MODEL_ROW_STYLE)
            btn.clicked.connect(
                lambda checked, i=idx: self._on_switch_model(i)
            )
            rlay.addWidget(btn, 1)

            self._model_rows_layout.addWidget(row)
            self._model_row_widgets.append({"dot": dot, "btn": btn, "idx": idx})

    def _on_switch_model(self, idx: int) -> None:
        """
        Gère le changement de modèle actif.

        Parameters
        ----------
        idx : int
            Index du modèle sélectionné.
        """
        if idx == self._current_model_idx:
            return
        self._current_model_idx = idx
        self.switch_model.emit(idx)

    def update_current_model(self, model_name: str, model_idx: int) -> None:
        """
        Met à jour l'affichage du modèle courant après un changement.

        Parameters
        ----------
        model_name : str
            Nouveau nom du modèle actif.
        model_idx : int
            Nouvel index du modèle actif.
        """
        self._model_name = model_name
        self._current_model_idx = model_idx
        self._model_info.setText(
            f"Modèle actuel : {model_name} (#{model_idx})"
        )
        self.refresh_model_style()

    def refresh_model_style(self) -> None:
        """Met à jour le style des lignes de modèles selon le modèle actif et l'état de santé."""
        for entry in self._model_row_widgets:
            is_current = entry["idx"] == self._current_model_idx
            entry["btn"].setStyleSheet(
                MODEL_ROW_ACTIVE if is_current else MODEL_ROW_STYLE
            )
            status = self._health_results.get(entry["idx"])
            if status is True:
                entry["dot"].setStyleSheet("color: #22c55e; font-size: 11px;")
            elif status is False:
                entry["dot"].setStyleSheet("color: #ef4444; font-size: 11px;")
            else:
                entry["dot"].setStyleSheet("color: #71717a; font-size: 11px;")

    # ════════════════════════════════════════════════════════════════════════
    # Vérifications de santé des backends
    # ════════════════════════════════════════════════════════════════════════

    def start_health_checks(self) -> None:
        """
        Lance les vérifications de santé de tous les backends LLM.

        Chaque vérification s'exécute dans un thread séparé. Un timer
        de 500 ms interroge les résultats jusqu'à ce que toutes les
        vérifications soient terminées.
        """
        self._health_results.clear()
        self._health_pending = 0
        for entry in self._model_row_widgets:
            entry["dot"].setStyleSheet("color: #71717a; font-size: 11px;")
            entry["dot"].setText("◌")
        for idx, tc in enumerate(self._llmclients):
            self._health_pending += 1
            t = threading.Thread(
                target=self._check, args=(idx, tc.backend), daemon=True
            )
            t.start()
        if self._health_poll_timer is None:
            self._health_poll_timer = QTimer(self)
            self._health_poll_timer.timeout.connect(self._poll)
        self._health_poll_timer.start(500)

    def _poll(self) -> None:
        """Interroge l'état des vérifications de santé et met à jour l'interface."""
        self.refresh_model_style()
        if len(self._health_results) >= self._health_pending:
            if self._health_poll_timer:
                self._health_poll_timer.stop()

    def _check(self, idx: int, backend: object) -> None:
        """
        Exécute la vérification de santé d'un backend dans un thread.

        Parameters
        ----------
        idx : int
            Index du backend dans la liste des clients.
        backend : object
            Objet backend avec une méthode ask() et un attribut model.
        """
        self._health_results[idx] = _check_backend_health(backend)

    # ════════════════════════════════════════════════════════════════════════
    # Mode autonome
    # ════════════════════════════════════════════════════════════════════════

    def _on_toggle_auto(self) -> None:
        """Gère le basculement du mode autonome."""
        self._autonomous_enabled = not self._autonomous_enabled
        self._auto_btn.setChecked(self._autonomous_enabled)
        lbl = (
            "Désactiver le mode autonome"
            if self._autonomous_enabled
            else "Activer le mode autonome (inactivité > 30 min)"
        )
        self._auto_btn.setText(lbl)
        self.toggle_autonomous.emit()

    @property
    def autonomous_enabled(self) -> bool:
        """Indique si le mode autonome est activé."""
        return self._autonomous_enabled

    @autonomous_enabled.setter
    def autonomous_enabled(self, value: bool) -> None:
        self._autonomous_enabled = value
        self._auto_btn.setChecked(value)
        lbl = (
            "Désactiver le mode autonome"
            if value
            else "Activer le mode autonome (inactivité > 30 min)"
        )
        self._auto_btn.setText(lbl)

    # ════════════════════════════════════════════════════════════════════════
    # Accès interne (pour compatibilité ChatPanel)
    # ════════════════════════════════════════════════════════════════════════

    @property
    def model_info_label(self) -> QLabel:
        """Label d'information sur le modèle courant."""
        return self._model_info

    @property
    def auto_button(self) -> QPushButton:
        """Bouton de basculement du mode autonome."""
        return self._auto_btn
