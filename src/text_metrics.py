"""
Text metrics calculation utilities for accurate bounding box computation.
"""

from typing import Tuple, List, Dict, Optional
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from PIL import Image, ImageDraw, ImageFont
import logging

logger = logging.getLogger(__name__)


class TextMetrics:
    """Calculate accurate text metrics for both PDF and PIL rendering."""
    
    @staticmethod
    def get_pdf_text_bbox(canvas_obj: canvas.Canvas, 
                         text: str, 
                         font_name: str, 
                         font_size: float) -> Dict[str, float]:
        """
        Get accurate text bounding box for PDF rendering.
        
        Returns dict with:
        - width: text width in points
        - height: total height including ascent and descent
        - ascent: height above baseline
        - descent: depth below baseline (negative value)
        """
        # Set the font to get accurate metrics
        canvas_obj.setFont(font_name, font_size)
        
        # Get text width
        width = canvas_obj.stringWidth(text, font_name, font_size)
        
        # Get font metrics
        face = pdfmetrics.getFont(font_name).face
        ascent = (face.ascent / 1000.0) * font_size
        descent = (face.descent / 1000.0) * font_size  # This is negative
        
        # Total height is ascent minus descent (since descent is negative)
        height = ascent - descent
        
        return {
            'width': width,
            'height': height,
            'ascent': ascent,
            'descent': descent
        }
    
    @staticmethod
    def get_pil_text_bbox(draw: ImageDraw.Draw,
                         text: str,
                         font: ImageFont.FreeTypeFont) -> Tuple[int, int, int, int]:
        """
        Get accurate text bounding box for PIL rendering.
        
        Returns (left, top, right, bottom) in pixels.
        """
        # Use textbbox for accurate bounding box
        # Starting at (0, 0) to get relative dimensions
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox
    
    @staticmethod
    def calculate_multiline_bbox(canvas_obj: canvas.Canvas,
                               lines: List[str],
                               font_name: str,
                               font_size: float,
                               line_spacing: float = 1.2) -> Dict[str, float]:
        """
        Calculate bounding box for multiple lines of text.
        
        Args:
            lines: List of text lines
            font_name: Font name
            font_size: Font size in points
            line_spacing: Line spacing multiplier (1.2 = 120% of font size)
            
        Returns dict with:
            - width: Maximum width across all lines
            - height: Total height of all lines
            - line_bboxes: List of bounding boxes for each line
        """
        if not lines:
            return {'width': 0, 'height': 0, 'line_bboxes': []}
        
        max_width = 0
        total_height = 0
        line_bboxes = []
        
        # Get metrics for first line to establish baseline
        first_bbox = TextMetrics.get_pdf_text_bbox(canvas_obj, lines[0], font_name, font_size)
        
        for i, line in enumerate(lines):
            bbox = TextMetrics.get_pdf_text_bbox(canvas_obj, line, font_name, font_size)
            line_bboxes.append(bbox)
            max_width = max(max_width, bbox['width'])
            
            if i == 0:
                # First line - use actual height
                total_height = bbox['height']
            else:
                # Subsequent lines - add line spacing
                total_height += font_size * line_spacing
        
        return {
            'width': max_width,
            'height': total_height,
            'line_bboxes': line_bboxes
        }
    
    @staticmethod
    def will_text_fit(canvas_obj: canvas.Canvas,
                     lines: List[str],
                     font_name: str,
                     font_size: float,
                     max_width: float,
                     max_height: float,
                     line_spacing: float = 1.2) -> bool:
        """
        Check if text will fit within given bounds without clipping.
        """
        bbox = TextMetrics.calculate_multiline_bbox(
            canvas_obj, lines, font_name, font_size, line_spacing
        )
        
        return bbox['width'] <= max_width and bbox['height'] <= max_height
    
    @staticmethod
    def get_optimal_font_size(canvas_obj: canvas.Canvas,
                            lines: List[str],
                            font_name: str,
                            max_width: float,
                            max_height: float,
                            min_size: float = 4,
                            max_size: float = 72,
                            line_spacing: float = 1.2) -> float:
        """
        Find the largest font size that fits within bounds.
        """
        # Binary search for optimal size
        low, high = min_size, max_size
        best_size = min_size
        
        while low <= high:
            mid = (low + high) / 2
            
            if TextMetrics.will_text_fit(canvas_obj, lines, font_name, mid, 
                                        max_width, max_height, line_spacing):
                best_size = mid
                low = mid + 0.5  # Try larger
            else:
                high = mid - 0.5  # Try smaller
        
        return best_size