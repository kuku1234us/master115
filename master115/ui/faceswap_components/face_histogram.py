from typing import List, Optional

from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QPixmap, QPainterPath
from PyQt6.QtCore import Qt, QRectF

# Import helper function for avatars
from .avatar import make_round_pixmap

# Standard library import for path manipulation
import os
from pathlib import Path # Import Path

from qt_base_app.models import Logger

# Constants for drawing
X_LABEL_AREA_HEIGHT = 60 # Approximate height needed for avatar + text
Y_AXIS_WIDTH = 40       # Width needed for Y-axis labels
AVATAR_SIZE = 32        # Size of the circular avatars
TEXT_HEIGHT = 16        # Approximate height for text labels
BAR_PADDING = 10        # Padding between bars and around chart
AXIS_PEN_COLOR = QColor("#aaaaaa")
AXIS_TEXT_COLOR = QColor("#cccccc")
DEFAULT_BAR_COLOR = QColor("#3498db")
PLACEHOLDER_AVATAR_COLOR = QColor("#555555")

class FaceHistogram(QWidget):
    """Widget to display face usage counts as a simple bar histogram."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FaceHistogram")
        self.logger = Logger.instance()
        self.caller = "FaceHistogram"

        self._face_image_paths: List[str] = []
        self._counts: List[int] = []

        # Define fonts reused in painting
        self._axis_font = QFont()
        self._axis_font.setPointSize(8)
        self._xlabel_font = QFont()
        self._xlabel_font.setPointSize(7)

        # Allow the widget to expand vertically and horizontally
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Increase minimum height to accommodate labels
        self.setMinimumSize(200, 150 + X_LABEL_AREA_HEIGHT) 

        # Basic styling for border/background
        self.setAutoFillBackground(True)
        self.setStyleSheet("""
            QWidget#FaceHistogram {
                border: 1px dashed #888888;
                background-color: rgba(0, 0, 0, 0.1);
            }
        """)

    def set_data(self, face_image_paths: List[str], counts: List[int]):
        """Sets the data for the histogram and triggers a repaint."""
        if len(face_image_paths) != len(counts):
            self.logger.error(self.caller, f"Data length mismatch: {len(face_image_paths)} paths vs {len(counts)} counts.")
            self._face_image_paths = []
            self._counts = []
        else:
            self.logger.debug(self.caller, f"Setting histogram data with {len(counts)} items.")
            self._face_image_paths = face_image_paths
            self._counts = counts
        
        # Trigger a repaint to reflect the new data or cleared state
        self.update()

    def paintEvent(self, event):
        """Draws the histogram or a placeholder message."""
        super().paintEvent(event) # Handle background etc.
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._counts: # Draw placeholder if no data
            self._draw_placeholder(painter)
        else:
            # Draw chart components
            self._draw_axes(painter)
            self._draw_bars(painter)
            self._draw_x_labels(painter) # Draw labels last (potentially overlapping axes slightly)

    def _draw_placeholder(self, painter: QPainter):
        """Draws the placeholder text centered in the widget."""
        painter.setPen(QColor("#aaaaaa"))
        font = QFont()
        font.setPointSize(10)
        font.setItalic(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 
                         "Select a person above to view usage statistics.")

    def _draw_bars(self, painter: QPainter):
        """Draws simple vertical bars based on the counts."""
        if not self._counts:
            return

        num_bars = len(self._counts)
        max_count = max(self._counts) if self._counts else 1
        
        # Define drawing area, accounting for axes and labels
        # Top padding, bottom padding reserved for X labels
        draw_area_y = BAR_PADDING 
        draw_area_height = self.height() - X_LABEL_AREA_HEIGHT - BAR_PADDING
        # Left padding reserved for Y axis, right padding
        draw_area_x = Y_AXIS_WIDTH 
        draw_area_width = self.width() - Y_AXIS_WIDTH - BAR_PADDING
        
        if draw_area_height <= 0 or draw_area_width <= 0:
            self.logger.warn(self.caller, "Not enough space to draw bars.")
            return
            
        # Calculate bar width and spacing (simple even distribution)
        total_spacing = BAR_PADDING * (num_bars - 1)
        bar_width = (draw_area_width - total_spacing) / num_bars if num_bars > 0 else draw_area_width
        bar_spacing = BAR_PADDING # Use padding as spacing for now

        if bar_width <= 0: # Prevent errors if width calculation fails
             self.logger.warn(self.caller, "Calculated bar width is zero or negative. Cannot draw bars.")
             return

        # Base Y position (bottom of the bar drawing area)
        base_y = draw_area_y + draw_area_height

        # Bar color (adjust with theme later)
        painter.setBrush(DEFAULT_BAR_COLOR)
        painter.setPen(Qt.PenStyle.NoPen) # No border around bars

        current_x = draw_area_x
        for count in self._counts:
            # Calculate bar height (proportional to max_count)
            bar_height = (count / max_count) * draw_area_height if max_count > 0 else 0
            # Bar Y position starts from the base and goes up
            bar_y = base_y - bar_height 
            
            # Draw the rectangle for the bar
            painter.drawRect(int(current_x), int(bar_y), int(bar_width), int(bar_height))
            
            # Move to the next bar position
            current_x += bar_width + bar_spacing

    def _draw_axes(self, painter: QPainter):
        """Draws the X and Y axis lines and basic Y labels."""
        if not self._counts:
            return
        
        painter.setPen(QPen(AXIS_PEN_COLOR, 1)) # Set pen for axes
        painter.setFont(self._axis_font)

        # Define axis coordinates based on drawing area
        x_axis_y = self.height() - X_LABEL_AREA_HEIGHT
        y_axis_x = Y_AXIS_WIDTH
        chart_top_y = BAR_PADDING
        chart_right_x = self.width() - BAR_PADDING

        # Draw Y axis line
        painter.drawLine(y_axis_x, chart_top_y, y_axis_x, x_axis_y)
        # Draw X axis line (baseline for bars)
        painter.drawLine(y_axis_x, x_axis_y, chart_right_x, x_axis_y)

        # Draw Y axis labels (Min and Max counts)
        max_count = max(self._counts)
        min_count = 0 # Assuming counts are non-negative
        
        painter.setPen(AXIS_TEXT_COLOR) # Switch pen for text
        # Max label (top)
        painter.drawText(QRectF(0, chart_top_y - TEXT_HEIGHT / 2, Y_AXIS_WIDTH - 5, TEXT_HEIGHT), 
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(max_count))
        # Min label (bottom)
        painter.drawText(QRectF(0, x_axis_y - TEXT_HEIGHT / 2, Y_AXIS_WIDTH - 5, TEXT_HEIGHT), 
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(min_count))
        # TODO: Add intermediate Y-axis labels if needed

    def _draw_x_labels(self, painter: QPainter):
        """Draws the avatars and face stems below the X axis."""
        if not self._counts or not self._face_image_paths:
            return
            
        num_bars = len(self._counts)
        # Recalculate bar width/spacing as needed (same logic as _draw_bars)
        draw_area_x = Y_AXIS_WIDTH
        draw_area_width = self.width() - Y_AXIS_WIDTH - BAR_PADDING
        total_spacing = BAR_PADDING * (num_bars - 1)
        bar_width = (draw_area_width - total_spacing) / num_bars if num_bars > 0 else draw_area_width
        bar_spacing = BAR_PADDING
        
        if bar_width <= 0: return # Cannot draw labels if bars aren't drawn

        # Y position for the top of the avatars
        avatar_y = self.height() - X_LABEL_AREA_HEIGHT + BAR_PADDING // 2 
        # Y position for the text baseline (approx)
        text_y = avatar_y + AVATAR_SIZE + BAR_PADDING // 2

        current_x_center = draw_area_x + bar_width / 2
        painter.setFont(self._xlabel_font)
        painter.setPen(AXIS_TEXT_COLOR)
        
        for i, img_path in enumerate(self._face_image_paths):
            # 1. Draw Avatar
            avatar_x = current_x_center - AVATAR_SIZE / 2
            try:
                # Load original pixmap
                original_pixmap = QPixmap(img_path)
                if original_pixmap.isNull():
                    raise ValueError("Failed to load pixmap")
                # Create rounded avatar
                avatar_pixmap = make_round_pixmap(original_pixmap, AVATAR_SIZE)
                painter.drawPixmap(int(avatar_x), int(avatar_y), avatar_pixmap)
            except Exception as e:
                # Draw placeholder on error
                # self.logger.warn(self.caller, f"Error loading avatar for {img_path}: {e}")
                painter.setBrush(PLACEHOLDER_AVATAR_COLOR)
                painter.setPen(Qt.PenStyle.NoPen)
                path = QPainterPath()
                path.addEllipse(QRectF(avatar_x, avatar_y, AVATAR_SIZE, AVATAR_SIZE))
                painter.drawPath(path)
                painter.setBrush(Qt.BrushStyle.NoBrush) # Reset brush
                painter.setPen(AXIS_TEXT_COLOR) # Reset pen for text

            # 2. Draw Text (Face Stem)
            face_stem = Path(img_path).stem # Get filename without extension
            text_rect = QRectF(current_x_center - bar_width*1.5 / 2, text_y, bar_width*1.5, TEXT_HEIGHT)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop, face_stem)
            
            # Move to the center of the next bar position
            current_x_center += bar_width + bar_spacing

    # def _draw_axes(self, painter: QPainter):
    #     # Draw Y-axis, X-axis baseline
    #     pass

    # def _draw_x_labels(self, painter: QPainter):
    #     # Draw avatars and names (Milestone 3)
    #     pass 