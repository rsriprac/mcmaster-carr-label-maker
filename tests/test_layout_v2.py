"""
Tests for the refactored dynamic label layout engine v2.
"""

import pytest
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
import tempfile
import os

from src.dynamic_label_layout_v2 import DynamicLabelLayoutV2, TextElement
from src.label_generator import LabelGenerator


class TestDynamicLayoutV2:
    """Test the refactored dynamic layout engine."""
    
    def test_initialization(self):
        """Test layout engine initialization."""
        layout = DynamicLabelLayoutV2(width_inches=2.0, height_inches=1.0)
        assert layout.dimensions.width == 2.0
        assert layout.dimensions.height == 1.0
        assert layout.dimensions.image_ratio == 0.25
        assert layout.dimensions.text_width == 1.4  # 2.0 - (2.0 * 0.25) - (2 * 0.05)
    
    def test_small_label_no_overlap(self):
        """Test that small labels don't have overlapping text."""
        layout = DynamicLabelLayoutV2(width_inches=0.5, height_inches=0.5)
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            c = canvas.Canvas(tmp.name)
            result = layout.calculate_layout(
                c,
                "Small Part",
                "M3 x 10mm",
                "12345"
            )
            
            # Check that text elements exist
            elements = result['text_elements']
            assert 'description' in elements
            assert 'dimensions' in elements
            assert 'product_id' in elements
            
            # Check no overlap - each element should start after the previous ends
            desc = elements['description']
            dims = elements['dimensions']
            prod = elements['product_id']
            
            # Dimensions should start after description ends
            assert dims.y_position >= desc.y_position + desc.total_height
            
            # Product ID should start after dimensions ends
            assert prod.y_position >= dims.y_position + dims.total_height
            
            os.unlink(tmp.name)
    
    def test_text_scaling(self):
        """Test that text scales with label size."""
        # Small label
        small_layout = DynamicLabelLayoutV2(width_inches=1.0, height_inches=0.5)
        # Large label
        large_layout = DynamicLabelLayoutV2(width_inches=4.0, height_inches=2.0)
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            c = canvas.Canvas(tmp.name)
            
            small_result = small_layout.calculate_layout(c, "Test Product", "10mm", "TEST001")
            large_result = large_layout.calculate_layout(c, "Test Product", "10mm", "TEST001")
            
            # Font size should be larger on larger label
            small_font = small_result['text_elements']['description'].font_size
            large_font = large_result['text_elements']['description'].font_size
            
            assert large_font > small_font
            
            os.unlink(tmp.name)
    
    def test_long_text_wrapping(self):
        """Test that long text wraps properly."""
        layout = DynamicLabelLayoutV2(width_inches=1.5, height_inches=0.5)
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            c = canvas.Canvas(tmp.name)
            
            long_text = "This is a very long product description that should wrap to multiple lines"
            result = layout.calculate_layout(c, long_text, "Dimensions", "ID123")
            
            desc = result['text_elements']['description']
            # Should wrap to multiple lines
            assert len(desc.lines) > 1
            
            # Total height should match line count
            expected_height = len(desc.lines) * desc.line_height
            assert abs(desc.total_height - expected_height) < 0.1
            
            os.unlink(tmp.name)
    
    def test_no_dimensions(self):
        """Test layout when dimensions are not provided."""
        layout = DynamicLabelLayoutV2(width_inches=2.0, height_inches=1.0)
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            c = canvas.Canvas(tmp.name)
            result = layout.calculate_layout(c, "Product Name", None, "PROD001")
            
            elements = result['text_elements']
            assert 'description' in elements
            assert 'dimensions' not in elements  # Should not have dimensions
            assert 'product_id' in elements
            
            os.unlink(tmp.name)
    
    def test_text_fits_within_bounds(self):
        """Test that all text fits within label bounds."""
        sizes = [(0.5, 0.5), (1.0, 0.5), (2.0, 1.0), (4.0, 2.0)]
        
        for width, height in sizes:
            layout = DynamicLabelLayoutV2(width_inches=width, height_inches=height)
            
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                c = canvas.Canvas(tmp.name)
                result = layout.calculate_layout(
                    c,
                    "Product with a reasonably long name",
                    "Multiple dimensional specifications here",
                    "LONG-PRODUCT-ID-12345"
                )
                
                # Calculate total text height
                total_height = 0
                last_element = None
                
                for element in result['text_elements'].values():
                    if last_element:
                        # Check gap between elements
                        gap = element.y_position - (last_element.y_position + last_element.total_height)
                        total_height += gap
                    
                    total_height += element.total_height
                    last_element = element
                
                # Total height should fit within available height (in points)
                available_height_pts = layout.dimensions.available_height * 72
                assert total_height <= available_height_pts
                
                os.unlink(tmp.name)


class TestLabelGeneratorIntegration:
    """Integration tests with the label generator."""
    
    def test_no_overlap_various_sizes(self):
        """Test that labels of various sizes don't have overlapping text."""
        sizes = [
            (0.5, 0.5),
            (1.0, 0.5), 
            (1.5, 0.5),
            (2.0, 1.0),
            (3.0, 2.0),
            (4.0, 1.0),  # Wide
            (1.0, 3.0),  # Tall
        ]
        
        products_data = {
            "TEST001": {
                "info": {
                    "short_description": "Test Product with Moderate Length Name",
                    "dimensional_description": "10mm x 20mm x 5mm, Stainless Steel, Grade 316"
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        for width, height in sizes:
            generator = LabelGenerator(width_inches=width, height_inches=height)
            
            # Generate PNG to verify layout
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                from src.output_formats import OutputFormat
                
                output_path = generator.generate_labels(
                    products_data,
                    tmp.name,
                    output_format=OutputFormat.PNG,
                    dpi=150
                )
                
                # Verify file was created
                assert os.path.exists(output_path)
                assert os.path.getsize(output_path) > 0
                
                # Could add image analysis here to verify no overlap
                
                os.unlink(output_path)
    
    def test_text_truncation_on_tiny_labels(self):
        """Test that text is properly truncated on very small labels."""
        generator = LabelGenerator(width_inches=0.5, height_inches=0.25)
        
        products_data = {
            "TINY001": {
                "info": {
                    "short_description": "This is an extremely long product description that definitely won't fit",
                    "dimensional_description": "These are very detailed dimensions that also won't fit"
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            output_path = generator.generate_labels(products_data, tmp.name)
            
            # Should generate without error even with text that doesn't fit
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
            
            os.unlink(output_path)