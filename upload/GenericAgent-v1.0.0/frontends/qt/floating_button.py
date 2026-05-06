"""
Bouton flottant animé — Point d'entrée visuel de l'interface GenericAgent.
Extrait de qtapp.py pour la refonte modulaire.
"""
from __future__ import annotations

import math
import time as _time

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QTimer, QPoint, QPointF, QDateTime
from PySide6.QtGui import (
    QPainter, QColor, QLinearGradient, QRadialGradient,
    QPen, QPainterPath, QCursor,
)


class FloatingButton(QWidget):
    """Bouton circulaire flottant avec animation de glow et icône robot.
    
    Sizes are DPI-aware: they scale with the device pixel ratio.
    """

    BASE_SIZE = 60       # base circle diameter at 1x scale
    BASE_MARGIN = 14     # base extra space for glow at 1x scale
    
    @property
    def SIZE(self):
        """DPI-scaled circle diameter."""
        scale = self.devicePixelRatio() if hasattr(self, 'devicePixelRatio') else 1.0
        return int(self.BASE_SIZE * max(1.0, scale * 0.7 + 0.3))  # gentle scaling
    
    @property
    def MARGIN(self):
        """DPI-scaled margin for glow."""
        scale = self.devicePixelRatio() if hasattr(self, 'devicePixelRatio') else 1.0
        return int(self.BASE_MARGIN * max(1.0, scale * 0.7 + 0.3))
    
    @property
    def TOTAL(self):
        """Total widget size (SIZE + 2*MARGIN)."""
        return self.SIZE + self.MARGIN * 2

    # Seconds of agent inactivity before pausing the animation timer.
    _INACTIVITY_PAUSE_S: float = 30.0

    def __init__(self, chat_panel: QWidget):
        super().__init__()
        self.chat_panel = chat_panel
        self._drag_origin_global: QPoint | None = None
        self._drag_origin_win: QPoint | None = None
        self._dragged = False
        self._glow = 0.5
        self._glow_dir = 1
        self._hovering = False
        self._hover_clock = 0.0
        self._hover_strength = 0.0
        self._flow_phase = 0.0
        self._running = False
        self._last_toggle_ms = 0  # debounce timestamp
        self._last_active_time: float = _time.monotonic()  # last time agent was active
        self._timer_paused: bool = False  # True when animation timer is stopped for inactivity

        # Window flags: frameless, always on top, no taskbar entry
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        # Use base sizes for fixed widget size (Qt handles DPI scaling)
        self.setFixedSize(self.BASE_SIZE + self.BASE_MARGIN * 2, self.BASE_SIZE + self.BASE_MARGIN * 2)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        # Smooth animation (~30 fps)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

        # Default position: bottom-right of the work area
        scr = QApplication.primaryScreen().availableGeometry()
        total = self.BASE_SIZE + self.BASE_MARGIN * 2
        self.move(scr.right() - total - 20, scr.bottom() - total - 20)

    # ── Animation ────────────────────────────────────────
    def _tick(self):
        # running status: green when model is actively responding
        self._running = bool(
            getattr(self.chat_panel, "_is_streaming", False)
            or getattr(getattr(self.chat_panel, "agent", None), "is_running", False)
        )

        # Track last active time (agent running or user hovering)
        if self._running or self._hovering:
            self._last_active_time = _time.monotonic()

        # Pause timer when hidden or inactive to save CPU/battery
        if not self.isVisible():
            if not self._timer_paused:
                self._timer.stop()
                self._timer_paused = True
            return

        if self._timer_paused:
            # Resume — timer was paused; restart it
            self._timer.start(33)
            self._timer_paused = False

        # Check inactivity — pause if idle for too long
        elapsed_inactive = _time.monotonic() - self._last_active_time
        if elapsed_inactive > self._INACTIVITY_PAUSE_S and not self._hovering:
            self._timer.stop()
            self._timer_paused = True
            return

        self._glow += self._glow_dir * 0.04
        if self._glow >= 1.0:
            self._glow, self._glow_dir = 1.0, -1
        elif self._glow <= 0.0:
            self._glow, self._glow_dir = 0.0, 1

        target = 1.0 if self._hovering else 0.0
        self._hover_strength += (target - self._hover_strength) * 0.20
        self._hover_clock += 0.033
        self._flow_phase += 0.16 + (0.06 if self._running else 0.0) + (0.05 if self._hovering else 0.0)
        self.update()

    # ── Painting ──────────────────────────────────────────
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        m = self.MARGIN
        r = self.SIZE // 2
        cx = m + r
        # Rhythmic spring bounce: one main hop + one lighter rebound per beat.
        beat_t = self._hover_clock % 1.18
        spring = 0.0
        if beat_t < 0.70:
            spring += max(0.0, math.exp(-5.2 * beat_t) * math.sin(15.5 * beat_t))
        if beat_t > 0.20:
            rt = beat_t - 0.20
            spring += 0.52 * max(0.0, math.exp(-7.0 * rt) * math.sin(21.0 * rt))
        idle_sway = 0.20 * math.sin(self._hover_clock * 2.1)
        bounce = int(round((spring * 7.2 + idle_sway) * self._hover_strength))
        cy = m + r - bounce

        if self._running:
            # running: #2DFFF5 -> #FFF878
            g0 = QColor(45, 255, 245, 195)
            g1 = QColor(255, 248, 120, 195)
            glow_rgb = (96, 255, 216)
        else:
            # idle: #103CE7 -> #64E9FF
            g0 = QColor(16, 60, 231, 195)
            g1 = QColor(100, 233, 255, 195)
            glow_rgb = (74, 170, 255)

        # --- Outer glow rings (3 layers) ---
        base_alpha = int(45 + 25 * self._glow)
        for i, gr in enumerate([r + 10, r + 6, r + 2]):
            g = QRadialGradient(QPointF(cx, cy), gr)
            g.setColorAt(0.0, QColor(glow_rgb[0], glow_rgb[1], glow_rgb[2], max(0, base_alpha - i * 14)))
            g.setColorAt(1.0, QColor(glow_rgb[0], glow_rgb[1], glow_rgb[2], 0))
            p.setBrush(g)
            p.setPen(Qt.NoPen)
            p.drawEllipse(int(cx - gr), int(cy - gr), int(gr * 2), int(gr * 2))

        # --- Frosted glass disc behind main circle ---
        frost = QRadialGradient(QPointF(cx, cy), r)
        frost.setColorAt(0.0, QColor(30, 30, 45, 140))
        frost.setColorAt(0.85, QColor(20, 20, 32, 160))
        frost.setColorAt(1.0, QColor(14, 14, 20, 100))
        p.setBrush(frost)
        p.setPen(Qt.NoPen)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # --- Main circle (flowing state gradient) ---
        spin = self._flow_phase
        dx = math.cos(spin) * r
        dy = math.sin(spin) * r
        grad = QLinearGradient(cx - dx, cy - dy, cx + dx, cy + dy)
        grad.setColorAt(0.0, g0)
        grad.setColorAt(1.0, g1)
        p.setBrush(grad)
        p.setPen(QPen(QColor(255, 255, 255, 50), 1.5))
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # --- Flowing glass streaks ---
        clip = QPainterPath()
        clip.addEllipse(float(cx - r), float(cy - r), float(r * 2), float(r * 2))
        p.setClipPath(clip)

        flow_shift = math.sin(self._flow_phase * 0.85) * (r * 0.7)
        streak1 = QLinearGradient(cx - r + flow_shift, cy - r, cx + r + flow_shift, cy + r)
        streak1.setColorAt(0.00, QColor(255, 255, 255, 0))
        streak1.setColorAt(0.45, QColor(255, 255, 255, 42))
        streak1.setColorAt(0.52, QColor(255, 255, 255, 78))
        streak1.setColorAt(0.60, QColor(255, 255, 255, 24))
        streak1.setColorAt(1.00, QColor(255, 255, 255, 0))
        p.setBrush(streak1)
        p.setPen(Qt.NoPen)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        flow_shift_2 = math.cos(self._flow_phase * 1.2) * (r * 0.5)
        streak2 = QLinearGradient(cx - r, cy + flow_shift_2, cx + r, cy - flow_shift_2)
        streak2.setColorAt(0.00, QColor(255, 255, 255, 0))
        streak2.setColorAt(0.35, QColor(255, 255, 255, 16))
        streak2.setColorAt(0.50, QColor(255, 255, 255, 46))
        streak2.setColorAt(0.65, QColor(255, 255, 255, 16))
        streak2.setColorAt(1.00, QColor(255, 255, 255, 0))
        p.setBrush(streak2)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # --- Top highlight ---
        hl = QLinearGradient(cx, cy - r, cx, cy)
        hl.setColorAt(0.0, QColor(255, 255, 255, 72))
        hl.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(hl)
        p.drawRect(cx - r, cy - r, r * 2, r)
        p.setClipping(False)

        # --- Bot icon ---
        p.setPen(QPen(QColor(255, 255, 255, 220), 1.8))
        p.setBrush(Qt.NoBrush)
        # Head
        p.drawRoundedRect(cx - 9, cy - 6, 18, 12, 2, 2)
        # Eyes
        p.setBrush(QColor(255, 255, 255, 220))
        p.setPen(Qt.NoPen)
        p.drawEllipse(cx - 6, cy - 3, 4, 4)
        p.drawEllipse(cx + 2, cy - 3, 4, 4)
        # Antenna stem
        p.setPen(QPen(QColor(255, 255, 255, 220), 1.8))
        p.drawLine(cx, cy - 6, cx, cy - 10)
        # Antenna tip
        p.setBrush(QColor(255, 255, 255, 190))
        p.setPen(Qt.NoPen)
        p.drawEllipse(cx - 2, cy - 13, 4, 4)

    # ── Visibility / hover — resume animation when needed ──
    def showEvent(self, event):
        """Resume animation timer when the button becomes visible."""
        super().showEvent(event)
        if self._timer_paused:
            self._last_active_time = _time.monotonic()
            self._timer.start(33)
            self._timer_paused = False

    def hideEvent(self, event):
        """Pause animation timer when the button is hidden."""
        super().hideEvent(event)
        if not self._timer_paused:
            self._timer.stop()
            self._timer_paused = True

    def enterEvent(self, event):
        self._hovering = True
        self._last_active_time = _time.monotonic()
        # Resume animation if it was paused for inactivity
        if self._timer_paused and self.isVisible():
            self._timer.start(33)
            self._timer_paused = False
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovering = False
        self.update()
        super().leaveEvent(event)

    # ── Mouse events (drag + click) ───────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_origin_global = event.globalPosition().toPoint()
            self._drag_origin_win = self.pos()
            self._dragged = False

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_origin_global:
            delta = event.globalPosition().toPoint() - self._drag_origin_global
            if abs(delta.x()) > 5 or abs(delta.y()) > 5:
                self._dragged = True
            if self._dragged:
                new = self._drag_origin_win + delta
                scr = QApplication.primaryScreen().availableGeometry()
                new.setX(max(scr.left(), min(new.x(), scr.right() - self.width())))
                new.setY(max(scr.top(), min(new.y(), scr.bottom() - self.height())))
                self.move(new)

    def mouseDoubleClickEvent(self, event):
        # Qt sends Press->Release->DoubleClick->Release on double-click.
        # The first Release already toggled the panel; swallow the DoubleClick
        # so the second Release does NOT trigger a second toggle.
        self._dragged = True   # mark as "dragged" -> Release will be ignored
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self._dragged:
                self._toggle()
            self._dragged = False
        self._drag_origin_global = None

    # ── Toggle panel ──────────────────────────────────────
    def _toggle(self):
        now = QDateTime.currentMSecsSinceEpoch()
        if now - self._last_toggle_ms < 500:   # 500 ms debounce
            return
        self._last_toggle_ms = now

        if self.chat_panel.isVisible():
            self.chat_panel.hide()
        else:
            self._position_panel()
            self.chat_panel.show()
            self.chat_panel.raise_()
            self.chat_panel.activateWindow()

    def _position_panel(self):
        scr = QApplication.primaryScreen().availableGeometry()
        btn = self.geometry()
        pw = self.chat_panel.width()
        ph = self.chat_panel.height()
        # Prefer left of button, bottom-aligned
        x = btn.left() - pw - 12
        y = btn.bottom() - ph
        x = max(scr.left() + 10, min(x, scr.right() - pw - 10))
        y = max(scr.top() + 10, min(y, scr.bottom() - ph - 10))
        self.chat_panel.move(x, y)
