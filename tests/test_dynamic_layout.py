"""
Tests for dynamic label layout engine.
"""

import pytest
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import tempfile
import os

from src.dynamic_label_layout_v2 import DynamicLabelLayoutV2, TextElement, LayoutDimensions
from src.label_generator import LabelGenerator


class TestDynamicLayout:
    """Test dynamic layout calculations."""
    
    def test_layout_initialization(self):
        """Test layout engine initialization."""
        layout = DynamicLabelLayoutV2(width_inches=2.0, height_inches=1.0)
        assert layout.dimensions.width == 2.0
        assert layout.dimensions.height == 1.0
        assert layout.dimensions.margin <= 0.05
        assert layout.dimensions.image_ratio == 0.25
    
    def test_small_label_layout(self):
        """Test layout for small labels (0.5" x 0.5")."""
        layout = DynamicLabelLayoutV2(width_inches=0.5, height_inches=0.5)
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            c = canvas.Canvas(tmp.name)
            result = layout.calculate_layout(
                c, 
                "Small Part",
                "M3 x 10mm",
                "12345"
            )
            
            # Check image area
            assert result['image_area']['width'] < 0.125  # Less than 25% of 0.5"
            assert result['image_area']['height'] < 0.5
            
            # Check text layout exists
            assert 'description' in result['text_elements']
            assert 'dimensions' in result['text_elements']
            assert 'product_id' in result['text_elements']
            
            # Font sizes should be small for small label
            desc_block = result['text_elements']['description']
            assert desc_block.font_size >= 4  # Minimum readable size
            assert desc_block.font_size <= 12  # Should be small for tiny label
            
            os.unlink(tmp.name)
    
    def test_medium_label_layout(self):
        """Test layout for medium labels (1.5" x 0.5")."""
        layout = DynamicLabelLayoutV2(width_inches=1.5, height_inches=0.5)
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            c = canvas.Canvas(tmp.name)
            result = layout.calculate_layout(
                c,
                "Socket Cap Screw",
                "1/4-20 x 1\" Long",
                "91290A115"
            )
            
            # Check text layout
            desc_block = result['text_elements']['description']
            dim_block = result['text_elements']['dimensions']
            
            # Font sizes should be reasonable
            assert 4 <= desc_block.font_size <= 20
            assert 4 <= dim_block.font_size <= 18
            
            # Font sizes should be close to each other (within 2 points)
            assert abs(desc_block.font_size - dim_block.font_size) <= 2
            
            os.unlink(tmp.name)
    
    def test_large_label_layout(self):
        """Test layout for large labels (4" x 2")."""
        layout = DynamicLabelLayoutV2(width_inches=4.0, height_inches=2.0)
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            c = canvas.Canvas(tmp.name)
            result = layout.calculate_layout(
                c,
                "Heavy Duty Industrial Bearing",
                "ID: 50mm, OD: 110mm, Width: 27mm",
                "6201-2RS"
            )
            
            # Font sizes should be large for big label
            desc_block = result['text_elements']['description']
            assert desc_block.font_size >= 20  # Should use space
            
            # Check that text fits properly
            assert len(desc_block.lines) >= 1
            
            os.unlink(tmp.name)
    
    def test_no_dimensions_layout(self):
        """Test layout when no dimensions are provided."""
        layout = DynamicLabelLayoutV2(width_inches=2.0, height_inches=1.0)
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            c = canvas.Canvas(tmp.name)
            result = layout.calculate_layout(
                c,
                "Generic Part Without Dimensions",
                None,  # No dimensions
                "PART-001"
            )
            
            # Should only have description and product_id
            assert result['text_elements']['description'] is not None
            assert 'dimensions' not in result['text_elements']
            assert result['text_elements']['product_id'] is not None
            
            # Description should get more space without dimensions
            desc_block = result['text_elements']['description']
            assert desc_block.font_size >= 8  # Reasonable size for 2"x1" label
            
            os.unlink(tmp.name)
    
    def test_long_text_wrapping(self):
        """Test text wrapping for long descriptions."""
        layout = DynamicLabelLayoutV2(width_inches=1.5, height_inches=0.5)
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            c = canvas.Canvas(tmp.name)
            
            long_desc = "This is a very long description that should wrap to multiple lines"
            result = layout.calculate_layout(c, long_desc, "10mm", "12345")
            
            desc_block = result['text_elements']['description']
            # Should wrap to multiple lines
            assert len(desc_block.lines) > 1
            
            # Each line should fit within available width
            text_width = (1.5 * 0.75) * 72  # 75% of label width in points
            for line in desc_block.lines:
                line_width = c.stringWidth(line, desc_block.font_name, desc_block.font_size)
                assert line_width <= text_width
            
            os.unlink(tmp.name)
    
    def test_aspect_ratio_labels(self):
        """Test various aspect ratio labels."""
        test_cases = [
            (1.0, 1.0),   # Square
            (3.0, 1.0),   # Wide
            (1.0, 3.0),   # Tall
            (2.0, 0.5),   # Very wide and short
            (0.5, 2.0),   # Narrow and tall
        ]
        
        for width, height in test_cases:
            layout = DynamicLabelLayoutV2(width_inches=width, height_inches=height)
            
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                c = canvas.Canvas(tmp.name)
                result = layout.calculate_layout(
                    c,
                    "Test Part",
                    "Test Dimension",
                    "TEST-001"
                )
                
                # Should always produce valid layout
                assert result['image_area'] is not None
                assert result['text_elements'] is not None
                
                # Image area should be proportional
                image_area = result['image_area']
                assert image_area['width'] > 0
                assert image_area['height'] > 0
                assert image_area['width'] <= width * 0.25
                
                os.unlink(tmp.name)
    
    def test_font_size_limits(self):
        """Test that font sizes stay within reasonable limits."""
        # Very large label
        layout = DynamicLabelLayoutV2(width_inches=10.0, height_inches=10.0)
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            c = canvas.Canvas(tmp.name)
            result = layout.calculate_layout(c, "Big Label", "Dimensions", "ID123")
            
            # Font shouldn't be too large even on huge label
            desc_block = result['text_elements']['description']
            assert desc_block.font_size <= 72  # Max font size
            
            os.unlink(tmp.name)
    
    def test_minimum_font_size(self):
        """Test that font sizes don't go below minimum readable size."""
        # Very small label with lots of text
        layout = DynamicLabelLayoutV2(width_inches=0.5, height_inches=0.25)
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            c = canvas.Canvas(tmp.name)
            result = layout.calculate_layout(
                c,
                "This is a very long description for a tiny label",
                "Many dimensions here",
                "LONG-ID-12345"
            )
            
            # All text should be at least minimum size
            for key, block in result['text_elements'].items():
                if block:
                    assert block.font_size >= 4  # Minimum readable
            
            os.unlink(tmp.name)


class TestLabelGeneratorIntegration:
    """Test label generator with dynamic layout."""
    
    def test_various_label_sizes(self):
        """Test label generation with various sizes."""
        test_sizes = [
            (0.5, 0.5),    # Tiny square
            (1.0, 0.5),    # Small rectangle
            (1.5, 0.5),    # Standard small
            (2.0, 1.0),    # Medium
            (3.0, 2.0),    # Large
            (4.0, 3.0),    # Extra large
        ]
        
        # Mock product data
        products_data = {
            "TEST001": {
                "info": {
                    "short_description": "Test Product",
                    "dimensional_description": "10mm x 20mm x 5mm"
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        for width, height in test_sizes:
            generator = LabelGenerator(width_inches=width, height_inches=height)
            
            # Test PDF generation
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                output_path = generator.generate_labels(
                    products_data,
                    tmp.name
                )
                
                # Should create file
                assert os.path.exists(output_path)
                assert os.path.getsize(output_path) > 0
                
                os.unlink(output_path)
    
    def test_content_scaling(self):
        """Test that content scales appropriately with label size."""
        # Create two labels with same content but different sizes
        products_data = {
            "SCALE001": {
                "info": {
                    "short_description": "Scaling Test Product with Longer Name",
                    "dimensional_description": "100mm x 50mm x 25mm Stainless Steel"
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        # Small label
        small_gen = LabelGenerator(width_inches=1.0, height_inches=0.5)
        
        # Large label  
        large_gen = LabelGenerator(width_inches=4.0, height_inches=2.0)
        
        # Both should generate successfully
        with tempfile.NamedTemporaryFile(suffix='_small.pdf', delete=False) as tmp_small:
            small_path = small_gen.generate_labels(products_data, tmp_small.name)
            assert os.path.exists(small_path)
            small_size = os.path.getsize(small_path)
            os.unlink(small_path)
        
        with tempfile.NamedTemporaryFile(suffix='_large.pdf', delete=False) as tmp_large:
            large_path = large_gen.generate_labels(products_data, tmp_large.name)
            assert os.path.exists(large_path)
            large_size = os.path.getsize(large_path)
            os.unlink(large_path)
        
        # Files should exist and have content
        assert small_size > 1000  # At least 1KB
        assert large_size > 1000
    
    def test_image_scaling(self):
        """Test that images scale properly with label size."""
        # Create a test image
        test_img = Image.new('RGB', (200, 100), color='white')
        draw = ImageDraw.Draw(test_img)
        draw.rectangle([10, 10, 190, 90], outline='black', width=2)
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_img:
            test_img.save(tmp_img.name)
            
            products_data = {
                "IMG001": {
                    "info": {
                        "short_description": "Image Scaling Test",
                        "dimensional_description": "With Image"
                    },
                    "image_path": tmp_img.name,
                    "cad_path": None
                }
            }
            
            # Test with different label sizes
            for width, height in [(1.0, 0.5), (2.0, 1.0), (4.0, 2.0)]:
                gen = LabelGenerator(width_inches=width, height_inches=height)
                
                # Generate PNG to check image scaling
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_out:
                    from src.output_formats import OutputFormat
                    output_path = gen.generate_labels(
                        products_data,
                        tmp_out.name,
                        output_format=OutputFormat.PNG,
                        dpi=150
                    )
                    
                    # Check output exists
                    assert os.path.exists(output_path)
                    
                    # Load and check size
                    result_img = Image.open(output_path)
                    expected_width = int(width * 150)
                    expected_height = int(height * 150)
                    
                    assert abs(result_img.width - expected_width) < 5
                    assert abs(result_img.height - expected_height) < 5
                    
                    result_img.close()
                    os.unlink(output_path)
            
            os.unlink(tmp_img.name)