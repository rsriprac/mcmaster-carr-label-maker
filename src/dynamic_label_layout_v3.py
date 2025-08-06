"""
Dynamic label layout engine v3 with proper text bounding box calculations.
"""

from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import math

from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from PIL import Image, ImageDraw, ImageFont
import logging

from .text_metrics import TextMetrics

logger = logging.getLogger(__name__)


@dataclass
class LayoutDimensions:
    """Dimensions for layout calculations."""
    width: float  # in inches
    height: float  # in inches
    margin: float  # in inches
    image_ratio: float  # portion of width for image
    
    @property
    def image_width(self) -> float:
        return self.width * self.image_ratio
    
    @property
    def text_width(self) -> float:
        # Allow text to extend to the right edge minus a small margin
        return self.width - self.image_width - self.margin
    
    @property
    def available_height(self) -> float:
        return self.height - (2 * self.margin)
    
    @property
    def text_start_x(self) -> float:
        return self.image_width + self.margin


@dataclass
class TextElement:
    """Represents a text element with calculated layout."""
    content: str
    font_name: str
    font_size: float
    lines: List[str]
    bbox: Dict[str, float]  # Bounding box info
    y_position: float  # Top of first line
    is_bold: bool = False


class DynamicLabelLayoutV3:
    """Layout engine with accurate text bounding box calculations."""
    
    def __init__(self, width_inches: float, height_inches: float):
        self.dimensions = LayoutDimensions(
            width=width_inches,
            height=height_inches,
            margin=min(0.05, width_inches * 0.05, height_inches * 0.05),
            image_ratio=0.25
        )
        self.line_spacing = 1.15  # Tighter line spacing since we have accurate metrics
        
    def calculate_layout(self, canvas_obj: canvas.Canvas,
                        description: str,
                        dimensions_text: Optional[str],
                        product_id: str) -> Dict[str, Any]:
        """Calculate optimal layout for all elements."""
        
        # Prepare text content
        elements = []
        if description:
            elements.append(("description", description, "Helvetica-Bold", True))
        if dimensions_text and dimensions_text.strip():
            elements.append(("dimensions", dimensions_text, "Helvetica", False))
        if product_id:
            elements.append(("product_id", f"#{product_id}", "Helvetica", False))
        
        # Calculate text layout with proper bounding boxes
        text_elements = self._calculate_text_layout(canvas_obj, elements)
        
        # Calculate image area
        image_area = {
            'x': self.dimensions.margin,
            'y': self.dimensions.margin,
            'width': self.dimensions.image_width - (2 * self.dimensions.margin),
            'height': self.dimensions.available_height
        }
        
        return {
            'image_area': image_area,
            'text_elements': text_elements,
            'dimensions': self.dimensions
        }
    
    def _calculate_text_layout(self, canvas_obj: canvas.Canvas,
                              elements: List[Tuple[str, str, str, bool]]) -> Dict[str, TextElement]:
        """Calculate optimal layout for text elements using accurate bounding boxes."""
        
        # Convert dimensions to points
        # For text width, use available space up to the edge
        text_width_pts = (self.dimensions.width - self.dimensions.image_width - self.dimensions.margin) * 72
        text_height_pts = self.dimensions.available_height * 72
        
        if not elements:
            return {}
        
        # Binary search for optimal font size
        min_font = 4
        max_font = min(72, int(text_height_pts / (len(elements) * 1.5)))
        
        best_font_size = min_font
        best_layout = None
        
        while min_font <= max_font:
            mid_font = (min_font + max_font) // 2
            
            # Try this font size
            test_layout = self._try_font_size_with_bbox(
                canvas_obj, elements, mid_font, text_width_pts, text_height_pts
            )
            
            if test_layout:
                # It fits! Try larger
                best_font_size = mid_font
                best_layout = test_layout
                min_font = mid_font + 1
            else:
                # Doesn't fit, try smaller
                max_font = mid_font - 1
        
        # If we found a layout, use it
        if best_layout:
            return best_layout
        
        # Fallback: Use minimum font size and truncate
        return self._create_minimal_layout_with_bbox(
            canvas_obj, elements, 4, text_width_pts, text_height_pts
        )
    
    def _try_font_size_with_bbox(self, canvas_obj: canvas.Canvas,
                                elements: List[Tuple[str, str, str, bool]],
                                base_font_size: float,
                                max_width_pts: float,
                                max_height_pts: float) -> Optional[Dict[str, TextElement]]:
        """Try to fit all elements with given font size using accurate bounding boxes."""
        
        # First pass: calculate all elements and total height
        temp_elements = []
        total_height = 0
        element_spacing = base_font_size * 0.3  # Space between different elements
        
        for i, (key, content, font_name, is_bold) in enumerate(elements):
            # Use base font for description, slightly smaller for others
            if key == "description":
                font_size = base_font_size
            else:
                font_size = max(4, int(base_font_size * 0.8))
            
            # Wrap text
            lines = self._wrap_text_with_bbox(canvas_obj, content, font_name, font_size, max_width_pts)
            
            # Calculate accurate bounding box for all lines
            bbox = TextMetrics.calculate_multiline_bbox(
                canvas_obj, lines, font_name, font_size, self.line_spacing
            )
            
            temp_elements.append({
                'key': key,
                'content': content,
                'font_name': font_name,
                'font_size': font_size,
                'lines': lines,
                'bbox': bbox,
                'is_bold': is_bold
            })
            
            total_height += bbox['height']
            if i < len(elements) - 1:  # Add spacing except after last element
                total_height += element_spacing
        
        # Check if total height fits
        if total_height > max_height_pts:
            return None  # Doesn't fit
        
        # Second pass: create elements with vertically centered positions
        result = {}
        # Calculate vertical offset to center the text block
        vertical_offset = (max_height_pts - total_height) / 2
        current_y = vertical_offset
        
        for i, elem in enumerate(temp_elements):
            result[elem['key']] = TextElement(
                content=elem['content'],
                font_name=elem['font_name'],
                font_size=elem['font_size'],
                lines=elem['lines'],
                bbox=elem['bbox'],
                y_position=current_y,
                is_bold=elem['is_bold']
            )
            
            # Update position for next element
            current_y += elem['bbox']['height']
            if i < len(temp_elements) - 1:  # Add spacing except after last element
                current_y += element_spacing
        
        return result
    
    def _create_minimal_layout_with_bbox(self, canvas_obj: canvas.Canvas,
                                       elements: List[Tuple[str, str, str, bool]],
                                       font_size: float,
                                       max_width_pts: float,
                                       max_height_pts: float) -> Dict[str, TextElement]:
        """Create layout with minimal font size, truncating if needed."""
        
        # First pass: calculate what fits
        temp_elements = []
        total_height = 0
        element_spacing = font_size * 0.3
        
        for key, content, font_name, is_bold in elements:
            lines = self._wrap_text_with_bbox(canvas_obj, content, font_name, font_size, max_width_pts)
            
            # Calculate how many lines we can fit
            remaining_height = max_height_pts - total_height
            if remaining_height <= 0:
                break
            
            # Get bbox for one line to estimate how many will fit
            if lines:
                single_line_bbox = TextMetrics.get_pdf_text_bbox(
                    canvas_obj, lines[0], font_name, font_size
                )
                line_height = single_line_bbox['height']
                max_lines = int(remaining_height / (line_height * self.line_spacing))
                
                if max_lines <= 0:
                    break
                
                # Truncate lines if needed
                if len(lines) > max_lines:
                    lines = lines[:max_lines]
                    if max_lines > 0:
                        # Add ellipsis to last line
                        lines[-1] = self._truncate_with_ellipsis(
                            canvas_obj, lines[-1], font_name, font_size, max_width_pts
                        )
            
            # Calculate actual bbox for the lines we're keeping
            bbox = TextMetrics.calculate_multiline_bbox(
                canvas_obj, lines, font_name, font_size, self.line_spacing
            )
            
            temp_elements.append({
                'key': key,
                'content': content,
                'font_name': font_name,
                'font_size': font_size,
                'lines': lines,
                'bbox': bbox,
                'is_bold': is_bold
            })
            
            total_height += bbox['height']
            if temp_elements and len(temp_elements) < len(elements):  # Add spacing if not last
                total_height += element_spacing
        
        # Second pass: create elements with vertically centered positions
        result = {}
        # Calculate vertical offset to center the text block
        vertical_offset = max(0, (max_height_pts - total_height) / 2)
        current_y = vertical_offset
        
        for i, elem in enumerate(temp_elements):
            result[elem['key']] = TextElement(
                content=elem['content'],
                font_name=elem['font_name'],
                font_size=elem['font_size'],
                lines=elem['lines'],
                bbox=elem['bbox'],
                y_position=current_y,
                is_bold=elem['is_bold']
            )
            
            current_y += elem['bbox']['height']
            if i < len(temp_elements) - 1:
                current_y += element_spacing
            
        return result
    
    def _wrap_text_with_bbox(self, canvas_obj: canvas.Canvas,
                           text: str,
                           font_name: str,
                           font_size: float,
                           max_width_pts: float) -> List[str]:
        """Wrap text to fit within maximum width using accurate measurements."""
        
        words = text.split()
        if not words:
            return [text]
        
        lines = []
        current_line = []
        
        for word in words:
            if current_line:
                test_line = " ".join(current_line + [word])
            else:
                test_line = word
            
            # Get accurate width measurement
            bbox = TextMetrics.get_pdf_text_bbox(canvas_obj, test_line, font_name, font_size)
            
            if bbox['width'] <= max_width_pts:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    # Single word is too long, add it anyway (will be truncated later if needed)
                    lines.append(word)
                    current_line = []
        
        if current_line:
            lines.append(" ".join(current_line))
        
        return lines if lines else [text]
    
    def _truncate_with_ellipsis(self, canvas_obj: canvas.Canvas,
                                text: str,
                                font_name: str,
                                font_size: float,
                                max_width_pts: float) -> str:
        """Truncate text with ellipsis to fit width."""
        
        ellipsis = "..."
        ellipsis_bbox = TextMetrics.get_pdf_text_bbox(canvas_obj, ellipsis, font_name, font_size)
        
        text_bbox = TextMetrics.get_pdf_text_bbox(canvas_obj, text, font_name, font_size)
        if text_bbox['width'] <= max_width_pts:
            return text
        
        # Binary search for the right truncation point
        left, right = 0, len(text)
        best_text = ""
        
        while left <= right:
            mid = (left + right) // 2
            truncated = text[:mid].rstrip()
            
            if truncated:
                test_text = truncated + ellipsis
                test_bbox = TextMetrics.get_pdf_text_bbox(canvas_obj, test_text, font_name, font_size)
                
                if test_bbox['width'] <= max_width_pts:
                    best_text = test_text
                    left = mid + 1
                else:
                    right = mid - 1
            else:
                left = mid + 1
        
        return best_text if best_text else ellipsis
    
    def _truncate_text_for_width(self, draw: ImageDraw.Draw,
                                text: str,
                                font: ImageFont.FreeTypeFont,
                                max_width_px: float) -> str:
        """Truncate text to fit within pixel width for PIL rendering."""
        
        ellipsis = "..."
        
        # Check if text already fits
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] <= max_width_px:
            return text
        
        # Check if ellipsis alone fits
        ellipsis_bbox = draw.textbbox((0, 0), ellipsis, font=font)
        if ellipsis_bbox[2] > max_width_px:
            return ""  # Not even ellipsis fits
        
        # Binary search for the right truncation point
        left, right = 0, len(text)
        best_text = ellipsis
        
        while left <= right:
            mid = (left + right) // 2
            truncated = text[:mid].rstrip()
            
            if truncated:
                test_text = truncated + ellipsis
                test_bbox = draw.textbbox((0, 0), test_text, font=font)
                
                if test_bbox[2] <= max_width_px:
                    best_text = test_text
                    left = mid + 1
                else:
                    right = mid - 1
            else:
                left = mid + 1
        
        return best_text
    
    def render_to_pil(self, draw: ImageDraw.Draw,
                     layout: Dict[str, Any],
                     dpi: int) -> None:
        """Render layout to PIL image using accurate bounding boxes."""
        
        text_elements = layout['text_elements']
        dimensions = layout['dimensions']
        
        # Calculate text start position in pixels
        text_start_x_px = int(dimensions.text_start_x * dpi)
        margin_px = int(dimensions.margin * dpi)
        
        # Load fonts and render text
        for key, element in text_elements.items():
            font_size_px = max(8, int(element.font_size * dpi / 72))
            
            # Try to load appropriate font
            try:
                if element.is_bold:
                    font = ImageFont.truetype("Arial-Bold.ttf", font_size_px)
                else:
                    font = ImageFont.truetype("Arial.ttf", font_size_px)
            except:
                # Fallback to default
                try:
                    font = ImageFont.load_default()
                except:
                    font = None
            
            if not font:
                continue
            
            # Calculate starting Y position
            y_px = margin_px + int(element.y_position * dpi / 72)
            
            # Render each line
            for i, line in enumerate(element.lines):
                if i > 0:
                    # Add line spacing for subsequent lines
                    y_px += int(element.font_size * self.line_spacing * dpi / 72)
                
                # Get accurate bounding box for this line
                bbox = draw.textbbox((text_start_x_px, y_px), line, font=font)
                
                # Check if text would be clipped vertically
                text_bottom = bbox[3]
                image_height_px = int(dimensions.height * dpi)
                
                if text_bottom > image_height_px - margin_px:
                    # Text would be clipped, skip remaining lines
                    logger.warning(f"Text clipped vertically for {key}: line {i+1}/{len(element.lines)}")
                    break
                
                # Check if text would be clipped horizontally
                text_right = bbox[2]
                image_width_px = int(dimensions.width * dpi)
                
                if text_right > image_width_px - 1:  # Allow text to go to within 1 pixel of edge
                    # Text extends beyond image, try to fit it
                    max_width_px = image_width_px - text_start_x_px - 1
                    truncated_line = self._truncate_text_for_width(
                        draw, line, font, max_width_px
                    )
                    if truncated_line != line:
                        logger.warning(f"Text truncated horizontally for {key}: line {i+1}")
                        line = truncated_line
                
                # Draw the text
                draw.text((text_start_x_px, y_px), line, fill='black', font=font)
    
    def render_to_pdf(self, canvas_obj: canvas.Canvas,
                     layout: Dict[str, Any]) -> None:
        """Render layout to PDF canvas using accurate positioning."""
        
        text_elements = layout['text_elements']
        dimensions = layout['dimensions']
        
        # Calculate positions
        text_start_x = dimensions.text_start_x * inch
        margin = dimensions.margin * inch
        page_height = dimensions.height * inch
        
        # Draw text elements
        for key, element in text_elements.items():
            canvas_obj.setFont(element.font_name, element.font_size)
            
            # Calculate Y position for first line
            # PDF coordinates are from bottom-left
            y_pos = page_height - margin - element.y_position / 72 * inch
            
            # Account for text ascent (text is drawn from baseline)
            if element.bbox and 'line_bboxes' in element.bbox and element.bbox['line_bboxes']:
                first_line_bbox = element.bbox['line_bboxes'][0]
                y_pos -= first_line_bbox['ascent'] / 72 * inch
            
            for i, line in enumerate(element.lines):
                if i > 0:
                    # Move down by line spacing
                    y_pos -= element.font_size * self.line_spacing / 72 * inch
                
                # Check if text would be clipped
                if y_pos < margin:
                    logger.warning(f"Text clipped for {key}: line {i+1}/{len(element.lines)}")
                    break
                
                canvas_obj.drawString(text_start_x, y_pos, line)