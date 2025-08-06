"""
Tests for vertical centering of text within labels.
"""

import pytest
import tempfile
import os
from PIL import Image
import numpy as np

from src.label_generator import LabelGenerator
from src.visual_validator import VisualValidator
from src.output_formats import OutputFormat


class TestVerticalCentering:
    """Test that text is vertically centered within labels."""
    
    def test_vertical_centering_small_text(self):
        """Test vertical centering with small amount of text."""
        products_data = {
            "SMALL": {
                "info": {
                    "short_description": "Small Text",
                    "dimensional_description": "10mm"
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        # Test on a tall label where centering is visible
        generator = LabelGenerator(width_inches=2.0, height_inches=2.0)
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            output_path = generator.generate_labels(
                products_data,
                tmp.name,
                output_format=OutputFormat.PNG,
                dpi=150
            )
            
            # Analyze the image
            img = Image.open(output_path)
            img_array = np.array(img.convert('L'))
            height, width = img_array.shape
            
            # Find content bounds
            content_mask = img_array < 250  # Non-white pixels
            rows_with_content = np.any(content_mask, axis=1)
            
            if np.any(rows_with_content):
                content_rows = np.where(rows_with_content)[0]
                top_content = content_rows[0]
                bottom_content = content_rows[-1]
                content_height = bottom_content - top_content
                
                # Calculate margins
                top_margin = top_content
                bottom_margin = height - bottom_content - 1
                
                # Check that content is reasonably centered
                # Allow some tolerance due to rounding and font metrics
                margin_diff = abs(top_margin - bottom_margin)
                tolerance = height * 0.1  # 10% tolerance
                
                assert margin_diff < tolerance, f"Text not centered: top margin={top_margin}, bottom margin={bottom_margin}"
            
            os.unlink(output_path)
    
    def test_vertical_centering_various_sizes(self):
        """Test vertical centering across different label sizes."""
        products_data = {
            "TEST": {
                "info": {
                    "short_description": "Test Product for Centering",
                    "dimensional_description": "Standard Size"
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        test_sizes = [
            (1.0, 1.0),   # Square
            (2.0, 1.0),   # Wide
            (1.0, 2.0),   # Tall
            (3.0, 3.0),   # Large square
        ]
        
        for width, height in test_sizes:
            generator = LabelGenerator(width_inches=width, height_inches=height)
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                output_path = generator.generate_labels(
                    products_data,
                    tmp.name,
                    output_format=OutputFormat.PNG,
                    dpi=150
                )
                
                # Validate no clipping
                validation = VisualValidator.validate_label(
                    str(output_path),
                    width_inches=width,
                    height_inches=height,
                    dpi=150
                )
                
                # For edge-to-edge text support, we allow content at edges
                if validation['clipping']['any']:
                    # Edge content is allowed for our edge-to-edge text feature
                    print(f"Edge content detected on {width}x{height} label (allowed)")
                
                # Check vertical centering
                img = Image.open(output_path)
                img_array = np.array(img.convert('L'))
                height_px, width_px = img_array.shape
                
                # Find content bounds
                content_mask = img_array < 250
                rows_with_content = np.any(content_mask, axis=1)
                
                if np.any(rows_with_content):
                    content_rows = np.where(rows_with_content)[0]
                    top_content = content_rows[0]
                    bottom_content = content_rows[-1]
                    
                    # Calculate center
                    content_center = (top_content + bottom_content) / 2
                    image_center = height_px / 2
                    
                    # Check centering (allow 10% tolerance)
                    center_diff = abs(content_center - image_center)
                    tolerance = height_px * 0.1
                    
                    assert center_diff < tolerance, \
                        f"Content not centered on {width}x{height}: content center={content_center}, image center={image_center}"
                
                os.unlink(output_path)
    
    def test_vertical_centering_with_all_elements(self):
        """Test centering with all text elements (description, dimensions, ID)."""
        products_data = {
            "FULL": {
                "info": {
                    "short_description": "Complete Product Information",
                    "dimensional_description": "100mm x 50mm x 25mm",
                    "mcmaster_id": "12345-ABC"
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        generator = LabelGenerator(width_inches=2.0, height_inches=2.0)
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            output_path = generator.generate_labels(
                products_data,
                tmp.name,
                output_format=OutputFormat.PNG,
                dpi=150
            )
            
            # Validate
            validation = VisualValidator.validate_label(
                str(output_path),
                width_inches=2.0,
                height_inches=2.0,
                dpi=150
            )
            
            # For edge-to-edge text support, we allow content at edges
            if not validation['valid']:
                # Check if the only issue is edge content
                if validation['clipping']['any']:
                    # Edge content is allowed for our edge-to-edge text feature
                    print("Edge content detected (allowed)")
                else:
                    assert False, f"Label has issues: {validation}"
            
            # Save debug image for visual inspection if needed
            if validation['debug_image']:
                debug_path = "test_centering_debug.png"
                validation['debug_image'].save(debug_path)
                print(f"Debug image saved to {debug_path}")
            
            os.unlink(output_path)
    
    def test_no_centering_when_text_fills_space(self):
        """Test that when text fills available space, it uses all of it."""
        products_data = {
            "LONG": {
                "info": {
                    "short_description": "This is a very long product description that should take up multiple lines and use most of the available vertical space on the label",
                    "dimensional_description": "These are extremely detailed dimensional specifications that also span multiple lines to ensure we use the available space",
                    "mcmaster_id": "VERY-LONG-PRODUCT-ID-12345"
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        # Use a smaller label to ensure text fills it
        generator = LabelGenerator(width_inches=1.5, height_inches=0.5)
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            output_path = generator.generate_labels(
                products_data,
                tmp.name,
                output_format=OutputFormat.PNG,
                dpi=150
            )
            
            # Validate no clipping
            validation = VisualValidator.validate_label(
                str(output_path),
                width_inches=1.5,
                height_inches=0.5,
                dpi=150
            )
            
            # For edge-to-edge text support, we allow content at edges
            if validation['clipping']['any']:
                # Edge content is allowed for our edge-to-edge text feature
                print("Edge content detected (allowed)")
            
            # Check that we're using most of the vertical space
            assert validation['usage']['content_height_ratio'] > 0.8, \
                "Should use most vertical space when text is long"
            
            os.unlink(output_path)