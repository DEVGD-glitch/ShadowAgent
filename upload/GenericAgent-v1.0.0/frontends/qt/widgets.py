"""
Widgets réutilisables pour l'interface Qt.
Séparateurs, badges, onglets, boutons d'action, lignes de message,
ToolCallWidget, ThinkingSection, AgentStatusBar et ApprovalDialog.
Extrait de qtapp.py pour la refonte modulaire.
"""
from __future__ import annotations

import html as _html
import re
import webbrowser
from urllib.parse import urlparse
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QTextBrowser, QApplication, QDialog,
    QDialogButtonBox, QTextEdit, QMessageBox,
)
from PySide6.QtCore import Qt, QByteArray, QSize, QTimer, QPropertyAnimation, QEasingCurve, Signal, QUrl
from PySide6.QtGui import QPainter, QColor, QPixmap, QCursor, QIcon

from frontends.qt.constants import _SVG_USER, _SVG_BOT, _SVG_COPY, _SVG_REGEN
from frontends.qt.theme import C, _MD_CSS, current_theme, generate_md_css
from frontends.qt.utils import _md_to_html, _svg_icon


def _safe_open_url(url: QUrl) -> None:
    """Validate and open an external URL: only http/https schemes allowed."""
    url_str = url.toString()
    parsed = urlparse(url_str)
    if parsed.scheme not in ("http", "https"):
        return  # Block javascript:, data:, file:, etc.
    if QMessageBox.question(
        None,
        "Ouvrir le lien",
        f"Ouvrir ce lien dans le navigateur ?\n{url_str}",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    ) == QMessageBox.Yes:
        webbrowser.open(url_str)


# ── small reusable widgets ────────────────────────────────────────────────────


class _Separator(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background: {C['border']};")


class _Badge(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(
            "QLabel { background: rgba(63,63,70,0.9); color: #a1a1aa;"
            " border: 1px solid #3f3f46; border-radius: 9px;"
            " padding: 1px 8px; font-size: 11px; }"
        )


class _StreamingBadge(QLabel):
    def __init__(self, parent=None):
        super().__init__("Traitement...", parent)
        self.setStyleSheet(
            "QLabel { background: rgba(124,58,237,0.18); color: #c4b5fd;"
            " border: 1px solid rgba(124,58,237,0.35); border-radius: 9px;"
            " padding: 1px 8px; font-size: 11px; }"
        )
        self.hide()


# ── message row ───────────────────────────────────────────────────────────────


class _MsgRow(QWidget):
    """A single message row – flat layout with avatar, inspired by ChatGPT / Qwen."""

    _ACTION_BTN = """
        QPushButton {
            background: transparent; border: none; border-radius: 4px; padding: 3px;
        }
        QPushButton:hover { background: rgba(63,63,70,0.6); }
    """

    def __init__(self, text: str, role: str, parent=None, on_resend=None):
        super().__init__(parent)
        self._text = text
        self._role = role
        self._on_resend = on_resend
        self._action_row = None
        self._finished = True

        is_user = role == "user"
        self.setStyleSheet(
            "background: rgba(255,255,255,0.03);" if is_user else "background: transparent;"
        )

        outer = QHBoxLayout(self)
        outer.setContentsMargins(20, 10, 20, 10)
        outer.setSpacing(12)
        outer.setAlignment(Qt.AlignTop)

        avatar = QLabel()
        avatar_size = max(30, QWidget().fontMetrics().height() + 14)
        avatar.setFixedSize(avatar_size, avatar_size)
        avatar.setAlignment(Qt.AlignCenter)
        svg_data = _SVG_USER if is_user else _SVG_BOT
        avatar_color = "#c8c8d0" if is_user else "#9eb4d0"
        pm = QPixmap(avatar_size, avatar_size)
        pm.fill(QColor(0, 0, 0, 0))
        from PySide6.QtSvg import QSvgRenderer
        renderer = QSvgRenderer(QByteArray(svg_data.replace("{c}", avatar_color).encode()))
        p = QPainter(pm)
        renderer.render(p)
        p.end()
        avatar.setPixmap(pm)
        avatar.setStyleSheet(
            "QLabel { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.10);"
            " border-radius: 15px; }"
        )
        outer.addWidget(avatar, 0, Qt.AlignTop)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(2)

        role_lbl = QLabel("Vous" if is_user else "Assistant")
        role_lbl.setStyleSheet(
            "color: #d4d4d8; font-size: 12px; font-weight: 700; background: transparent;"
        )
        right.addWidget(role_lbl)

        if is_user:
            label = QLabel(text)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            label.setStyleSheet(
                "QLabel { background: transparent; color: #e4e4e7;"
                " padding: 2px 0; font-size: 14px; line-height: 1.6; }"
            )
            right.addWidget(label)
            self._label = label
        else:
            browser = QTextBrowser()
            browser.setReadOnly(True)
            browser.setOpenExternalLinks(False)
            browser.anchorClicked.connect(_safe_open_url)
            browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            browser.document().setDefaultStyleSheet(_MD_CSS)
            browser.setStyleSheet(
                "QTextBrowser { background: transparent; color: #e4e4e7;"
                " border: none; padding: 0; font-size: 14px; }"
            )
            browser.setHtml(_md_to_html(text))
            self._label = browser
            right.addWidget(browser)
            self._adjust_browser_height()

            self._action_row = QWidget()
            self._action_row.setStyleSheet("background: transparent;")
            alayout = QHBoxLayout(self._action_row)
            alayout.setContentsMargins(0, 4, 0, 0)
            alayout.setSpacing(4)

            icon_sz = QSize(15, 15)

            copy_btn = QPushButton()
            copy_btn.setIcon(_svg_icon("copy", _SVG_COPY))
            copy_btn.setIconSize(icon_sz)
            action_btn_sz = max(26, QWidget().fontMetrics().height() + 10)
            copy_btn.setFixedSize(action_btn_sz, action_btn_sz - 2)
            copy_btn.setStyleSheet(self._ACTION_BTN)
            copy_btn.setToolTip("Copier")
            copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
            copy_btn.clicked.connect(self._copy_text)
            alayout.addWidget(copy_btn)

            if on_resend:
                regen_btn = QPushButton()
                regen_btn.setIcon(_svg_icon("regen", _SVG_REGEN))
                regen_btn.setIconSize(icon_sz)
                regen_btn.setFixedSize(action_btn_sz, action_btn_sz - 2)
                regen_btn.setStyleSheet(self._ACTION_BTN)
                regen_btn.setToolTip("Regénérer")
                regen_btn.setCursor(QCursor(Qt.PointingHandCursor))
                regen_btn.clicked.connect(self._do_resend)
                alayout.addWidget(regen_btn)

            alayout.addStretch()
            self._action_row.hide()
            right.addWidget(self._action_row)

        outer.addLayout(right, 1)

    def _copy_text(self):
        QApplication.clipboard().setText(self._text)

    def _do_resend(self):
        if self._on_resend:
            self._on_resend()

    def enterEvent(self, event):
        if self._action_row and self._finished:
            self._action_row.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._action_row:
            self._action_row.hide()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._role != "user" and hasattr(self, '_label'):
            self._adjust_browser_height()

    def set_finished(self, done: bool):
        self._finished = done
        if not done and self._action_row:
            self._action_row.hide()

    def set_interrupted_style(self):
        """Apply a distinct visual style for interrupted/stopped messages.

        Makes the message appear faded/italic with a muted color to
        visually distinguish it from complete LLM responses.
        """
        if self._role == "user":
            self._label.setStyleSheet(
                "QLabel { background: transparent; color: #71717a;"
                " padding: 2px 0; font-size: 14px; font-style: italic; }"
            )
        else:
            self._label.setStyleSheet(
                "QTextBrowser { background: transparent; color: #71717a;"
                " border: none; padding: 0; font-size: 14px; font-style: italic; }"
            )
            # Append an "(Arrêté)" indicator in the rendered HTML
            current_text = self._text
            if current_text and not current_text.rstrip().endswith("(Arrêté)"):
                self._text = current_text.rstrip() + "\n\n*(Arrêté)*"
            self._label.setHtml(_md_to_html(self._text))
            self._adjust_browser_height()

    def _adjust_browser_height(self):
        doc = self._label.document()
        w = self._label.width()
        if w < 50:
            w = 460
        doc.setTextWidth(w - 6)
        self._label.setFixedHeight(int(doc.size().height() + 8))

    def set_text(self, text: str):
        self._text = text
        if self._role == "user":
            self._label.setText(text)
            self._label.adjustSize()
        else:
            self._label.setHtml(_md_to_html(text))
            self._adjust_browser_height()

    def highlight(self, keyword: str):
        """Apply highlight and return keyword's y position in document, or None."""
        if not keyword or not self._text:
            return None
        kw_lower = keyword.lower()
        text_lower = self._text.lower()
        if kw_lower not in text_lower:
            return None
        if self._role == "user":
            escaped = _html.escape(self._text)
            kw_esc = _html.escape(keyword)
            highlighted = escaped.replace(kw_esc, f'<span style="background: rgba(251,191,36,0.35); color: #fbbf24;">{kw_esc}</span>')
            self._label.setText(highlighted)
            self._label.adjustSize()
            return 0  # plain text, keyword at top
        else:
            from PySide6.QtGui import QTextDocument, QTextCursor, QTextCharFormat
            doc = self._label.document()
            cursor = QTextCursor(doc)
            flags = QTextDocument.FindFlags(0)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(251, 191, 36, 90))
            fmt.setForeground(QColor(251, 191, 36))
            keyword_y = None
            while True:
                cursor = doc.find(keyword, cursor, flags)
                if cursor.isNull():
                    break
                cursor.mergeCharFormat(fmt)
                if keyword_y is None:
                    keyword_y = self._label.cursorRect(cursor).y()
            self._adjust_browser_height()
            return keyword_y

    def clear_highlight(self):
        if self._role == "user":
            self._label.setText(self._text)
            self._label.adjustSize()
        else:
            self._label.setHtml(_md_to_html(self._text))
            self._adjust_browser_height()


# ── tab button & action button ────────────────────────────────────────────────


class _TabButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setFixedHeight(max(30, self.fontMetrics().height() + 10))
        self._apply_theme_style()

    def _apply_theme_style(self):
        t = current_theme()
        self.setStyleSheet(f"""
        QPushButton {{
            background: transparent; color: {t.muted};
            border: none; border-radius: 8px;
            padding: 0 14px; font-size: 12px; font-weight: 700;
        }}
        QPushButton:hover {{
            background: {t.border_light}; color: {t.text};
        }}
        QPushButton:checked {{
            background: {t.accent}; color: white;
        }}
        """)


def _action_btn(label: str, color: str, icon: QIcon | None = None) -> QPushButton:
    btn = QPushButton(label)
    if icon and not icon.isNull():
        btn.setIcon(icon)
        btn.setIconSize(QSize(16, 16))
    btn.setFixedHeight(max(36, btn.fontMetrics().height() + 12))
    btn.setStyleSheet(f"""
        QPushButton {{
            background: rgba(35,35,40,0.8); color: {C['text']};
            border: 1px solid {C['border']};
            border-left: 3px solid {color};
            border-radius: 8px; padding: 0 14px;
            font-size: 13px; font-weight: 700; text-align: left;
        }}
        QPushButton:hover {{ background: rgba(55,55,62,0.9); }}
        QPushButton:checked {{ color: {color}; background: rgba(35,35,40,0.95); }}
    """)
    return btn


# ══════════════════════════════════════════════════════════════════════════════
# Phase 7 — UI/UX Superpowers
# ══════════════════════════════════════════════════════════════════════════════


# ── ToolCallWidget ────────────────────────────────────────────────────────────

# Status colors for tool call border and badge
_TOOL_STATUS_COLORS = {
    "pending": {"border": "#eab308", "bg": "rgba(234,179,8,0.12)", "text": "#fbbf24", "label": "En cours"},
    "success": {"border": "#22c55e", "bg": "rgba(34,197,94,0.10)", "text": "#4ade80", "label": "Succès"},
    "error":   {"border": "#ef4444", "bg": "rgba(239,68,68,0.12)", "text": "#f87171", "label": "Erreur"},
}


class ToolCallWidget(QWidget):
    """Widget showing a tool call with status and expandable result.

    Shows: [Icon] [Tool name + summary] [Status badge]
    Expandable: [Detail with result]

    States: pending (yellow), success (green), error (red)
    """

    def __init__(
        self,
        tool_name: str,
        args_summary: str = "",
        status: str = "pending",
        result: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._tool_name = tool_name
        self._args_summary = args_summary
        self._status = status
        self._result = result
        self._expanded = False

        self._build_ui()

    def _build_ui(self):
        sc = _TOOL_STATUS_COLORS.get(self._status, _TOOL_STATUS_COLORS["pending"])

        self.setStyleSheet(f"""
            ToolCallWidget {{
                background: {sc['bg']};
                border: 1px solid rgba(63,63,70,0.4);
                border-left: 3px solid {sc['border']};
                border-radius: 6px;
            }}
        """)

        ly = QVBoxLayout(self)
        ly.setContentsMargins(10, 6, 10, 6)
        ly.setSpacing(4)

        # ── Header row ──
        header = QHBoxLayout()
        header.setSpacing(8)

        # Tool icon label (wrench unicode)
        icon_lbl = QLabel("\u2699")  # ⚙ GEAR
        icon_lbl.setStyleSheet(f"color: {sc['text']}; font-size: 14px; background: transparent;")
        icon_lbl.setFixedWidth(18)
        header.addWidget(icon_lbl)

        # Tool name
        name_lbl = QLabel(self._tool_name)
        name_lbl.setStyleSheet(
            "color: #d4d4d8; font-size: 12px; font-weight: 700; background: transparent;"
        )
        header.addWidget(name_lbl)

        # Args summary
        if self._args_summary:
            summary_text = self._args_summary
            if len(summary_text) > 80:
                summary_text = summary_text[:77] + "..."
            args_lbl = QLabel(summary_text)
            args_lbl.setStyleSheet(
                "color: #71717a; font-size: 11px; background: transparent;"
            )
            args_lbl.setWordWrap(True)
            header.addWidget(args_lbl, 1)

        header.addStretch()

        # Status badge
        self._badge = QLabel(sc["label"])
        self._badge.setStyleSheet(f"""
            QLabel {{
                background: {sc['bg']}; color: {sc['text']};
                border: 1px solid {sc['border']};
                border-radius: 9px; padding: 1px 8px; font-size: 10px; font-weight: 600;
            }}
        """)
        header.addWidget(self._badge)

        # Expand/collapse toggle button
        self._toggle_btn = QPushButton("\u25B6")  # ▶
        toggle_sz = max(18, self.fontMetrics().height() + 2)
        self._toggle_btn.setFixedSize(toggle_sz, toggle_sz)
        self._toggle_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none; color: #71717a;
                font-size: 10px; padding: 0;
            }
            QPushButton:hover { color: #a1a1aa; }
        """)
        self._toggle_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._toggle_btn.clicked.connect(self._toggle_expand)
        header.addWidget(self._toggle_btn)

        ly.addLayout(header)

        # ── Expandable detail area ──
        self._detail_widget = QWidget()
        self._detail_widget.setStyleSheet("background: transparent;")
        detail_ly = QVBoxLayout(self._detail_widget)
        detail_ly.setContentsMargins(24, 4, 4, 4)
        detail_ly.setSpacing(2)

        self._result_browser = QTextBrowser()
        self._result_browser.setReadOnly(True)
        self._result_browser.setOpenExternalLinks(False)
        self._result_browser.anchorClicked.connect(_safe_open_url)
        self._result_browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._result_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._result_browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._result_browser.document().setDefaultStyleSheet(_MD_CSS)
        self._result_browser.setStyleSheet(
            "QTextBrowser { background: rgba(24,24,30,0.6); color: #a1a1aa;"
            " border: 1px solid #3f3f46; border-radius: 4px;"
            " padding: 6px; font-size: 12px; }"
        )
        self._result_browser.setHtml(_md_to_html(self._result) if self._result else "")
        self._adjust_result_height()
        detail_ly.addWidget(self._result_browser)

        self._detail_widget.hide()
        ly.addWidget(self._detail_widget)

    def _toggle_expand(self):
        self._expanded = not self._expanded
        if self._expanded:
            self._detail_widget.show()
            self._toggle_btn.setText("\u25BC")  # ▼
        else:
            self._detail_widget.hide()
            self._toggle_btn.setText("\u25B6")  # ▶

    def _adjust_result_height(self):
        doc = self._result_browser.document()
        w = self._result_browser.width()
        if w < 50:
            w = 400
        doc.setTextWidth(w - 12)
        h = int(doc.size().height() + 16)
        self._result_browser.setFixedHeight(min(h, 300))

    def set_status(self, status: str, result: str = ""):
        """Update the tool call status and optionally the result text.

        Parameters
        ----------
        status : str
            One of 'pending', 'success', 'error'.
        result : str
            The tool result text (markdown).
        """
        self._status = status
        if result:
            self._result = result

        sc = _TOOL_STATUS_COLORS.get(status, _TOOL_STATUS_COLORS["pending"])

        # Update border/badge styling
        self.setStyleSheet(f"""
            ToolCallWidget {{
                background: {sc['bg']};
                border: 1px solid rgba(63,63,70,0.4);
                border-left: 3px solid {sc['border']};
                border-radius: 6px;
            }}
        """)

        self._badge.setText(sc["label"])
        self._badge.setStyleSheet(f"""
            QLabel {{
                background: {sc['bg']}; color: {sc['text']};
                border: 1px solid {sc['border']};
                border-radius: 9px; padding: 1px 8px; font-size: 10px; font-weight: 600;
            }}
        """)

        if result:
            self._result_browser.setHtml(_md_to_html(result))
            self._adjust_result_height()

    def set_result(self, result: str):
        """Set the result text (markdown)."""
        self._result = result
        self._result_browser.setHtml(_md_to_html(result))
        self._adjust_result_height()

    @property
    def tool_name(self) -> str:
        return self._tool_name

    @property
    def status(self) -> str:
        return self._status

    @property
    def is_expanded(self) -> bool:
        return self._expanded


# ── ThinkingSection ───────────────────────────────────────────────────────────

# Regex patterns for thinking tags
_THINKING_RE = re.compile(r"<thinking>([\s\S]*?)</thinking>", re.IGNORECASE)
_THINKERING_RE = re.compile(r"<thinkering>([\s\S]*?)</thinkering>", re.IGNORECASE)


def _extract_thinking(text: str) -> tuple[str, str]:
    """Extract thinking content from text with <thinking> or <thinkering> tags.

    Returns (cleaned_text, thinking_content).
    """
    thinking = ""
    for pattern in (_THINKING_RE, _THINKERING_RE):
        m = pattern.search(text)
        if m:
            thinking = m.group(1).strip()
            text = pattern.sub("", text).strip()
            break
    return text, thinking


class ThinkingSection(QWidget):
    """Collapsible section showing agent reasoning/thinking.

    Detects <thinking>...</thinking> tags in responses.
    Shows: [arrow] Raisonnement (Xs) — expandable
    """

    def __init__(
        self,
        content: str = "",
        duration_seconds: float | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._content = content
        self._duration = duration_seconds
        self._expanded = False
        self._max_height = 0

        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            ThinkingSection {
                background: rgba(24,24,30,0.7);
                border: 1px solid #27272a;
                border-radius: 6px;
            }
        """)

        ly = QVBoxLayout(self)
        ly.setContentsMargins(10, 6, 10, 6)
        ly.setSpacing(0)

        # ── Header (clickable to expand/collapse) ──
        self._header_btn = QPushButton()
        self._header_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._header_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none; color: #71717a;
                text-align: left; padding: 2px 0; font-size: 12px;
            }
            QPushButton:hover { color: #a1a1aa; }
        """)

        dur_str = f" ({self._duration:.1f}s)" if self._duration is not None else ""
        self._header_btn.setText(f"\u25B6 Raisonnement{dur_str}")
        self._header_btn.clicked.connect(self._toggle_expand)
        ly.addWidget(self._header_btn)

        # ── Content (collapsible) ──
        self._content_widget = QWidget()
        self._content_widget.setStyleSheet("background: transparent;")
        content_ly = QVBoxLayout(self._content_widget)
        content_ly.setContentsMargins(20, 4, 4, 4)
        content_ly.setSpacing(0)

        self._content_browser = QTextBrowser()
        self._content_browser.setReadOnly(True)
        self._content_browser.setOpenExternalLinks(False)
        self._content_browser.anchorClicked.connect(_safe_open_url)
        self._content_browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._content_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._content_browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._content_browser.document().setDefaultStyleSheet(_MD_CSS)
        self._content_browser.setStyleSheet(
            "QTextBrowser { background: transparent; color: #71717a;"
            " border: none; padding: 0; font-size: 12px; font-style: italic; }"
        )
        self._content_browser.setHtml(_md_to_html(self._content) if self._content else "")
        self._adjust_content_height()
        content_ly.addWidget(self._content_browser)

        self._content_widget.hide()
        ly.addWidget(self._content_widget)

    def _toggle_expand(self):
        self._expanded = not self._expanded
        dur_str = f" ({self._duration:.1f}s)" if self._duration is not None else ""
        if self._expanded:
            self._content_widget.show()
            self._header_btn.setText(f"\u25BC Raisonnement{dur_str}")
        else:
            self._content_widget.hide()
            self._header_btn.setText(f"\u25B6 Raisonnement{dur_str}")

    def _adjust_content_height(self):
        doc = self._content_browser.document()
        w = self._content_browser.width()
        if w < 50:
            w = 400
        doc.setTextWidth(w - 12)
        h = int(doc.size().height() + 12)
        self._content_browser.setFixedHeight(min(h, 400))

    def set_content(self, content: str):
        """Update the thinking content text."""
        self._content = content
        self._content_browser.setHtml(_md_to_html(content))
        self._adjust_content_height()

    def set_duration(self, seconds: float):
        """Update the displayed duration."""
        self._duration = seconds
        dur_str = f" ({seconds:.1f}s)"
        arrow = "\u25BC" if self._expanded else "\u25B6"
        self._header_btn.setText(f"{arrow} Raisonnement{dur_str}")

    @property
    def is_expanded(self) -> bool:
        return self._expanded

    @property
    def content(self) -> str:
        return self._content


# ── AgentStatusBar ────────────────────────────────────────────────────────────

_AGENT_STATUS_COLORS = {
    "idle":           {"dot": "#22c55e", "label": "Inactif",        "animate": False},
    "thinking":       {"dot": "#eab308", "label": "Raisonnement...", "animate": True},
    "acting":         {"dot": "#3b82f6", "label": "Action...",      "animate": True},
    "waiting_input":  {"dot": "#f97316", "label": "En attente",     "animate": True},
    "error":          {"dot": "#ef4444", "label": "Erreur",         "animate": False},
    "streaming":      {"dot": "#a855f7", "label": "Streaming...",   "animate": True},
}


class AgentStatusBar(QWidget):
    """Animated status indicator for the agent.

    States: idle (green dot), thinking (yellow pulse), acting (blue rotate),
    waiting_input (orange blink), error (red), streaming (purple progress)
    """

    status_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = "idle"
        self._pulse_phase = 0.0
        self._build_ui()

        # Animation timer for pulsing/rotating states
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start(50)  # ~20fps

    def _build_ui(self):
        self.setFixedHeight(max(20, self.fontMetrics().height() + 6))
        self.setStyleSheet("background: transparent;")

        ly = QHBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(6)

        # Animated dot
        self._dot = QLabel("\u25CF")  # ●
        sc = _AGENT_STATUS_COLORS["idle"]
        self._dot.setStyleSheet(f"color: {sc['dot']}; font-size: 9px;")
        self._dot.setFixedWidth(14)
        ly.addWidget(self._dot)

        # Status label
        self._label = QLabel(sc["label"])
        self._label.setStyleSheet("color: #71717a; font-size: 11px;")
        ly.addWidget(self._label)

        ly.addStretch()

    def _tick(self):
        sc = _AGENT_STATUS_COLORS.get(self._status, _AGENT_STATUS_COLORS["idle"])
        if sc["animate"]:
            self._pulse_phase += 0.15
            alpha = int(128 + 127 * __import__("math").sin(self._pulse_phase))
            # Parse the base color
            base_color = sc["dot"]
            if base_color.startswith("#"):
                r = int(base_color[1:3], 16)
                g = int(base_color[3:5], 16)
                b = int(base_color[5:7], 16)
                self._dot.setStyleSheet(
                    f"color: rgba({r},{g},{b},{alpha}); font-size: 9px;"
                )
        else:
            self._dot.setStyleSheet(f"color: {sc['dot']}; font-size: 9px;")

    def set_status(self, status: str):
        """Set the agent status.

        Parameters
        ----------
        status : str
            One of 'idle', 'thinking', 'acting', 'waiting_input', 'error', 'streaming'.
        """
        if status == self._status:
            return
        self._status = status
        sc = _AGENT_STATUS_COLORS.get(status, _AGENT_STATUS_COLORS["idle"])
        self._label.setText(sc["label"])
        self._label.setStyleSheet(f"color: {sc['dot']}; font-size: 11px;")
        if not sc["animate"]:
            self._dot.setStyleSheet(f"color: {sc['dot']}; font-size: 9px;")
        self.status_changed.emit(status)

    @property
    def status(self) -> str:
        return self._status


# ── ApprovalDialog ────────────────────────────────────────────────────────────

_RISK_COLORS = {
    "low":      {"border": "#22c55e", "bg": "rgba(34,197,94,0.08)",  "icon": "\u2713",  "icon_color": "#4ade80"},
    "medium":   {"border": "#eab308", "bg": "rgba(234,179,8,0.08)",  "icon": "\u26A0",  "icon_color": "#fbbf24"},
    "high":     {"border": "#f97316", "bg": "rgba(249,115,22,0.08)", "icon": "\u26A0",  "icon_color": "#fb923c"},
    "critical": {"border": "#ef4444", "bg": "rgba(239,68,68,0.10)",  "icon": "\u26D4",  "icon_color": "#f87171"},
}

# Result codes
APPROVAL_ALLOW = 1
APPROVAL_DENY = 0
APPROVAL_ALWAYS_ALLOW = 2


class ApprovalDialog(QDialog):
    """Modal dialog for approving dangerous agent actions.

    Risk levels: low (green), medium (yellow), high (orange), critical (red)
    Buttons: [Autoriser] [Refuser] [Toujours autoriser ce type]
    """

    def __init__(
        self,
        title: str,
        description: str,
        code_preview: str = "",
        risk_level: str = "medium",
        code_type: str = "shell",
        parent=None,
    ):
        super().__init__(parent)
        self._risk_level = risk_level
        self._result = APPROVAL_DENY

        self.setWindowTitle("Approbation requise")
        self.setModal(True)
        self.setMinimumWidth(440)

        self._build_ui(title, description, code_preview, risk_level, code_type)

    def _build_ui(self, title: str, description: str, code_preview: str,
                  risk_level: str, code_type: str):
        rc = _RISK_COLORS.get(risk_level, _RISK_COLORS["medium"])

        self.setStyleSheet(f"""
            QDialog {{
                background: {C['bg']},
                border: 1px solid {rc['border']};
                border-radius: 8px;
            }}
        """)

        ly = QVBoxLayout(self)
        ly.setContentsMargins(20, 16, 20, 16)
        ly.setSpacing(12)

        # ── Risk indicator header ──
        header_ly = QHBoxLayout()
        header_ly.setSpacing(10)

        risk_labels = {"low": "Faible", "medium": "Moyen", "high": "Élevé", "critical": "Critique"}
        icon_lbl = QLabel(rc["icon"])
        icon_lbl.setStyleSheet(f"color: {rc['icon_color']}; font-size: 22px; background: transparent;")
        header_ly.addWidget(icon_lbl)

        risk_lbl = QLabel(f"Niveau de risque : {risk_labels.get(risk_level, risk_level)}")
        risk_lbl.setStyleSheet(f"color: {rc['icon_color']}; font-size: 13px; font-weight: 700; background: transparent;")
        header_ly.addWidget(risk_lbl, 1)
        ly.addLayout(header_ly)

        # ── Title ──
        title_lbl = QLabel(title)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet("color: #e4e4e7; font-size: 14px; font-weight: 600; background: transparent;")
        ly.addWidget(title_lbl)

        # ── Description ──
        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #a1a1aa; font-size: 12px; background: transparent;")
        ly.addWidget(desc_lbl)

        # ── Code preview ──
        if code_preview:
            preview_box = QTextEdit()
            preview_box.setReadOnly(True)
            preview_box.setPlainText(code_preview)
            preview_box.setMaximumHeight(120)
            preview_box.setStyleSheet(f"""
                QTextEdit {{
                    background: rgba(24,24,30,0.9);
                    color: #c4b5fd; border: 1px solid #3f3f46;
                    border-radius: 4px; padding: 6px; font-size: 12px;
                    font-family: Consolas, "Courier New", monospace;
                }}
            """)
            ly.addWidget(preview_box)

        # ── Buttons ──
        btn_ly = QHBoxLayout()
        btn_ly.setSpacing(8)

        deny_btn = QPushButton("Refuser")
        deny_btn.setStyleSheet("""
            QPushButton {
                background: rgba(63,63,70,0.6); color: #a1a1aa;
                border: 1px solid #3f3f46; border-radius: 6px;
                padding: 6px 16px; font-size: 12px; font-weight: 600;
            }
            QPushButton:hover { background: rgba(239,68,68,0.3); color: #f87171; }
        """)
        deny_btn.setCursor(QCursor(Qt.PointingHandCursor))
        deny_btn.clicked.connect(lambda: self._finish(APPROVAL_DENY))
        btn_ly.addWidget(deny_btn)

        always_btn = QPushButton("Toujours autoriser")
        always_btn.setStyleSheet("""
            QPushButton {
                background: rgba(63,63,70,0.6); color: #a1a1aa;
                border: 1px solid #3f3f46; border-radius: 6px;
                padding: 6px 16px; font-size: 12px; font-weight: 600;
            }
            QPushButton:hover { background: rgba(124,58,237,0.3); color: #c4b5fd; }
        """)
        always_btn.setCursor(QCursor(Qt.PointingHandCursor))
        always_btn.clicked.connect(lambda: self._finish(APPROVAL_ALWAYS_ALLOW))
        btn_ly.addWidget(always_btn)

        allow_btn = QPushButton("Autoriser")
        allow_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba({self._risk_color_rgb()},0.25); color: {rc['icon_color']};
                border: 1px solid {rc['border']}; border-radius: 6px;
                padding: 6px 16px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background: rgba({self._risk_color_rgb()},0.4); }}
        """)
        allow_btn.setCursor(QCursor(Qt.PointingHandCursor))
        allow_btn.clicked.connect(lambda: self._finish(APPROVAL_ALLOW))
        btn_ly.addWidget(allow_btn)

        btn_ly.addStretch()
        ly.addLayout(btn_ly)

    def _risk_color_rgb(self) -> str:
        rc = _RISK_COLORS.get(self._risk_level, _RISK_COLORS["medium"])
        hex_color = rc["border"].lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return f"{r},{g},{b}"

    def _finish(self, result: int):
        self._result = result
        self.done(result)

    def get_result(self) -> int:
        """Return the user's choice: APPROVAL_ALLOW, APPROVAL_DENY, or APPROVAL_ALWAYS_ALLOW."""
        return self._result

    @classmethod
    def ask(
        cls,
        title: str,
        description: str,
        code_preview: str = "",
        risk_level: str = "medium",
        code_type: str = "shell",
        parent=None,
    ) -> int:
        """Show the dialog and return the result code.

        Returns one of APPROVAL_ALLOW, APPROVAL_DENY, APPROVAL_ALWAYS_ALLOW.
        """
        dlg = cls(title, description, code_preview, risk_level, code_type, parent)
        dlg.exec()
        return dlg.get_result()
