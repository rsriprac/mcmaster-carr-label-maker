"""Comprehensive test cases to ensure no text gets clipped off the page."""

import pytest
from pathlib import Path
import json
from unittest.mock import patch
import io
from reportlab.pdfgen import canvas

from src.label_generator import LabelGenerator
from src.config import LABEL_WIDTH_INCHES, LABEL_HEIGHT_INCHES


class TestNoClipping:
    """Test suite to prevent text clipping issues."""
    
    @pytest.fixture
    def generator(self):
        """Create a LabelGenerator instance."""
        return LabelGenerator()
    
    @pytest.fixture
    def mock_canvas(self, generator):
        """Create a mock canvas for testing."""
        buffer = io.BytesIO()
        return canvas.Canvas(buffer, pagesize=(generator.page_width, generator.page_height))
    
    def _check_element_bounds(self, element, margin, page_height, element_name):
        """Helper to check if an element is within page bounds."""
        if not element:
            return True, None
            
        # Calculate actual top and bottom positions
        font_size = element['font_size']
        y_start = element['y_start']
        lines = element['lines']
        line_height = element['line_height']
        
        # Top of text includes ascent
        ascent = font_size * 0.75
        top_y = y_start + ascent
        
        # Bottom depends on number of lines
        if len(lines) == 1:
            bottom_y = y_start  # Baseline is bottom for single line
        else:
            bottom_y = y_start - ((len(lines) - 1) * line_height)
        
        # Check bounds with small tolerance for floating point precision
        tolerance = 0.1
        if top_y > (page_height - margin + tolerance):
            return False, f"{element_name} top ({top_y:.1f}) exceeds top margin"
        if bottom_y < (margin - tolerance):
            return False, f"{element_name} bottom ({bottom_y:.1f}) below bottom margin by {margin - bottom_y:.1f} points"
            
        return True, None
    
    def test_no_clipping_with_o_ring_products(self, generator, mock_canvas):
        """Test all O-ring products to ensure no clipping."""
        # Read O-ring product IDs
        o_rings_file = Path("product_id.o-rings.txt")
        if not o_rings_file.exists():
            pytest.skip("O-rings product file not found")
            
        with open(o_rings_file) as f:
            product_ids = [line.strip() for line in f if line.strip()]
        
        clipping_issues = []
        
        for product_id in product_ids:
            cache_file = Path(f"cache/product_{product_id}.json")
            if not cache_file.exists():
                continue
                
            with open(cache_file) as f:
                product_info = json.load(f)
            
            # Extract text components
            description = generator._get_product_description(product_info)
            dimensions = generator._get_dimensions_text(product_info)
            product_id_text = f"ID: {product_id}"
            
            # Calculate layout
            text_width = generator.page_width - generator.text_start_x - generator.margin
            text_height = generator.page_height - (2 * generator.margin)
            
            layout = generator._calculate_optimal_text_layout(
                mock_canvas, description, dimensions, product_id_text, text_width, text_height
            )
            
            # Check bounds for each element
            desc_ok, desc_msg = self._check_element_bounds(
                layout['description'], generator.margin, generator.page_height, "Description"
            )
            dim_ok, dim_msg = self._check_element_bounds(
                layout.get('dimensions'), generator.margin, generator.page_height, "Dimensions"
            )
            id_ok, id_msg = self._check_element_bounds(
                layout['product_id'], generator.margin, generator.page_height, "Product ID"
            )
            
            if not all([desc_ok, dim_ok, id_ok]):
                issues = [msg for ok, msg in [(desc_ok, desc_msg), (dim_ok, dim_msg), (id_ok, id_msg)] if not ok]
                clipping_issues.append(f"{product_id}: {', '.join(issues)}")
        
        # Assert no clipping issues
        assert len(clipping_issues) == 0, f"Clipping detected:\n" + "\n".join(clipping_issues)
    
    def test_no_clipping_with_realistic_text(self, generator, mock_canvas):
        """Test realistic text cases to ensure no clipping."""
        text_width = generator.page_width - generator.text_start_x - generator.margin
        text_height = generator.page_height - (2 * generator.margin)
        
        realistic_cases = [
            {
                "name": "Standard product",
                "description": "Alloy Steel Socket Head Cap Screw",
                "dimensions": "M8 x 1.25mm Thread, 50mm Length",
                "product_id": "91290A115"
            },
            {
                "name": "O-Ring",
                "description": "Chemical-Resistant Viton Fluoroelastomer O-Ring",
                "dimensions": "",  # No dimensions
                "product_id": "9464K15"
            },
            {
                "name": "Longer description",
                "description": "High-Strength Socket Head Cap Screw with Black-Oxide Coating",
                "dimensions": "M10 x 1.5mm Thread",
                "product_id": "TEST123"
            },
            {
                "name": "Short everything",
                "description": "Fastener",
                "dimensions": "M6",
                "product_id": "SHORT"
            }
        ]
        
        for case in realistic_cases:
            layout = generator._calculate_optimal_text_layout(
                mock_canvas,
                case["description"],
                case["dimensions"],
                f"ID: {case['product_id']}",
                text_width,
                text_height
            )
            
            # Check all elements are within bounds
            desc_ok, desc_msg = self._check_element_bounds(
                layout['description'], generator.margin, generator.page_height, "Description"
            )
            dim_ok, dim_msg = self._check_element_bounds(
                layout.get('dimensions'), generator.margin, generator.page_height, "Dimensions"
            )
            id_ok, id_msg = self._check_element_bounds(
                layout['product_id'], generator.margin, generator.page_height, "Product ID"
            )
            
            assert desc_ok, f"Description clipped for case '{case['name']}': {desc_msg}"
            assert dim_ok or not layout.get('dimensions'), f"Dimensions clipped for case '{case['name']}': {dim_msg}"
            assert id_ok, f"Product ID clipped for case '{case['name']}': {id_msg}"
    
    def test_font_priority_maintained(self, generator, mock_canvas):
        """Test that font priority is maintained while preventing clipping."""
        text_width = generator.page_width - generator.text_start_x - generator.margin
        text_height = generator.page_height - (2 * generator.margin)
        
        # Test with dimensions present
        layout = generator._calculate_optimal_text_layout(
            mock_canvas,
            "Test Product Description",
            "M8 x 25mm",
            "ID: TEST123",
            text_width,
            text_height
        )
        
        desc_font = layout['description']['font_size']
        dim_font = layout['dimensions']['font_size']
        id_font = layout['product_id']['font_size']
        
        # Dimensions should be largest (or equal), ID should be smallest
        assert dim_font >= desc_font, f"Dimensions font ({dim_font}) should be >= description ({desc_font})"
        assert desc_font >= id_font, f"Description font ({desc_font}) should be >= ID ({id_font})"
        
        # Test without dimensions
        layout_no_dim = generator._calculate_optimal_text_layout(
            mock_canvas,
            "Test Product Description",
            "",
            "ID: TEST456",
            text_width,
            text_height
        )
        
        desc_font_no_dim = layout_no_dim['description']['font_size']
        id_font_no_dim = layout_no_dim['product_id']['font_size']
        
        # Description should be larger than ID
        assert desc_font_no_dim >= id_font_no_dim, f"Description font ({desc_font_no_dim}) should be >= ID ({id_font_no_dim})"
    
    def test_total_height_calculation(self, generator, mock_canvas):
        """Test that total height calculations are accurate."""
        text_width = generator.page_width - generator.text_start_x - generator.margin
        text_height = generator.page_height - (2 * generator.margin)
        
        layout = generator._calculate_optimal_text_layout(
            mock_canvas,
            "Test Product with Standard Text",
            "M6 x 20mm",
            "ID: HEIGHT001",
            text_width,
            text_height
        )
        
        # Calculate actual total height used
        desc = layout['description']
        dim = layout['dimensions']
        pid = layout['product_id']
        
        # Top of first element (with ascent)
        top_y = desc['y_start'] + (desc['font_size'] * 0.75)
        
        # Bottom of last element
        bottom_y = pid['y_start']
        
        # Total height used
        total_used = top_y - bottom_y
        
        # Should not exceed available height
        assert total_used <= text_height, f"Total height used ({total_used:.1f}) exceeds available ({text_height:.1f})"
        
        # Should be reasonably close to available height (good space utilization)
        utilization = (total_used / text_height) * 100
        assert utilization > 50, f"Poor space utilization: only {utilization:.1f}% used"
    
    def test_fallback_algorithm_no_clipping(self, generator):
        """Test that fallback algorithm also prevents clipping."""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=(generator.page_width, generator.page_height))
        
        text_width = generator.page_width - generator.text_start_x - generator.margin
        text_height = generator.page_height - (2 * generator.margin)
        
        # Call fallback directly
        layout = generator._fallback_layout_algorithm(
            c,
            "Fallback Test Product Description",
            "M8 x 30mm",
            "ID: FALLBACK001",
            text_width,
            text_height
        )
        
        # Check all elements are within bounds
        for element_name, element in [('description', layout['description']), 
                                     ('dimensions', layout.get('dimensions')),
                                     ('product_id', layout['product_id'])]:
            if element:
                ok, msg = self._check_element_bounds(
                    element, generator.margin, generator.page_height, element_name
                )
                assert ok, f"Fallback algorithm: {msg}"
    
    def test_actual_pdf_generation_no_clipping(self, generator):
        """Integration test with actual PDF generation."""
        # Test data that previously caused clipping
        test_products = {
            "9464K15": {
                "info": {
                    "FamilyDescription": "Chemical-Resistant Viton® Fluoroelastomer O-Ring",
                    "DetailDescription": "1/16 Fractional Width, Dash Number 010",
                    "Specifications": []
                },
                "image_path": None,
                "cad_path": None
            },
            "EXTREME_TEST": {
                "info": {
                    "FamilyDescription": "Extremely Long Product Description That Should Challenge The Layout Algorithm",
                    "DetailDescription": "With Many Technical Details And Specifications That Need To Wrap Properly Without Causing Any Text To Be Clipped Off The Page",
                    "Specifications": [
                        {"Attribute": "Thread Size", "Values": ["M12"]},
                        {"Attribute": "Length", "Values": ["100 mm"]},
                        {"Attribute": "Material", "Values": ["Grade 12.9 Alloy Steel"]},
                    ]
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        # Generate PDF - should not raise any exceptions
        output_path = generator.generate_labels(test_products, "no_clipping_test.pdf")
        
        # Verify PDF was created
        assert output_path.exists()
        assert output_path.stat().st_size > 0
        
        # Clean up
        output_path.unlink()