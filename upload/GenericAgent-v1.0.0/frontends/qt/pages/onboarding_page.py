"""
Onboarding wizard for GenericAgent desktop app.

5-step guided setup:
  1. Welcome
  2. Provider selection
  3. API Key input
  4. Connection test
  5. Ready

On success, stores the API key via credential_store (keyring) and
emits a signal so the main window switches to the chat page.
"""
from __future__ import annotations

import logging
import webbrowser

logger = logging.getLogger(__name__)

try:
    from i18n import t
except ImportError:
    def t(key, *args, **kwargs):
        return key

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QLineEdit, QRadioButton, QButtonGroup,
    QSizePolicy, QSpacerItem,
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QCursor

from frontends.qt.theme import current_theme

# Provider metadata: name, description, API key URL, credential key name
_PROVIDERS = {
    "openai": {
        "label": "OpenAI (GPT-4 / GPT-4o)",
        "desc": t("onboarding.provider_openai_desc", "Modèles GPT puissants par OpenAI"),
        "key_url": "https://platform.openai.com/api-keys",
        "cred_key": "openai_api_key",
    },
    "claude": {
        "label": "Anthropic (Claude)",
        "desc": t("onboarding.provider_claude_desc", "Claude — raisonnement avancé par Anthropic"),
        "key_url": "https://console.anthropic.com/settings/keys",
        "cred_key": "anthropic_api_key",
    },
    "gemini": {
        "label": "Google (Gemini)",
        "desc": t("onboarding.provider_gemini_desc", "Gemini — modèles multimodaux par Google"),
        "key_url": "https://aistudio.google.com/app/apikey",
        "cred_key": "google_api_key",
    },
    "ollama": {
        "label": "Ollama (local)",
        "desc": t("onboarding.provider_ollama_desc", "Exécution locale, aucune clé API nécessaire"),
        "key_url": "",
        "cred_key": "ollama_url",
    },
}


class _ConnectionTestWorker(QThread):
    """Background thread to test an LLM connection with a simple call."""

    success = Signal(str)   # emits response text
    error = Signal(str)     # emits error message

    def __init__(self, provider: str, api_key: str, parent=None):
        super().__init__(parent)
        self._provider = provider
        self._api_key = api_key

    def run(self):
        try:
            if self._provider == "ollama":
                # For Ollama, just try to reach the local server
                import urllib.request
                import urllib.error
                try:
                    req = urllib.request.Request(
                        "http://localhost:11434/api/tags",
                        headers={"Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        if resp.status == 200:
                            self.success.emit("Ollama local détecté !")
                            return
                except Exception:
                    self.error.emit(t("onboarding.ollama_not_found",
                                      "Ollama n'est pas détecté. Assurez-vous qu'il est en cours d'exécution."))
                    return

            # For cloud providers, try a minimal LLM call
            try:
                from llmcore.clients import create_client
            except ImportError:
                # Fallback: just validate key format
                if len(self._api_key) < 10:
                    self.error.emit(t("onboarding.key_too_short",
                                      "La clé API semble trop courte. Vérifiez votre clé."))
                    return
                self.success.emit(t("onboarding.key_format_ok",
                                    "Format de clé valide (connexion non vérifiée)."))
                return

            try:
                client = create_client(self._provider, self._api_key)
                # Make a minimal test call
                if hasattr(client, 'chat'):
                    response = client.chat([{"role": "user", "content": "Hi"}],
                                           max_tokens=5, temperature=0)
                    self.success.emit(t("onboarding.connection_ok",
                                        "Connexion réussie !"))
                else:
                    self.success.emit(t("onboarding.key_format_ok",
                                        "Format de clé valide."))
            except Exception as exc:
                err_msg = str(exc)
                if "auth" in err_msg.lower() or "401" in err_msg or "invalid" in err_msg.lower():
                    self.error.emit(t("onboarding.auth_failed",
                                      "Clé API invalide. Vérifiez votre clé."))
                elif "rate" in err_msg.lower() or "429" in err_msg:
                    self.success.emit(t("onboarding.connection_ok_limited",
                                        "Clé valide (rate-limit atteint)."))
                else:
                    self.error.emit(t("onboarding.connection_error",
                                      f"Erreur de connexion : {err_msg[:100]}"))
        except Exception as exc:
            self.error.emit(t("onboarding.test_error",
                              f"Erreur lors du test : {str(exc)[:100]}"))


class OnboardingWizard(QWidget):
    """Multi-step onboarding wizard for first-time setup.

    Steps:
      0 - Welcome
      1 - Provider selection
      2 - API Key input
      3 - Connection test
      4 - Ready

    Signals
    -------
    onboarding_complete : Signal(str, str)
        Emitted with (provider, api_key) when the wizard finishes.
    """

    onboarding_complete = Signal(str, str)  # (provider, api_key)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_step = 0
        self._selected_provider = "openai"
        self._api_key = ""
        self._test_worker = None

        self.setStyleSheet("background: transparent;")
        self._build_ui()
        self._apply_step_style()

    # ── Build ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(40, 30, 40, 30)
        self._outer.setSpacing(0)

        # Step indicator
        self._step_label = QLabel("")
        self._step_label.setAlignment(Qt.AlignCenter)
        self._step_label.setStyleSheet("font-size: 12px; font-weight: 600; background: transparent;")
        self._outer.addWidget(self._step_label)
        self._outer.addSpacing(16)

        # Stack
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        self._outer.addWidget(self._stack, 1)

        # Build each step
        self._stack.addWidget(self._build_welcome_step())
        self._stack.addWidget(self._build_provider_step())
        self._stack.addWidget(self._build_apikey_step())
        self._stack.addWidget(self._build_test_step())
        self._stack.addWidget(self._build_ready_step())

        self._outer.addSpacing(20)

        # Navigation buttons
        nav = QHBoxLayout()
        nav.setSpacing(12)
        nav.addStretch()

        self._back_btn = QPushButton(t("onboarding.back", "Retour"))
        self._back_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._back_btn.clicked.connect(self._go_back)
        nav.addWidget(self._back_btn)

        self._next_btn = QPushButton(t("onboarding.next", "Suivant"))
        self._next_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._next_btn.clicked.connect(self._go_next)
        nav.addWidget(self._next_btn)

        self._outer.addLayout(nav)

        self._update_step_ui()

    # ── Step 0: Welcome ──────────────────────────────────────────────────
    def _build_welcome_step(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        ly = QVBoxLayout(w)
        ly.setAlignment(Qt.AlignCenter)
        ly.setSpacing(16)

        # Logo/icon placeholder
        icon = QLabel("🤖")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 64px; background: transparent;")
        ly.addWidget(icon)

        title = QLabel(t("onboarding.welcome_title", "Bienvenue sur GenericAgent"))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: 700; background: transparent;")
        ly.addWidget(title)

        desc = QLabel(t("onboarding.welcome_desc",
                         "Votre assistant IA de bureau.\n"
                         "Configurons votre premier fournisseur LLM en quelques étapes."))
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 14px; background: transparent;")
        ly.addWidget(desc)

        return w

    # ── Step 1: Provider selection ────────────────────────────────────────
    def _build_provider_step(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        ly = QVBoxLayout(w)
        ly.setSpacing(12)

        title = QLabel(t("onboarding.provider_title", "Choisissez votre fournisseur LLM"))
        title.setStyleSheet("font-size: 18px; font-weight: 700; background: transparent;")
        ly.addWidget(title)

        self._provider_group = QButtonGroup(self)
        for i, (key, meta) in enumerate(_PROVIDERS.items()):
            rb = QRadioButton(f"{meta['label']}\n  {meta['desc']}")
            rb.setChecked(key == self._selected_provider)
            rb.setStyleSheet(f"""
                QRadioButton {{
                    color: {current_theme().text}; font-size: 13px;
                    spacing: 8px; background: transparent; padding: 8px;
                }}
                QRadioButton::indicator {{
                    width: 16px; height: 16px;
                }}
            """)
            self._provider_group.addButton(rb, i)
            ly.addWidget(rb)

        ly.addStretch()
        return w

    # ── Step 2: API Key input ────────────────────────────────────────────
    def _build_apikey_step(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        ly = QVBoxLayout(w)
        ly.setSpacing(12)

        self._key_title = QLabel(t("onboarding.key_title", "Entrez votre clé API"))
        self._key_title.setStyleSheet("font-size: 18px; font-weight: 700; background: transparent;")
        ly.addWidget(self._key_title)

        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.Password)
        self._key_input.setPlaceholderText(t("onboarding.key_placeholder", "sk-... ou votre clé API"))
        self._key_input.setMinimumWidth(300)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background: {current_theme().input_bg};
                border: 1px solid {current_theme().border};
                border-radius: 8px; color: {current_theme().text};
                font-size: 14px; padding: 10px 14px;
            }}
            QLineEdit::placeholder {{ color: {current_theme().muted}; }}
        """)
        ly.addWidget(self._key_input)

        # Show/hide toggle
        toggle_ly = QHBoxLayout()
        self._show_key_btn = QPushButton(t("onboarding.show_key", "Afficher"))
        self._show_key_btn.setCheckable(True)
        self._show_key_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._show_key_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {current_theme().accent};
                border: none; font-size: 12px; padding: 4px 8px;
            }}
            QPushButton:hover {{ text-decoration: underline; }}
        """)
        self._show_key_btn.clicked.connect(self._toggle_key_visibility)
        toggle_ly.addWidget(self._show_key_btn)
        toggle_ly.addStretch()
        ly.addLayout(toggle_ly)

        # Get key button
        self._get_key_btn = QPushButton(t("onboarding.get_key", "Obtenir une clé"))
        self._get_key_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._get_key_btn.setStyleSheet(f"""
            QPushButton {{
                background: {current_theme().accent}; color: white;
                border: none; border-radius: 8px; padding: 8px 18px;
                font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {current_theme().accent_hover}; }}
        """)
        self._get_key_btn.clicked.connect(self._open_key_url)
        ly.addWidget(self._get_key_btn)

        ly.addStretch()
        return w

    # ── Step 3: Connection test ──────────────────────────────────────────
    def _build_test_step(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        ly = QVBoxLayout(w)
        ly.setAlignment(Qt.AlignCenter)
        ly.setSpacing(16)

        self._test_status_label = QLabel(t("onboarding.testing", "Test de connexion en cours..."))
        self._test_status_label.setAlignment(Qt.AlignCenter)
        self._test_status_label.setStyleSheet("font-size: 16px; font-weight: 600; background: transparent;")
        ly.addWidget(self._test_status_label)

        self._test_detail_label = QLabel("")
        self._test_detail_label.setAlignment(Qt.AlignCenter)
        self._test_detail_label.setWordWrap(True)
        self._test_detail_label.setStyleSheet("font-size: 13px; background: transparent;")
        ly.addWidget(self._test_detail_label)

        # Spinner indicator (animated dots)
        self._spinner_label = QLabel("⠋")
        self._spinner_label.setAlignment(Qt.AlignCenter)
        self._spinner_label.setStyleSheet("font-size: 32px; background: transparent;")
        ly.addWidget(self._spinner_label)

        self._spinner_timer = QTimer(self)
        self._spinner_frame = 0
        self._spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self._spinner_timer.timeout.connect(self._tick_spinner)

        # Retry button (hidden by default)
        self._retry_btn = QPushButton(t("onboarding.retry", "Réessayer"))
        self._retry_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._retry_btn.hide()
        self._retry_btn.setStyleSheet(f"""
            QPushButton {{
                background: {current_theme().accent}; color: white;
                border: none; border-radius: 8px; padding: 10px 24px;
                font-size: 14px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {current_theme().accent_hover}; }}
        """)
        self._retry_btn.clicked.connect(self._run_connection_test)
        ly.addWidget(self._retry_btn)

        return w

    # ── Step 4: Ready ────────────────────────────────────────────────────
    def _build_ready_step(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        ly = QVBoxLayout(w)
        ly.setAlignment(Qt.AlignCenter)
        ly.setSpacing(16)

        checkmark = QLabel("✅")
        checkmark.setAlignment(Qt.AlignCenter)
        checkmark.setStyleSheet("font-size: 64px; background: transparent;")
        ly.addWidget(checkmark)

        title = QLabel(t("onboarding.ready_title", "Tout est prêt !"))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: 700; background: transparent;")
        ly.addWidget(title)

        desc = QLabel(t("onboarding.ready_desc",
                         "Posez votre première question."))
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 14px; background: transparent;")
        ly.addWidget(desc)

        start_btn = QPushButton(t("onboarding.start", "Commencer"))
        start_btn.setCursor(QCursor(Qt.PointingHandCursor))
        start_btn.setStyleSheet(f"""
            QPushButton {{
                background: {current_theme().accent}; color: white;
                border: none; border-radius: 10px; padding: 12px 36px;
                font-size: 16px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {current_theme().accent_hover}; }}
        """)
        start_btn.clicked.connect(self._finish_onboarding)
        ly.addWidget(start_btn)

        return w

    # ── Navigation ───────────────────────────────────────────────────────
    def _update_step_ui(self):
        total = 5
        step = self._current_step
        th = current_theme()
        self._step_label.setText(t("onboarding.step_of", f"Étape {step + 1} sur {total}",
                                    step + 1, total))
        self._step_label.setStyleSheet(
            f"color: {th.muted}; font-size: 12px; font-weight: 600; background: transparent;"
        )
        self._stack.setCurrentIndex(step)

        # Back button visibility
        self._back_btn.setVisible(step > 0)

        # Next button text and visibility
        if step == 4:
            self._next_btn.setVisible(False)
        elif step == 3:
            self._next_btn.setText(t("onboarding.next", "Suivant"))
            self._next_btn.setVisible(False)  # test auto-advances
        else:
            self._next_btn.setText(t("onboarding.next", "Suivant"))
            self._next_btn.setVisible(True)

        # Update provider title in step 2
        if step == 2:
            provider_meta = _PROVIDERS.get(self._selected_provider, {})
            self._key_title.setText(
                t("onboarding.key_title_for",
                  f"Entrez votre clé API {provider_meta.get('label', '')}",
                  provider_meta.get('label', ''))
            )
            self._get_key_btn.setVisible(bool(provider_meta.get('key_url')))
            if self._selected_provider == 'ollama':
                self._key_input.setPlaceholderText(
                    t("onboarding.ollama_url_placeholder", "http://localhost:11434")
                )
                self._key_input.setEchoMode(QLineEdit.Normal)
            else:
                self._key_input.setPlaceholderText(
                    t("onboarding.key_placeholder", "sk-... ou votre clé API")
                )
                self._key_input.setEchoMode(QLineEdit.Password)

        self._apply_step_style()

    def _apply_step_style(self):
        th = current_theme()
        btn_style = f"""
            QPushButton {{
                background: {th.accent}; color: white;
                border: none; border-radius: 8px; padding: 10px 24px;
                font-size: 14px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {th.accent_hover}; }}
            QPushButton:disabled {{ background: {th.border_light}; color: {th.muted}; }}
        """
        self._next_btn.setStyleSheet(btn_style)
        back_style = f"""
            QPushButton {{
                background: transparent; color: {th.muted};
                border: 1px solid {th.border}; border-radius: 8px;
                padding: 10px 24px; font-size: 14px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {th.card_bg}; color: {th.text}; }}
        """
        self._back_btn.setStyleSheet(back_style)

    def _go_next(self):
        step = self._current_step
        if step == 1:
            # Read selected provider
            idx = self._provider_group.checkedId()
            keys = list(_PROVIDERS.keys())
            if 0 <= idx < len(keys):
                self._selected_provider = keys[idx]
        elif step == 2:
            # Read API key
            self._api_key = self._key_input.text().strip()
            if not self._api_key and self._selected_provider != 'ollama':
                # Don't advance without key for cloud providers
                self._key_input.setStyleSheet(
                    f"QLineEdit {{ background: rgba(239,68,68,0.1); "
                    f"border: 2px solid {current_theme().red}; "
                    f"border-radius: 8px; color: {current_theme().text}; "
                    f"font-size: 14px; padding: 10px 14px; }}"
                )
                return

        self._current_step = min(step + 1, 4)
        self._update_step_ui()

        # Auto-run connection test on step 3
        if self._current_step == 3:
            self._run_connection_test()

    def _go_back(self):
        self._current_step = max(self._current_step - 1, 0)
        self._update_step_ui()

    # ── Helpers ───────────────────────────────────────────────────────────
    def _toggle_key_visibility(self, checked):
        self._key_input.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)

    def _open_key_url(self):
        meta = _PROVIDERS.get(self._selected_provider, {})
        url = meta.get('key_url', '')
        if url:
            webbrowser.open(url)

    def _tick_spinner(self):
        self._spinner_frame = (self._spinner_frame + 1) % len(self._spinner_chars)
        self._spinner_label.setText(self._spinner_chars[self._spinner_frame])

    # ── Connection test ──────────────────────────────────────────────────
    def _run_connection_test(self):
        th = current_theme()
        self._test_status_label.setText(t("onboarding.testing", "Test de connexion en cours..."))
        self._test_status_label.setStyleSheet(
            f"color: {th.text}; font-size: 16px; font-weight: 600; background: transparent;"
        )
        self._test_detail_label.setText("")
        self._spinner_label.show()
        self._spinner_timer.start(80)
        self._retry_btn.hide()

        self._test_worker = _ConnectionTestWorker(self._selected_provider, self._api_key, self)
        self._test_worker.success.connect(self._on_test_success)
        self._test_worker.error.connect(self._on_test_error)
        self._test_worker.start()

    def _on_test_success(self, message: str):
        self._spinner_timer.stop()
        self._spinner_label.hide()
        th = current_theme()
        self._test_status_label.setText("✅ " + t("onboarding.test_success", "Connexion réussie !"))
        self._test_status_label.setStyleSheet(
            f"color: {th.green}; font-size: 16px; font-weight: 600; background: transparent;"
        )
        self._test_detail_label.setText(message)
        self._test_detail_label.setStyleSheet(
            f"color: {th.text_secondary}; font-size: 13px; background: transparent;"
        )

        # Store the API key via credential_store
        self._store_api_key()

        # Auto-advance to "Ready" after a short delay
        QTimer.singleShot(1200, self._auto_advance_after_test)

    def _on_test_error(self, message: str):
        self._spinner_timer.stop()
        self._spinner_label.hide()
        th = current_theme()
        self._test_status_label.setText("❌ " + t("onboarding.test_failed", "Échec de la connexion"))
        self._test_status_label.setStyleSheet(
            f"color: {th.red}; font-size: 16px; font-weight: 600; background: transparent;"
        )
        self._test_detail_label.setText(message)
        self._test_detail_label.setStyleSheet(
            f"color: {th.text_secondary}; font-size: 13px; background: transparent;"
        )
        self._retry_btn.show()

    def _auto_advance_after_test(self):
        self._current_step = 4
        self._update_step_ui()

    def _store_api_key(self):
        """Store the API key using the credential store (keyring)."""
        try:
            from agentmain.credential_store import get_credential_store
            store = get_credential_store()
            meta = _PROVIDERS.get(self._selected_provider, {})
            cred_key = meta.get('cred_key', f'{self._selected_provider}_api_key')
            if self._api_key:
                store.set_credential(cred_key, self._api_key)
                logger.info("Stored API key for provider %s via credential store", self._selected_provider)
        except Exception:
            logger.debug("Failed to store API key via credential store", exc_info=True)

    def _finish_onboarding(self):
        """Emit the onboarding_complete signal."""
        self.onboarding_complete.emit(self._selected_provider, self._api_key)


def has_credentials() -> bool:
    """Check if any API credentials exist in the credential store.

    Returns True if at least one known API key is found, meaning the
    user has already been through onboarding or manual configuration.
    """
    try:
        from agentmain.credential_store import get_credential_store
        store = get_credential_store()
        keys = store.list_keys()
        # Check for known API key patterns
        api_key_patterns = ["api_key", "apikey", "anthropic", "openai", "google", "ollama"]
        for k in keys:
            for pat in api_key_patterns:
                if pat in k.lower():
                    return True
    except Exception:
        pass

    # Also check if mykey.py exists with actual keys
    try:
        import os
        mykey_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))), "mykey.py")
        if os.path.isfile(mykey_path):
            with open(mykey_path, 'r') as f:
                content = f.read()
            # Check if it has non-placeholder keys
            if "apikey" in content and "VOTRE-CLE" not in content and "YOUR-KEY" not in content:
                return True
    except Exception:
        pass

    return False
