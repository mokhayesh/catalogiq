# =====================================================================
#  LoadingOverlay — Fullscreen Loading Spinner Overlay
#  FIXED FOR wxPython 4.2.1 + Python 3.13
# =====================================================================

import wx
import threading
import time


class LoadingOverlay(wx.Frame):
    """
    A semi-transparent overlay with a loading message.
    Safe to call from worker threads using .start() and .stop().
    """

    def __init__(self, parent, message="Loading…"):
        style = wx.FRAME_NO_TASKBAR | wx.STAY_ON_TOP | wx.FRAME_SHAPED
        super().__init__(parent, style=style)

        self.parent = parent
        self.message = message
        self._running = False

        # ✅ Required for AutoBufferedPaintDC
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        # No border, transparent-style
        self.SetTransparent(210)

        # Timer for spinner animation
        self._angle = 0
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_timer, self._timer)

        # Paint event
        self.Bind(wx.EVT_PAINT, self._on_paint)

    # =================================================================
    # START OVERLAY
    # =================================================================

    def start(self):
        """Safe to call from worker thread."""
        if self._running:
            return

        self._running = True
        wx.CallAfter(self._show_overlay)

    def _show_overlay(self):
        # Match parent full-screen size
        parent_pos = self.parent.ClientToScreen((0, 0))
        parent_size = self.parent.GetSize()
        self.SetPosition(parent_pos)
        self.SetSize(parent_size)

        self.Show(True)
        self._timer.Start(50)

    # =================================================================
    # STOP OVERLAY
    # =================================================================

    def stop(self):
        """Safe to call from worker thread."""
        if not self._running:
            return
        self._running = False
        wx.CallAfter(self._hide_overlay)

    def _hide_overlay(self):
        if self._timer.IsRunning():
            self._timer.Stop()
        self.Hide()

    # =================================================================
    # TIMER UPDATE (spinner animation)
    # =================================================================

    def _on_timer(self, _):
        self._angle = (self._angle + 10) % 360
        self.Refresh(False)

    # =================================================================
    # PAINT EVENT
    # =================================================================

    def _on_paint(self, _):
        # ✅ AutoBufferedPaintDC requires BG_STYLE_PAINT
        dc = wx.AutoBufferedPaintDC(self)
        w, h = self.GetClientSize()

        # Semi-transparent dark background
        dc.SetBrush(wx.Brush(wx.Colour(20, 20, 20, 190)))
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.DrawRectangle(0, 0, w, h)

        # Spinner
        dc.SetPen(wx.Pen(wx.Colour(255, 255, 255), 6))
        radius = 28
        center = (w // 2, h // 2 - 40)

        # Draw spinning arc
        dc.DrawArc(
            center[0] + radius, center[1],
            center[0] - radius, center[1],
            center[0], center[1] + radius
        )

        # Message text
        dc.SetTextForeground(wx.Colour(255, 255, 255))
        dc.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))

        tw, th = dc.GetTextExtent(self.message)
        dc.DrawText(self.message, (w - tw) // 2, h // 2 + 10)
