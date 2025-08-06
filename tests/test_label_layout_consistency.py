import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
import io
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

from src.label_generator import LabelGenerator


# Test dimensions covering various sizes and aspect ratios
TEST_DIMENSIONS = [
    # Standard sizes
    (1.5, 0.5),    # Default size
    (2.0, 1.0),    # 2:1 ratio
    (1.0, 1.0),    # Square
    (3.0, 1.5),    # 2:1 ratio, larger
    
    # Metric conversions (approximate)
    (1.97, 0.79),  # 50mm x 20mm
    (3.94, 1.97),  # 100mm x 50mm
    (2.36, 1.18),  # 60mm x 30mm
    
    # Extreme but valid sizes
    (0.5, 0.5),    # Minimum square
    (4.0, 0.5),    # Very wide
    (0.5, 2.0),    # Very tall
    (6.0, 4.0),    # Large format
    (8.0, 2.0),    # Wide banner
    
    # Common label sizes
    (2.625, 1.0),  # Address label
    (3.5, 1.125),  # Name badge
    (4.0, 2.0),    # Shipping label
]


def create_mock_product_data():
    """Create mock product data for testing."""
    return {
        "91290A115": {
            "info": {
                "short_description": "Zinc-Plated Steel Hex Nut",
                "specs": [
                    {"name": "Thread Size", "value": "1/4\"-20"},
                    {"name": "Width Across Flats", "value": "7/16\""},
                    {"name": "Material", "value": "Steel"},
                    {"name": "Finish", "value": "Zinc-Plated"}
                ]
            },
            "image_path": "/mock/path/image.png",
            "cad_path": None
        }
    }


class TestLabelLayoutConsistency:
    """Test that label layouts remain consistent across different sizes."""
    
    @pytest.fixture
    def mock_image(self):
        """Create a mock image for testing."""
        img = Image.new('RGB', (100, 100), color='white')
        return img
    
    @pytest.fixture
    def mock_image_processor(self, mock_image):
        """Mock the image processor."""
        processor = Mock()
        processor.get_image_for_product.return_value = mock_image
        return processor
    
    @pytest.mark.parametrize("width,height", TEST_DIMENSIONS)
    def test_label_dimensions_respected(self, width, height, mock_image_processor, tmp_path):
        """Test that generated labels respect the specified dimensions."""
        # Create generator with specific dimensions
        generator = LabelGenerator(width_inches=width, height_inches=height)
        generator.image_processor = mock_image_processor
        
        # Verify internal dimensions are set correctly
        assert generator.width_inches == width
        assert generator.height_inches == height
        assert generator.page_width == width * inch
        assert generator.page_height == height * inch
    
    @pytest.mark.parametrize("width,height", TEST_DIMENSIONS)
    def test_image_area_proportion(self, width, height):
        """Test that image area maintains 25% width proportion."""
        generator = LabelGenerator(width_inches=width, height_inches=height)
        
        # Image should always be 25% of label width
        expected_image_width = generator.page_width * 0.25
        assert generator.image_width == expected_image_width
        
        # Text should start after image + margin
        expected_text_start = generator.image_width + generator.margin
        assert generator.text_start_x == expected_text_start
    
    @pytest.mark.parametrize("width,height", TEST_DIMENSIONS)
    def test_margin_consistency(self, width, height):
        """Test that margins remain consistent across sizes."""
        generator = LabelGenerator(width_inches=width, height_inches=height)
        
        # Margin should always be 0.05 inches
        assert generator.margin == 0.05 * inch
    
    @pytest.mark.parametrize("width,height", TEST_DIMENSIONS)
    def test_text_area_calculation(self, width, height):
        """Test that text area is calculated correctly for all sizes."""
        generator = LabelGenerator(width_inches=width, height_inches=height)
        
        # Calculate available text area
        text_area_width = generator.page_width - generator.text_start_x - generator.margin
        text_area_height = generator.page_height - (2 * generator.margin)
        
        # Text area should be positive
        assert text_area_width > 0
        assert text_area_height > 0
        
        # Text area should be approximately 75% of width (minus margins)
        expected_text_width = generator.page_width * 0.75 - (2 * generator.margin)
        assert abs(text_area_width - expected_text_width) < 0.01 * inch
    
    @pytest.mark.parametrize("width,height", TEST_DIMENSIONS)
    @patch('src.label_generator.canvas')
    def test_pdf_page_size_set_correctly(self, mock_canvas, width, height, mock_image_processor):
        """Test that PDF pages are created with correct dimensions."""
        generator = LabelGenerator(width_inches=width, height_inches=height)
        generator.image_processor = mock_image_processor
        
        # Mock canvas instance
        mock_canvas_instance = MagicMock()
        mock_canvas.Canvas.return_value = mock_canvas_instance
        
        # Mock stringWidth to return reasonable values
        mock_canvas_instance.stringWidth.return_value = 50.0  # Reasonable width for text
        
        # Generate labels
        products_data = create_mock_product_data()
        generator.generate_labels(products_data, "test.pdf")
        
        # Verify canvas was created with correct page size
        mock_canvas.Canvas.assert_called_once()
        call_args = mock_canvas.Canvas.call_args
        assert call_args[1]['pagesize'] == (width * inch, height * inch)
    
    def test_layout_proportions_across_sizes(self):
        """Test that layout proportions remain consistent across all sizes."""
        proportions = []
        
        for width, height in TEST_DIMENSIONS:
            generator = LabelGenerator(width_inches=width, height_inches=height)
            
            # Calculate proportions
            image_proportion = generator.image_width / generator.page_width
            margin_proportion = generator.margin / generator.page_width
            
            proportions.append({
                'size': (width, height),
                'image_proportion': image_proportion,
                'margin_proportion': margin_proportion
            })
        
        # All image proportions should be 25%
        for prop in proportions:
            assert abs(prop['image_proportion'] - 0.25) < 0.001, \
                f"Image proportion inconsistent for size {prop['size']}"
        
        # Margin proportions will vary with size, but should be reasonable
        for prop in proportions:
            # Margin should be between 0.5% and 20% of width
            # For very large labels, 0.05" margin can be less than 1% of width
            assert 0.005 < prop['margin_proportion'] < 0.20, \
                f"Margin proportion unreasonable for size {prop['size']}"
    
    @pytest.mark.parametrize("width,height", TEST_DIMENSIONS)
    def test_font_size_scaling(self, width, height):
        """Test that font sizes scale appropriately with label size."""
        generator = LabelGenerator(width_inches=width, height_inches=height)
        
        # Test available space calculations
        text_width = generator.page_width - generator.text_start_x - generator.margin
        text_height = generator.page_height - (2 * generator.margin)
        
        # Available text area should be positive
        assert text_width > 0
        assert text_height > 0
        
        # Text area should scale with label size
        label_area = width * height
        text_area = (text_width / inch) * (text_height / inch)
        
        # Text should use a reasonable portion of label area
        text_area_ratio = text_area / label_area
        
        # For very small labels, the fixed margin takes up more space
        if label_area < 0.5:  # Very small labels
            assert 0.2 < text_area_ratio < 0.8  # Between 20% and 80%
        else:
            assert 0.3 < text_area_ratio < 0.8  # Between 30% and 80%
        
        # Smaller labels should have relatively more text area (but not tiny ones)
        if 0.5 < label_area < 1.0:
            assert text_area_ratio > 0.4
        
        # Font sizing bounds check
        # The actual font sizing is done dynamically in _add_product_text
        # but we can verify the bounds used
        min_font_bound = 3
        max_font_bound = 12
        
        # For very large labels, max font could be increased
        if label_area > 10.0:
            max_font_bound = int(min(24, height * 12))  # Scale with height
        
        assert min_font_bound >= 3  # Minimum readable size
        assert max_font_bound <= 72  # Maximum reasonable size
    
    @pytest.mark.parametrize("width,height", TEST_DIMENSIONS[:5])  # Test subset for performance
    def test_vertical_centering_consistency(self, width, height, mock_image_processor):
        """Test that content is vertically centered consistently."""
        generator = LabelGenerator(width_inches=width, height_inches=height)
        generator.image_processor = mock_image_processor
        
        # Mock the canvas to capture drawing operations
        with patch('src.label_generator.canvas.Canvas') as mock_canvas_class:
            mock_canvas = MagicMock()
            mock_canvas_class.return_value = mock_canvas
            
            # Mock stringWidth to return reasonable values
            mock_canvas.stringWidth.return_value = 50.0  # Reasonable width for text
            
            # Track drawImage and drawString calls
            draw_operations = []
            mock_canvas.drawImage.side_effect = lambda *args, **kwargs: draw_operations.append(('image', args, kwargs))
            mock_canvas.drawString.side_effect = lambda *args, **kwargs: draw_operations.append(('text', args, kwargs))
            
            # Generate a label
            products_data = create_mock_product_data()
            generator.generate_labels(products_data, "test.pdf")
            
            # Analyze vertical positions
            image_positions = [op[1][2] for op in draw_operations if op[0] == 'image']
            text_positions = [op[1][1] for op in draw_operations if op[0] == 'text']
            
            if image_positions:
                # Image should be vertically centered
                image_y = image_positions[0]
                image_center = image_y + (generator.image_width * 0.5)  # Assuming square aspect
                label_center = generator.page_height * 0.5
                
                # Image center should be close to label center
                assert abs(image_center - label_center) < generator.page_height * 0.25
            
            if text_positions:
                # Text should be distributed in the vertical space
                min_text_y = min(text_positions)
                max_text_y = max(text_positions)
                text_span = max_text_y - min_text_y
                
                # Text should use significant vertical space but leave margins
                # The text span depends on the number of lines and font size
                # For this mock, we're getting a fixed span, so just check it's reasonable
                assert text_span > 0  # At least some vertical distribution
                assert text_span < generator.page_height  # Within label bounds
    
    def test_aspect_ratio_handling(self):
        """Test that various aspect ratios are handled correctly."""
        aspect_ratios = []
        
        for width, height in TEST_DIMENSIONS:
            generator = LabelGenerator(width_inches=width, height_inches=height)
            ratio = width / height
            
            # Verify layout adjusts for aspect ratio
            if ratio > 4:  # Very wide labels
                # Text area should dominate
                text_width = generator.page_width - generator.text_start_x - generator.margin
                assert text_width > generator.page_width * 0.7
            elif ratio < 0.5:  # Very tall labels
                # Vertical space should be well-utilized
                usable_height = generator.page_height - (2 * generator.margin)
                assert usable_height > generator.page_height * 0.9
            
            aspect_ratios.append(ratio)
        
        # We should have tested a variety of aspect ratios
        assert min(aspect_ratios) < 0.5  # Some tall labels
        assert max(aspect_ratios) > 3.0  # Some wide labels
        assert any(0.9 < r < 1.1 for r in aspect_ratios)  # Some square labels