"""
Visual validation utilities to detect text clipping and layout issues.
"""

from typing import Dict, List, Tuple, Optional
from PIL import Image, ImageDraw
import numpy as np
import logging

logger = logging.getLogger(__name__)


class VisualValidator:
    """Validate rendered labels for visual issues like clipping."""
    
    @staticmethod
    def detect_clipping(image: Image.Image, 
                       margin_px: int = 2,
                       threshold: int = 10) -> Dict[str, bool]:
        """
        Detect if content is clipped at image edges.
        
        Args:
            image: PIL Image to analyze
            margin_px: Pixels from edge to check (smaller than actual margin)
            threshold: Minimum number of non-white pixels to consider as content
            
        Returns:
            Dict with clipping detection for each edge
        """
        # Convert to numpy array
        img_array = np.array(image.convert('L'))  # Convert to grayscale
        height, width = img_array.shape
        
        # Define what we consider "content" (non-white pixels)
        # White is 255, so anything significantly darker is content
        content_threshold = 250
        
        results = {
            'top': False,
            'bottom': False,
            'left': False,
            'right': False,
            'any': False
        }
        
        # Check top edge
        top_region = img_array[0:margin_px, :]
        if np.sum(top_region < content_threshold) > threshold:
            results['top'] = True
            logger.warning("Content detected at top edge - possible clipping")
        
        # Check bottom edge
        bottom_region = img_array[height-margin_px:height, :]
        if np.sum(bottom_region < content_threshold) > threshold:
            results['bottom'] = True
            logger.warning("Content detected at bottom edge - possible clipping")
        
        # Check left edge
        left_region = img_array[:, 0:margin_px]
        if np.sum(left_region < content_threshold) > threshold:
            results['left'] = True
            logger.warning("Content detected at left edge - possible clipping")
        
        # Check right edge
        right_region = img_array[:, width-margin_px:width]
        if np.sum(right_region < content_threshold) > threshold:
            results['right'] = True
            logger.warning("Content detected at right edge - possible clipping")
        
        results['any'] = any([results['top'], results['bottom'], 
                             results['left'], results['right']])
        
        return results
    
    @staticmethod
    def get_content_bounds(image: Image.Image) -> Tuple[int, int, int, int]:
        """
        Get the bounding box of actual content (non-white pixels).
        
        Returns:
            (left, top, right, bottom) coordinates of content
        """
        # Convert to numpy array
        img_array = np.array(image.convert('L'))
        
        # Find non-white pixels (content)
        content_mask = img_array < 250
        
        # Find the bounds
        rows = np.any(content_mask, axis=1)
        cols = np.any(content_mask, axis=0)
        
        if not np.any(rows) or not np.any(cols):
            # No content found
            return (0, 0, 0, 0)
        
        rmin, rmax = np.where(rows)[0][[0, -1]]
        cmin, cmax = np.where(cols)[0][[0, -1]]
        
        return (cmin, rmin, cmax, rmax)
    
    @staticmethod
    def calculate_whitespace_usage(image: Image.Image, 
                                 expected_margin_px: int) -> Dict[str, float]:
        """
        Calculate how well the label uses available space.
        
        Returns:
            Dict with usage statistics
        """
        width, height = image.size
        content_bounds = VisualValidator.get_content_bounds(image)
        
        if content_bounds == (0, 0, 0, 0):
            return {
                'content_width_ratio': 0,
                'content_height_ratio': 0,
                'total_usage_ratio': 0,
                'margin_violations': []
            }
        
        left, top, right, bottom = content_bounds
        content_width = right - left
        content_height = bottom - top
        
        # Calculate available space (total minus margins)
        available_width = width - (2 * expected_margin_px)
        available_height = height - (2 * expected_margin_px)
        
        # Calculate usage ratios
        width_ratio = content_width / available_width if available_width > 0 else 0
        height_ratio = content_height / available_height if available_height > 0 else 0
        
        # Check margin violations
        margin_violations = []
        if left < expected_margin_px:
            margin_violations.append('left')
        if top < expected_margin_px:
            margin_violations.append('top')
        if width - right < expected_margin_px:
            margin_violations.append('right')
        if height - bottom < expected_margin_px:
            margin_violations.append('bottom')
        
        return {
            'content_width_ratio': width_ratio,
            'content_height_ratio': height_ratio,
            'total_usage_ratio': width_ratio * height_ratio,
            'margin_violations': margin_violations,
            'content_bounds': content_bounds
        }
    
    @staticmethod
    def validate_label(image_path: str, 
                      width_inches: float,
                      height_inches: float,
                      dpi: int = 150) -> Dict[str, any]:
        """
        Comprehensive validation of a label image.
        
        Returns:
            Dict with validation results
        """
        image = Image.open(image_path)
        
        # Calculate expected dimensions
        expected_width = int(width_inches * dpi)
        expected_height = int(height_inches * dpi)
        expected_margin = int(min(0.05 * dpi, width_inches * 0.05 * dpi, height_inches * 0.05 * dpi))
        
        # Check dimensions
        dimension_match = (abs(image.width - expected_width) < 5 and 
                          abs(image.height - expected_height) < 5)
        
        # Detect clipping - check only at very edge
        clipping = VisualValidator.detect_clipping(image, margin_px=1)
        
        # Calculate space usage
        usage = VisualValidator.calculate_whitespace_usage(image, expected_margin)
        
        # Create debug image if issues found
        debug_image = None
        if clipping['any'] or usage['margin_violations']:
            debug_image = VisualValidator.create_debug_overlay(
                image, usage['content_bounds'], clipping, expected_margin
            )
        
        return {
            'valid': not clipping['any'] and not usage['margin_violations'],
            'dimension_match': dimension_match,
            'clipping': clipping,
            'usage': usage,
            'debug_image': debug_image
        }
    
    @staticmethod
    def create_debug_overlay(image: Image.Image,
                           content_bounds: Tuple[int, int, int, int],
                           clipping: Dict[str, bool],
                           expected_margin: int) -> Image.Image:
        """Create a debug overlay showing issues."""
        # Create a copy to draw on
        debug_img = image.copy()
        draw = ImageDraw.Draw(debug_img, 'RGBA')
        
        # Draw content bounds in green
        if content_bounds != (0, 0, 0, 0):
            draw.rectangle(content_bounds, outline=(0, 255, 0, 128), width=2)
        
        # Draw expected margins in blue
        width, height = image.size
        margin_bounds = (expected_margin, expected_margin, 
                        width - expected_margin, height - expected_margin)
        draw.rectangle(margin_bounds, outline=(0, 0, 255, 128), width=1)
        
        # Highlight clipped edges in red
        if clipping['top']:
            draw.rectangle((0, 0, width, 5), fill=(255, 0, 0, 128))
        if clipping['bottom']:
            draw.rectangle((0, height-5, width, height), fill=(255, 0, 0, 128))
        if clipping['left']:
            draw.rectangle((0, 0, 5, height), fill=(255, 0, 0, 128))
        if clipping['right']:
            draw.rectangle((width-5, 0, width, height), fill=(255, 0, 0, 128))
        
        return debug_img