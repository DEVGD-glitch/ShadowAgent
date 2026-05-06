"""
Thème visuel de l'interface Qt — palette de couleurs, styles de barre de défilement et CSS Markdown.
Extrait de qtapp.py pour la refonte modulaire.

Phase 2 refactor:
  - Immutable Theme dataclass replaces mutable dict C
  - ThemeManager with callback list for theme_changed notifications
  - Qt Signal (ThemeSignal) for theme_changed — widgets connect via signal/slot
  - Dynamic CSS generation from Theme objects (generate_stylesheet, generate_md_css, generate_scrollbar_css)
  - Complete light + dark + catppuccin themes
  - No more module-level .name() captures — all colors are CSS strings
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

# ══════════════════════════════════════════════════════════════════════════════
# Helper: convert RGB values to CSS color strings
# ══════════════════════════════════════════════════════════════════════════════

def _hex(r: int, g: int, b: int) -> str:
    """Return a CSS hex color string like '#0e0e12'."""
    return f"#{r:02x}{g:02x}{b:02x}"

def _rgba(r: int, g: int, b: int, a: int) -> str:
    """Return a CSS rgba() string. *a* is 0-255."""
    return f"rgba({r},{g},{b},{a / 255:.4g})"


# ══════════════════════════════════════════════════════════════════════════════
# Theme dataclass — immutable definition of a complete visual theme
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Theme:
    """Immutable theme definition holding every visual property.

    All color values are CSS-compatible strings (``#rrggbb`` or ``rgba(...)``)
    so they can be interpolated directly into Qt stylesheets.
    """

    # ── Identity ────────────────────────────────────────────────────────────
    name: str

    # ── Backgrounds ─────────────────────────────────────────────────────────
    bg: str              # Main window background
    panel: str           # Sidebar / panel background
    input_bg: str        # Text input / card background
    card_bg: str         # Content card background (hover overlays, etc.)

    # ── Text ────────────────────────────────────────────────────────────────
    text: str            # Primary text
    text_secondary: str  # Secondary / less important text
    muted: str           # Muted / disabled / placeholder text

    # ── Borders ─────────────────────────────────────────────────────────────
    border: str          # General border color
    border_light: str    # Lighter / subtler border

    # ── Accent ──────────────────────────────────────────────────────────────
    accent: str          # Primary accent color (buttons, highlights)
    accent_hover: str    # Accent on hover

    # ── Buttons ─────────────────────────────────────────────────────────────
    btn_bg: str          # Default button background
    btn_hover: str       # Button hover background
    btn_active: str      # Button active / pressed background

    # ── Scrollbar ───────────────────────────────────────────────────────────
    scrollbar_handle: str   # Scrollbar handle color (with alpha)
    scrollbar_bg: str       # Scrollbar track background

    # ── Chat bubbles ────────────────────────────────────────────────────────
    user_bubble_g0: str       # User bubble gradient start
    user_bubble_g1: str       # User bubble gradient end
    asst_bubble_bg: str       # Assistant bubble background
    asst_bubble_border: str   # Assistant bubble border

    # ── Send button ─────────────────────────────────────────────────────────
    send_g0: str         # Send button gradient start
    send_g1: str         # Send button gradient end

    # ── Status colors ───────────────────────────────────────────────────────
    green: str           # Success / active indicator
    red: str             # Danger / error indicator

    # ── Markdown-specific ───────────────────────────────────────────────────
    md_code_bg: str              # Inline code background
    md_code_color: str           # Inline code text color
    md_pre_bg: str               # <pre> block background
    md_pre_border: str           # <pre> block border
    md_pre_code_color: str       # Code color inside <pre>
    md_link_color: str           # Hyperlink color
    md_blockquote_border: str    # Blockquote left border
    md_blockquote_color: str     # Blockquote text color
    md_table_header_bg: str      # <th> background
    md_table_border: str         # Table cell border
    md_heading_color: str        # H1-H3 text color
    md_heading_sub_color: str    # H4-H6 text color
    md_heading_border: str       # H1/H2 bottom border
    md_hr_color: str             # <hr> color


# ══════════════════════════════════════════════════════════════════════════════
# Pre-defined themes
# ══════════════════════════════════════════════════════════════════════════════

DARK_THEME = Theme(
    name="dark",
    # Backgrounds
    bg=_hex(14, 14, 18),
    panel=_rgba(20, 20, 24, 248),
    input_bg=_rgba(32, 32, 38, 230),
    card_bg=_rgba(35, 35, 42, 153),
    # Text
    text="#e4e4e7",
    text_secondary="#a1a1aa",
    muted="#71717a",
    # Borders
    border=_hex(45, 45, 50),
    border_light=_hex(63, 63, 70),
    # Accent
    accent="#7c3aed",
    accent_hover=_rgba(124, 58, 237, 230),
    # Buttons
    btn_bg=_rgba(35, 35, 40, 204),
    btn_hover=_rgba(55, 55, 62, 230),
    btn_active=_rgba(35, 35, 40, 242),
    # Scrollbar
    scrollbar_handle=_rgba(255, 255, 255, 31),    # rgba(~0.12 alpha)
    scrollbar_bg="transparent",
    # Chat bubbles
    user_bubble_g0=_hex(79, 70, 229),
    user_bubble_g1=_hex(124, 58, 237),
    asst_bubble_bg=_rgba(39, 39, 42, 210),
    asst_bubble_border=_hex(63, 63, 70),
    # Send button
    send_g0=_hex(220, 38, 38),
    send_g1=_hex(239, 68, 68),
    # Status
    green="#22c55e",
    red=_hex(220, 38, 38),
    # Markdown
    md_code_bg=_rgba(63, 63, 70, 153),
    md_code_color="#c4b5fd",
    md_pre_bg=_rgba(24, 24, 30, 242),
    md_pre_border=_hex(63, 63, 70),
    md_pre_code_color="#d4d4d8",
    md_link_color="#818cf8",
    md_blockquote_border="#7c3aed",
    md_blockquote_color="#a1a1aa",
    md_table_header_bg=_rgba(63, 63, 70, 89),
    md_table_border=_hex(63, 63, 70),
    md_heading_color="#f4f4f5",
    md_heading_sub_color="#d4d4d8",
    md_heading_border=_hex(63, 63, 70),
    md_hr_color=_hex(63, 63, 70),
)

LIGHT_THEME = Theme(
    name="light",
    # Backgrounds
    bg=_hex(255, 255, 255),
    panel=_rgba(245, 245, 245, 248),
    input_bg=_rgba(255, 255, 255, 242),
    card_bg=_rgba(229, 231, 235, 153),
    # Text
    text="#18181b",
    text_secondary="#52525b",
    muted="#6b7280",
    # Borders
    border=_hex(209, 213, 219),
    border_light=_hex(229, 231, 235),
    # Accent
    accent="#7c3aed",
    accent_hover=_rgba(124, 58, 237, 230),
    # Buttons
    btn_bg=_rgba(255, 255, 255, 230),
    btn_hover=_rgba(243, 244, 246, 242),
    btn_active=_rgba(229, 231, 235, 255),
    # Scrollbar
    scrollbar_handle=_rgba(0, 0, 0, 31),
    scrollbar_bg="transparent",
    # Chat bubbles
    user_bubble_g0=_hex(79, 70, 229),
    user_bubble_g1=_hex(124, 58, 237),
    asst_bubble_bg=_rgba(243, 244, 246, 210),
    asst_bubble_border=_hex(209, 213, 219),
    # Send button
    send_g0=_hex(220, 38, 38),
    send_g1=_hex(239, 68, 68),
    # Status
    green="#16a34a",
    red=_hex(220, 38, 38),
    # Markdown
    md_code_bg=_rgba(0, 0, 0, 31),
    md_code_color="#6d28d9",
    md_pre_bg=_hex(248, 249, 250),
    md_pre_border=_hex(209, 213, 219),
    md_pre_code_color="#1f2937",
    md_link_color="#4f46e5",
    md_blockquote_border="#7c3aed",
    md_blockquote_color="#6b7280",
    md_table_header_bg=_rgba(0, 0, 0, 25),
    md_table_border=_hex(209, 213, 219),
    md_heading_color="#111827",
    md_heading_sub_color="#374151",
    md_heading_border=_hex(209, 213, 219),
    md_hr_color=_hex(209, 213, 219),
)

CATPPUCCIN_THEME = Theme(
    name="catppuccin",
    # Backgrounds
    bg=_hex(30, 30, 46),
    panel=_rgba(24, 24, 37, 248),
    input_bg=_rgba(30, 30, 46, 230),
    card_bg=_rgba(49, 50, 68, 153),
    # Text
    text="#cdd6f4",
    text_secondary="#bac2de",
    muted="#6c7086",
    # Borders
    border=_hex(49, 50, 68),
    border_light=_hex(69, 71, 90),
    # Accent
    accent="#cba6f7",
    accent_hover=_rgba(203, 166, 247, 230),
    # Buttons
    btn_bg=_rgba(49, 50, 68, 204),
    btn_hover=_rgba(69, 71, 90, 230),
    btn_active=_rgba(49, 50, 68, 242),
    # Scrollbar
    scrollbar_handle=_rgba(205, 214, 244, 31),
    scrollbar_bg="transparent",
    # Chat bubbles
    user_bubble_g0=_hex(137, 180, 250),
    user_bubble_g1=_hex(203, 166, 247),
    asst_bubble_bg=_rgba(49, 50, 68, 210),
    asst_bubble_border=_hex(69, 71, 90),
    # Send button
    send_g0=_hex(243, 139, 168),
    send_g1=_hex(250, 179, 135),
    # Status
    green="#a6e3a1",
    red=_hex(243, 139, 168),
    # Markdown
    md_code_bg=_rgba(69, 71, 90, 153),
    md_code_color="#cba6f7",
    md_pre_bg=_rgba(24, 24, 37, 242),
    md_pre_border=_hex(69, 71, 90),
    md_pre_code_color="#bac2de",
    md_link_color="#89b4fa",
    md_blockquote_border="#cba6f7",
    md_blockquote_color="#6c7086",
    md_table_header_bg=_rgba(69, 71, 90, 89),
    md_table_border=_hex(69, 71, 90),
    md_heading_color="#cdd6f4",
    md_heading_sub_color="#bac2de",
    md_heading_border=_hex(69, 71, 90),
    md_hr_color=_hex(69, 71, 90),
)

# Registry of all available themes by name
THEMES: Dict[str, Theme] = {
    "dark": DARK_THEME,
    "light": LIGHT_THEME,
    "catppuccin": CATPPUCCIN_THEME,
}


# ══════════════════════════════════════════════════════════════════════════════
# Qt Signal for theme changes
# ══════════════════════════════════════════════════════════════════════════════

try:
    from PySide6.QtCore import QObject, Signal as _QtSignal

    class _ThemeSignalHelper(QObject):
        """Internal QObject that owns the Qt signal for theme changes.

        This is separated from ThemeManager so that ThemeManager doesn't
        need to inherit from QObject (keeping it usable in non-Qt contexts
        like headless / test mode).
        """
        theme_changed = _QtSignal(object)  # emits Theme instance

except ImportError:
    # Fallback when PySide6 is not installed (headless / CI)
    class _ThemeSignalHelper:  # type: ignore[no-redef]
        """Stub that provides .connect / .disconnect / .emit as no-ops."""
        def __init__(self):
            self._slots: List[Callable] = []
        def connect(self, slot):
            self._slots.append(slot)
        def disconnect(self, slot=None):
            if slot is None:
                self._slots.clear()
            else:
                try:
                    self._slots.remove(slot)
                except ValueError:
                    pass
        def emit(self, theme):
            for s in self._slots:
                try:
                    s(theme)
                except Exception:
                    pass


# ══════════════════════════════════════════════════════════════════════════════
# ThemeManager — singleton that holds the current theme & notifies listeners
# ══════════════════════════════════════════════════════════════════════════════

class ThemeManager:
    """Central manager for the active theme.

    Widgets can subscribe to theme changes via **two mechanisms**:

    1. **Qt signal** (preferred for QObjects)::

           theme_manager.signal.theme_changed.connect(my_widget._on_theme)

       The signal emits the new :class:`Theme` instance.

    2. **Plain callback** (for non-Qt code)::

           theme_manager.on_theme_changed(my_callback)

    Both fire when :meth:`set_theme` is called.
    """

    def __init__(self, initial: Theme = DARK_THEME) -> None:
        self._current: Theme = initial
        self._callbacks: List[Callable[[Theme], None]] = []
        # Qt signal helper — lives as long as the ThemeManager
        self._signal_helper = _ThemeSignalHelper()

    # ── Public API ──────────────────────────────────────────────────────────

    @property
    def current(self) -> Theme:
        """The currently active :class:`Theme`."""
        return self._current

    @property
    def signal(self):
        """Access the Qt ``theme_changed`` signal for ``.connect()`` / ``.disconnect()``."""
        return self._signal_helper.theme_changed

    def set_theme(self, theme: Theme) -> None:
        """Switch to *theme* and notify all registered callbacks + Qt signal."""
        if theme is self._current:
            return
        self._current = theme
        # Fire Qt signal first (so widgets can re-render via slot)
        try:
            self._signal_helper.theme_changed.emit(theme)
        except Exception:
            pass
        # Then fire plain callbacks (backward compat)
        for cb in self._callbacks:
            try:
                cb(theme)
            except Exception:
                # Never let a broken callback crash the theme switch
                import traceback
                traceback.print_exc()

    def on_theme_changed(self, callback: Callable[[Theme], None]) -> None:
        """Register *callback* to be called with the new Theme on every switch."""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[Theme], None]) -> None:
        """Unregister a previously registered callback."""
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass

    @property
    def theme_names(self) -> List[str]:
        """Return the list of available theme names."""
        return list(THEMES.keys())


# Module-level singleton
_manager = ThemeManager(DARK_THEME)

# Register C-dict sync as the first callback so it always fires
_manager.on_theme_changed(lambda t: _sync_c_dict(t))


# ══════════════════════════════════════════════════════════════════════════════
# Public convenience functions (backward-compatible API)
# ══════════════════════════════════════════════════════════════════════════════

def current_theme() -> Theme:
    """Return the currently active :class:`Theme` object."""
    return _manager.current


def current_theme_name() -> str:
    """Return the name of the currently active theme."""
    return _manager.current.name


def get_theme(name: str) -> Theme:
    """Return a :class:`Theme` by name.

    Raises
    ------
    KeyError
        If *name* is not a known theme.
    """
    if name not in THEMES:
        raise KeyError(
            f"Thème inconnu : {name!r}. Thèmes disponibles : {list(THEMES.keys())}"
        )
    return THEMES[name]


def apply_theme(app, theme_name: str) -> None:
    """Apply a theme by name to the entire application.

    Updates the global ``C`` dict, switches the ThemeManager, and emits
    the ``theme_changed`` signal so all subscribed widgets can re-render.

    Parameters
    ----------
    app : QApplication
        The Qt application instance.
    theme_name : str
        Theme name: 'dark', 'light', or 'catppuccin'.
    """
    if theme_name not in THEMES:
        return

    new_theme = THEMES[theme_name]

    # Switch the manager (notifies callbacks, including C-dict sync)
    _manager.set_theme(new_theme)

    # Regenerate and apply the global stylesheet
    stylesheet = generate_stylesheet(new_theme)
    if app is not None:
        app.setStyleSheet(stylesheet)


def on_theme_changed(callback: Callable[[Theme], None]) -> None:
    """Register a callback to be invoked whenever the theme changes."""
    _manager.on_theme_changed(callback)


def remove_theme_callback(callback: Callable[[Theme], None]) -> None:
    """Unregister a previously registered theme-changed callback."""
    _manager.remove_callback(callback)


# ══════════════════════════════════════════════════════════════════════════════
# Backward-compatible palette C (dict of CSS strings, always current)
# ══════════════════════════════════════════════════════════════════════════════

# Mapping from Theme field names to the short keys used by the old C dict
_C_KEY_MAP = {
    "bg":               "bg",
    "panel":            "panel",
    "border":           "border",
    "accent":           "accent",
    "text":             "text",
    "muted":            "muted",
    "user_bubble_g0":   "user_g0",
    "user_bubble_g1":   "user_g1",
    "asst_bubble_bg":   "asst_bg",
    "asst_bubble_border": "asst_bdr",
    "send_g0":          "send_g0",
    "send_g1":          "send_g1",
    "green":            "green",
}


def _sync_c_dict(theme: Theme) -> None:
    """Update the global ``C`` dict in-place to reflect *theme*."""
    C.clear()
    for field_name, short_key in _C_KEY_MAP.items():
        C[short_key] = getattr(theme, field_name)
    # Extra convenience keys that old code may reference
    C["input_bg"]      = theme.input_bg
    C["card_bg"]       = theme.card_bg
    C["text_secondary"] = theme.text_secondary
    C["border_light"]  = theme.border_light
    C["accent_hover"]  = theme.accent_hover
    C["btn_bg"]        = theme.btn_bg
    C["btn_hover"]     = theme.btn_hover
    C["btn_active"]    = theme.btn_active
    C["scrollbar_handle"] = theme.scrollbar_handle
    C["asst_bdr"]      = theme.asst_bubble_border   # alias already in map, but be safe


# Initialise C to the dark theme
C: Dict[str, str] = {}
_sync_c_dict(DARK_THEME)


# ══════════════════════════════════════════════════════════════════════════════
# Dynamic CSS generation
# ══════════════════════════════════════════════════════════════════════════════

def generate_scrollbar_css(t: Theme) -> str:
    """Generate scrollbar CSS for the given theme."""
    return f"""
QScrollBar:vertical {{
    width: 5px; background: {t.scrollbar_bg}; border: none;
}}
QScrollBar::handle:vertical {{
    background: {t.scrollbar_handle}; border-radius: 2px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
"""


def generate_md_css(t: Theme) -> str:
    """Generate Markdown HTML CSS for the given theme.

    This is intended for ``QTextBrowser.document().setDefaultStyleSheet()``.
    """
    return f"""
body {{
    color: {t.text}; font-family: "Arial", "Microsoft YaHei", sans-serif;
    font-size: 13px; line-height: 1.6; font-weight: 400;
}}
h1 {{
    color: {t.md_heading_color}; font-size: 20px; font-weight: 700;
    border-bottom: 1px solid {t.md_heading_border}; padding-bottom: 4px; margin-top: 16px;
}}
h2 {{
    color: {t.md_heading_color}; font-size: 17px; font-weight: 700;
    border-bottom: 1px solid {t.md_heading_border}; padding-bottom: 3px; margin-top: 14px;
}}
h3 {{
    color: {t.md_heading_color}; font-size: 15px; font-weight: 600; margin-top: 12px;
}}
h4, h5, h6 {{
    color: {t.md_heading_sub_color}; font-size: 13px; font-weight: 600; margin-top: 10px;
}}
code {{
    background: {t.md_code_bg}; color: {t.md_code_color}; padding: 1px 4px;
    border-radius: 3px; font-family: Consolas, "Courier New", monospace; font-size: 12px;
}}
pre {{
    background: {t.md_pre_bg}; border: 1px solid {t.md_pre_border}; border-radius: 6px;
    padding: 10px 12px; margin: 8px 0;
}}
pre code {{
    background: transparent; padding: 0; color: {t.md_pre_code_color};
}}
a {{ color: {t.md_link_color}; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
blockquote {{
    border-left: 3px solid {t.md_blockquote_border}; margin: 8px 0 8px 0;
    padding: 4px 0 4px 12px; color: {t.md_blockquote_color};
}}
table {{ border-collapse: collapse; margin: 8px 0; }}
th, td {{ border: 1px solid {t.md_table_border}; padding: 5px 10px; }}
th {{ background: {t.md_table_header_bg}; color: {t.md_heading_sub_color}; font-weight: 700; }}
hr {{ border: none; border-top: 1px solid {t.md_hr_color}; margin: 12px 0; }}
ul, ol {{ padding-left: 22px; margin: 4px 0; }}
li {{ margin: 2px 0; }}
p {{ margin: 6px 0; }}
"""


def generate_stylesheet(t: Theme) -> str:
    """Generate the complete Qt application stylesheet from *t*.

    This includes the global widget stylesheet, scrollbar styles, and
    any base styling that should be applied app-wide.
    """
    parts = [
        generate_scrollbar_css(t),
        # Base widget overrides that apply globally
        _base_widget_css(t),
    ]
    return "\n".join(parts)


def _base_widget_css(t: Theme) -> str:
    """Generate global base widget CSS for the given theme."""
    return f"""
QWidget {{
    background: {t.bg}; color: {t.text};
    font-family: "Arial", "Microsoft YaHei", sans-serif;
}}
QLabel {{
    background: transparent; color: {t.text};
}}
QMenu {{
    background: {t.panel}; border: 1px solid {t.border}; padding: 4px 0;
}}
QMenu::item {{
    color: {t.text}; padding: 6px 20px 6px 12px; font-size: 12px;
}}
QMenu::item:selected {{
    background: {t.accent_hover};
}}
QLineEdit {{
    background: {t.input_bg}; border: 1px solid {t.border};
    border-radius: 13px; color: {t.text}; font-size: 13px; padding: 0 10px;
}}
QLineEdit::placeholder {{
    color: {t.muted};
}}
QListWidget {{
    background: transparent; border: none; outline: none; color: {t.text};
}}
QListWidget::item {{
    color: {t.muted}; padding: 7px 10px; border-radius: 4px; margin: 1px 4px;
}}
QListWidget::item:hover {{
    background: {t.card_bg}; color: {t.text};
}}
QListWidget::item:selected {{
    background: {t.accent_hover}; color: white;
}}
QTextBrowser {{
    background: transparent; color: {t.text}; border: none;
}}
QTextEdit {{
    background: transparent; color: {t.text}; border: none;
}}
QPushButton {{
    background: transparent; color: {t.text}; border: none; border-radius: 8px;
    padding: 0 14px; font-size: 12px; font-weight: 700;
}}
QPushButton:hover {{
    background: {t.btn_hover}; color: {t.text};
}}
QScrollBar:vertical {{
    width: 5px; background: transparent; border: none;
}}
QScrollBar::handle:vertical {{
    background: {t.scrollbar_handle}; border-radius: 2px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
"""




# ══════════════════════════════════════════════════════════════════════════════
# QSS Template Integration
# ══════════════════════════════════════════════════════════════════════════════

def generate_qss(t: Theme) -> str:
    """Generate a complete QSS stylesheet from a Theme by filling a template.

    Reads the QSS template from ``assets/themes/dark.qss`` (or equivalent
    for the current theme) and replaces ``{{placeholder}}`` tokens with
    the corresponding Theme color values.

    Parameters
    ----------
    t : Theme
        The theme object whose color values will fill the template.

    Returns
    -------
    str
        The fully resolved QSS stylesheet string.
    """
    import os

    # Find the QSS template file
    template_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "assets", "themes"
    )
    template_path = os.path.join(template_dir, f"{t.name}.qss")

    # Fallback to dark.qss if the specific theme template doesn't exist
    if not os.path.isfile(template_path):
        template_path = os.path.join(template_dir, "dark.qss")

    if os.path.isfile(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            qss_template = f.read()
    else:
        # If no template file at all, fall back to programmatic generation
        return generate_stylesheet(t)

    # Build the replacement map from Theme fields
    # Map Theme attribute names to template placeholders
    placeholder_map = {
        "bg": t.bg,
        "panel": t.panel,
        "input_bg": t.input_bg,
        "card_bg": t.card_bg,
        "text": t.text,
        "text_secondary": t.text_secondary,
        "muted": t.muted,
        "border": t.border,
        "border_light": t.border_light,
        "accent": t.accent,
        "accent_hover": t.accent_hover,
        "btn_bg": t.btn_bg,
        "btn_hover": t.btn_hover,
        "btn_active": t.btn_active,
        "scrollbar_handle": t.scrollbar_handle,
        "scrollbar_bg": t.scrollbar_bg,
        "user_bubble_g0": t.user_bubble_g0,
        "user_bubble_g1": t.user_bubble_g1,
        "asst_bubble_bg": t.asst_bubble_bg,
        "asst_bubble_border": t.asst_bubble_border,
        "send_g0": t.send_g0,
        "send_g1": t.send_g1,
        "green": t.green,
        "red": t.red,
    }

    # Replace all {{placeholder}} tokens
    result = qss_template
    for key, value in placeholder_map.items():
        result = result.replace("{{" + key + "}}", value)

    return result


def apply_theme_with_qss(app, theme_name: str) -> None:
    """Apply a theme by name using the QSS template system.

    This is an enhanced version of :func:`apply_theme` that uses the
    external QSS template file when available, falling back to the
    programmatic stylesheet generator.

    Parameters
    ----------
    app : QApplication
        The Qt application instance.
    theme_name : str
        Theme name: 'dark', 'light', or 'catppuccin'.
    """
    if theme_name not in THEMES:
        return

    new_theme = THEMES[theme_name]

    # Switch the manager (notifies callbacks, including C-dict sync)
    _manager.set_theme(new_theme)

    # Generate QSS from template (falls back to programmatic if no template)
    stylesheet = generate_qss(new_theme)
    if app is not None:
        app.setStyleSheet(stylesheet)

# ══════════════════════════════════════════════════════════════════════════════
# Backward-compatible module-level constants (now generated dynamically)
# ══════════════════════════════════════════════════════════════════════════════

# These are kept for code that imports them directly.  They reflect the
# *initial* dark theme; for dynamic behaviour use generate_md_css() /
# generate_scrollbar_css() instead.

SCROLLBAR_STYLE: str = generate_scrollbar_css(DARK_THEME)
_MD_CSS: str = generate_md_css(DARK_THEME)


def md_css() -> str:
    """Return the Markdown CSS for the currently active theme."""
    return generate_md_css(current_theme())


def scrollbar_css() -> str:
    """Return the scrollbar CSS for the currently active theme."""
    return generate_scrollbar_css(current_theme())
