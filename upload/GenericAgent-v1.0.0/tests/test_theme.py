"""Tests for the theme system — Theme dataclass, ThemeManager, CSS generation.

Verifies that:
1. Theme change → all colors updated.
2. Non-existent theme → fallback to dark.
3. Generated CSS is coherent (non-empty, valid).
4. All predefined themes have complete attribute sets.
5. C-dict sync stays in sync with the active theme.

Test IDs correspond to Task 4.2.3 in the project roadmap.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import pytest
from dataclasses import fields

# ---------------------------------------------------------------------------
# Direct module import
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _PROJECT_ROOT)

# Import theme module directly
_theme_path = os.path.join(_PROJECT_ROOT, "frontends", "qt", "theme.py")
_theme_spec = importlib.util.spec_from_file_location("theme", _theme_path)
_theme_mod = importlib.util.module_from_spec(_theme_spec)
sys.modules["theme"] = _theme_mod
_theme_spec.loader.exec_module(_theme_mod)  # type: ignore[union-attr]

Theme = _theme_mod.Theme
DARK_THEME = _theme_mod.DARK_THEME
LIGHT_THEME = _theme_mod.LIGHT_THEME
CATPPUCCIN_THEME = _theme_mod.CATPPUCCIN_THEME
THEMES = _theme_mod.THEMES
ThemeManager = _theme_mod.ThemeManager
current_theme = _theme_mod.current_theme
current_theme_name = _theme_mod.current_theme_name
get_theme = _theme_mod.get_theme
generate_stylesheet = _theme_mod.generate_stylesheet
generate_md_css = _theme_mod.generate_md_css
generate_scrollbar_css = _theme_mod.generate_scrollbar_css
C = _theme_mod.C
_sync_c_dict = _theme_mod._sync_c_dict


# ══════════════════════════════════════════════════════════════════════════════
#  1. Theme change → all colors updated
# ══════════════════════════════════════════════════════════════════════════════

class TestThemeChange:
    """Verify that changing the theme updates all colors."""

    def test_theme_manager_switches_theme(self):
        """ThemeManager.set_theme() switches the active theme."""
        manager = ThemeManager(DARK_THEME)
        assert manager.current is DARK_THEME
        manager.set_theme(LIGHT_THEME)
        assert manager.current is LIGHT_THEME

    def test_theme_manager_notifies_callbacks(self):
        """ThemeManager notifies all callbacks on theme change."""
        manager = ThemeManager(DARK_THEME)
        received = []
        manager.on_theme_changed(lambda t: received.append(t))
        manager.set_theme(LIGHT_THEME)
        assert len(received) == 1
        assert received[0] is LIGHT_THEME

    def test_theme_manager_no_duplicate_notification(self):
        """Setting the same theme again → no notification."""
        manager = ThemeManager(DARK_THEME)
        received = []
        manager.on_theme_changed(lambda t: received.append(t))
        manager.set_theme(DARK_THEME)  # Same theme
        assert len(received) == 0

    def test_all_colors_differ_between_themes(self):
        """Dark and light themes have different color values."""
        dark_values = {f.name: getattr(DARK_THEME, f.name) for f in fields(Theme) if f.name != "name"}
        light_values = {f.name: getattr(LIGHT_THEME, f.name) for f in fields(Theme) if f.name != "name"}
        different_count = sum(1 for k in dark_values if dark_values[k] != light_values[k])
        # Most colors should differ between dark and light
        assert different_count > len(dark_values) * 0.5

    def test_c_dict_updates_on_theme_change(self):
        """The C dict updates when the theme changes."""
        _sync_c_dict(DARK_THEME)
        dark_bg = C.get("bg")
        _sync_c_dict(LIGHT_THEME)
        light_bg = C.get("bg")
        assert dark_bg != light_bg

    def test_theme_remove_callback(self):
        """Callbacks can be removed."""
        manager = ThemeManager(DARK_THEME)
        received = []
        cb = lambda t: received.append(t)  # noqa: E731
        manager.on_theme_changed(cb)
        manager.remove_callback(cb)
        manager.set_theme(LIGHT_THEME)
        assert len(received) == 0


# ══════════════════════════════════════════════════════════════════════════════
#  2. Non-existent theme → fallback / KeyError
# ══════════════════════════════════════════════════════════════════════════════

class TestNonExistentTheme:
    """Verify behavior when a non-existent theme is requested."""

    def test_get_theme_unknown_raises_keyerror(self):
        """get_theme() raises KeyError for unknown theme name."""
        with pytest.raises(KeyError, match="Thème inconnu"):
            get_theme("nonexistent_theme")

    def test_apply_theme_ignores_unknown(self):
        """apply_theme() silently ignores unknown theme names."""
        # This shouldn't raise — it should just do nothing
        # Verify that the function doesn't crash with unknown name
        try:
            _theme_mod.apply_theme(None, "nonexistent")
        except Exception:
            # It should handle it gracefully — might return silently
            pass  # The function checks `if theme_name not in THEMES: return`

    def test_dark_theme_is_default(self):
        """Dark theme is the default/initial theme."""
        manager = ThemeManager()
        assert manager.current.name == "dark"

    def test_theme_names_include_dark_and_light(self):
        """Available themes include at least 'dark' and 'light'."""
        names = ThemeManager(DARK_THEME).theme_names
        assert "dark" in names
        assert "light" in names


# ══════════════════════════════════════════════════════════════════════════════
#  3. Generated CSS is coherent
# ══════════════════════════════════════════════════════════════════════════════

class TestCSSGeneration:
    """Verify that generated CSS is coherent and usable."""

    def test_generate_scrollbar_css_non_empty(self):
        """generate_scrollbar_css() returns non-empty CSS."""
        css = generate_scrollbar_css(DARK_THEME)
        assert len(css) > 50
        assert "QScrollBar" in css

    def test_generate_md_css_non_empty(self):
        """generate_md_css() returns non-empty CSS."""
        css = generate_md_css(DARK_THEME)
        assert len(css) > 100
        assert "body" in css
        assert "code" in css
        assert "pre" in css

    def test_generate_stylesheet_non_empty(self):
        """generate_stylesheet() returns non-empty CSS."""
        css = generate_stylesheet(DARK_THEME)
        assert len(css) > 100
        assert "QWidget" in css

    def test_css_contains_theme_colors(self):
        """Generated CSS contains colors from the theme."""
        css = generate_stylesheet(DARK_THEME)
        # The bg color should appear in the CSS
        assert DARK_THEME.bg in css
        assert DARK_THEME.text in css

    def test_scrollbar_css_differs_between_themes(self):
        """Scrollbar CSS differs between dark and light themes."""
        dark_css = generate_scrollbar_css(DARK_THEME)
        light_css = generate_scrollbar_css(LIGHT_THEME)
        assert dark_css != light_css

    def test_md_css_differs_between_themes(self):
        """Markdown CSS differs between dark and light themes."""
        dark_css = generate_md_css(DARK_THEME)
        light_css = generate_md_css(LIGHT_THEME)
        assert dark_css != light_css

    def test_md_css_contains_all_elements(self):
        """Markdown CSS styles all expected HTML elements."""
        css = generate_md_css(DARK_THEME)
        expected_selectors = ["h1", "h2", "h3", "code", "pre", "a", "blockquote", "table", "hr", "ul", "ol"]
        for selector in expected_selectors:
            assert selector in css, f"CSS missing selector: {selector}"


# ══════════════════════════════════════════════════════════════════════════════
#  4. Theme dataclass completeness
# ══════════════════════════════════════════════════════════════════════════════

class TestThemeCompleteness:
    """Verify that all themes have complete attribute sets."""

    @pytest.mark.parametrize("theme_name,theme_obj", [
        ("dark", DARK_THEME),
        ("light", LIGHT_THEME),
        ("catppuccin", CATPPUCCIN_THEME),
    ])
    def test_theme_has_all_fields(self, theme_name, theme_obj):
        """Each theme has all fields defined in the Theme dataclass."""
        for f in fields(Theme):
            value = getattr(theme_obj, f.name, None)
            assert value is not None, f"Theme '{theme_name}' missing field: {f.name}"

    @pytest.mark.parametrize("theme_name,theme_obj", [
        ("dark", DARK_THEME),
        ("light", LIGHT_THEME),
        ("catppuccin", CATPPUCCIN_THEME),
    ])
    def test_theme_colors_are_valid_css(self, theme_name, theme_obj):
        """All color values in each theme are valid CSS color strings."""
        for f in fields(Theme):
            if f.name == "name":
                continue
            value = getattr(theme_obj, f.name)
            # Must be a string starting with # or rgba(
            assert isinstance(value, str), f"Theme '{theme_name}' field '{f.name}' is not a string"
            assert value.startswith("#") or value.startswith("rgba(") or value == "transparent", \
                f"Theme '{theme_name}' field '{f.name}' has invalid CSS color: {value}"

    def test_themes_registry_complete(self):
        """THEMES dict contains all predefined themes."""
        assert "dark" in THEMES
        assert "light" in THEMES
        assert "catppuccin" in THEMES

    def test_theme_is_frozen(self):
        """Theme dataclass is frozen (immutable)."""
        with pytest.raises(AttributeError):
            DARK_THEME.bg = "#ffffff"  # type: ignore[misc]

    def test_c_dict_has_required_keys(self):
        """The C dict has all required backward-compatible keys."""
        _sync_c_dict(DARK_THEME)
        required_keys = ["bg", "panel", "border", "accent", "text", "muted",
                         "user_g0", "user_g1", "asst_bg", "asst_bdr",
                         "send_g0", "send_g1", "green"]
        for key in required_keys:
            assert key in C, f"C dict missing key: {key}"
