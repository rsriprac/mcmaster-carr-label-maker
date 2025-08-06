import pytest
import os
from src.dimensions import (
    parse_dimension, get_cached_dimensions, cache_dimensions,
    validate_dimensions, format_dimension_for_display
)


class TestDimensionParsing:
    """Test dimension parsing with various units."""
    
    def test_parse_inches(self):
        """Test parsing dimensions in inches."""
        assert parse_dimension("1.5in") == 1.5
        assert parse_dimension("2in") == 2.0
        assert parse_dimension("0.5in") == 0.5
        assert parse_dimension("10.25in") == 10.25
    
    def test_parse_no_unit_defaults_to_inches(self):
        """Test that dimensions without units default to inches."""
        assert parse_dimension("1.5") == 1.5
        assert parse_dimension("2") == 2.0
        assert parse_dimension("0.5") == 0.5
        assert parse_dimension("10.25") == 10.25
        assert parse_dimension("3.14159") == 3.14159
    
    def test_parse_millimeters(self):
        """Test parsing dimensions in millimeters."""
        assert parse_dimension("25.4mm") == pytest.approx(1.0, rel=1e-3)
        assert parse_dimension("100mm") == pytest.approx(3.937, rel=1e-3)
        assert parse_dimension("50.8mm") == pytest.approx(2.0, rel=1e-3)
    
    def test_parse_centimeters(self):
        """Test parsing dimensions in centimeters."""
        assert parse_dimension("2.54cm") == pytest.approx(1.0, rel=1e-3)
        assert parse_dimension("10cm") == pytest.approx(3.937, rel=1e-3)
        assert parse_dimension("5.08cm") == pytest.approx(2.0, rel=1e-3)
    
    def test_parse_meters(self):
        """Test parsing dimensions in meters."""
        assert parse_dimension("0.0254m") == pytest.approx(1.0, rel=1e-3)
        assert parse_dimension("0.1m") == pytest.approx(3.937, rel=1e-3)
    
    def test_parse_feet(self):
        """Test parsing dimensions in feet."""
        assert parse_dimension("1ft") == 12.0
        assert parse_dimension("0.5ft") == 6.0
        assert parse_dimension("2.5ft") == 30.0
    
    def test_parse_points(self):
        """Test parsing dimensions in points (typography)."""
        assert parse_dimension("72pt") == pytest.approx(1.0, rel=1e-3)
        assert parse_dimension("36pt") == pytest.approx(0.5, rel=1e-3)
    
    def test_parse_pixels_at_96dpi(self):
        """Test parsing dimensions in pixels (assuming 96 DPI standard)."""
        assert parse_dimension("96px") == pytest.approx(1.0, rel=1e-3)
        assert parse_dimension("192px") == pytest.approx(2.0, rel=1e-3)
    
    def test_parse_without_units(self):
        """Test parsing dimensions without explicit units defaults to inches."""
        assert parse_dimension("1.5") == 1.5
        assert parse_dimension("2.0") == 2.0
        assert parse_dimension("0.5") == 0.5
    
    def test_parse_invalid_format(self):
        """Test parsing invalid dimension formats."""
        with pytest.raises(ValueError):
            parse_dimension("abc")
        with pytest.raises(ValueError):
            parse_dimension("")
        with pytest.raises(ValueError):
            parse_dimension("12xyz")  # Invalid unit
    
    def test_parse_negative_values(self):
        """Test parsing negative dimensions (should work but validation will catch)."""
        assert parse_dimension("-1.5in") == -1.5
    
    def test_parse_with_spaces(self):
        """Test parsing dimensions with spaces."""
        assert parse_dimension("1.5 in") == 1.5
        assert parse_dimension("100 mm") == pytest.approx(3.937, rel=1e-3)
        assert parse_dimension("2.54 cm") == pytest.approx(1.0, rel=1e-3)


class TestDimensionValidation:
    """Test dimension validation."""
    
    def test_validate_normal_dimensions(self):
        """Test validation of normal label dimensions."""
        # Should not raise
        validate_dimensions(1.5, 0.5)
        validate_dimensions(2.0, 1.0)
        validate_dimensions(4.0, 6.0)
        validate_dimensions(12.0, 12.0)
    
    def test_validate_minimum_size(self):
        """Test validation rejects too small dimensions."""
        with pytest.raises(ValueError, match="at least"):
            validate_dimensions(0.1, 0.5)
        with pytest.raises(ValueError, match="at least"):
            validate_dimensions(0.5, 0.1)
        with pytest.raises(ValueError, match="at least"):
            validate_dimensions(0.1, 0.1)
    
    def test_validate_maximum_size(self):
        """Test validation rejects too large dimensions."""
        with pytest.raises(ValueError, match="not exceed"):
            validate_dimensions(13.0, 5.0)
        with pytest.raises(ValueError, match="not exceed"):
            validate_dimensions(5.0, 13.0)
        with pytest.raises(ValueError, match="not exceed"):
            validate_dimensions(13.0, 13.0)
    
    def test_validate_zero_dimensions(self):
        """Test validation rejects zero dimensions."""
        with pytest.raises(ValueError, match="positive"):
            validate_dimensions(0, 1.0)
        with pytest.raises(ValueError, match="positive"):
            validate_dimensions(1.0, 0)
        with pytest.raises(ValueError, match="positive"):
            validate_dimensions(0, 0)
    
    def test_validate_negative_dimensions(self):
        """Test validation rejects negative dimensions."""
        with pytest.raises(ValueError, match="positive"):
            validate_dimensions(-1.5, 0.5)
        with pytest.raises(ValueError, match="positive"):
            validate_dimensions(1.5, -0.5)
        with pytest.raises(ValueError, match="positive"):
            validate_dimensions(-1.5, -0.5)
    
    def test_validate_extreme_aspect_ratios(self, capsys):
        """Test validation warns about extreme aspect ratios."""
        # Very wide (10:1)
        validate_dimensions(10.0, 1.0)
        captured = capsys.readouterr()
        assert "Unusual aspect ratio" in captured.out
        
        # Very tall (1:10)
        validate_dimensions(1.0, 10.0)
        captured = capsys.readouterr()
        assert "Unusual aspect ratio" in captured.out
        
        # Normal aspect ratio should not warn
        validate_dimensions(1.5, 0.5)
        captured = capsys.readouterr()
        assert "Unusual aspect ratio" not in captured.out


class TestDimensionCaching:
    """Test dimension caching functionality."""
    
    def teardown_method(self):
        """Clean up environment variables after each test."""
        os.environ.pop('MCMASTER_LABEL_WIDTH', None)
        os.environ.pop('MCMASTER_LABEL_HEIGHT', None)
    
    def test_cache_dimensions(self):
        """Test caching dimensions to environment."""
        cache_dimensions(2.0, 1.0)
        assert os.getenv('MCMASTER_LABEL_WIDTH') == '2.0'
        assert os.getenv('MCMASTER_LABEL_HEIGHT') == '1.0'
    
    def test_get_cached_dimensions(self):
        """Test retrieving cached dimensions."""
        # No cached dimensions
        width, height = get_cached_dimensions()
        assert width is None
        assert height is None
        
        # Cache some dimensions
        cache_dimensions(3.0, 1.5)
        width, height = get_cached_dimensions()
        assert width == 3.0
        assert height == 1.5
    
    def test_get_cached_dimensions_invalid(self):
        """Test retrieving invalid cached dimensions."""
        # Set invalid values
        os.environ['MCMASTER_LABEL_WIDTH'] = 'invalid'
        os.environ['MCMASTER_LABEL_HEIGHT'] = '1.0'
        
        width, height = get_cached_dimensions()
        assert width is None
        assert height is None
    
    def test_get_cached_dimensions_partial(self):
        """Test retrieving partial cached dimensions."""
        # Only width cached
        os.environ['MCMASTER_LABEL_WIDTH'] = '2.0'
        width, height = get_cached_dimensions()
        assert width is None
        assert height is None
        
        # Only height cached
        os.environ.pop('MCMASTER_LABEL_WIDTH', None)
        os.environ['MCMASTER_LABEL_HEIGHT'] = '1.0'
        width, height = get_cached_dimensions()
        assert width is None
        assert height is None


class TestDimensionFormatting:
    """Test dimension formatting for display."""
    
    def test_format_dimension_for_display(self):
        """Test formatting dimensions for display."""
        assert format_dimension_for_display(1.5) == "1.50in"
        assert format_dimension_for_display(2.0) == "2.00in"
        assert format_dimension_for_display(0.5) == "0.50in"
        assert format_dimension_for_display(10.25) == "10.25in"
        assert format_dimension_for_display(1.333) == "1.33in"
        assert format_dimension_for_display(1.337) == "1.34in"  # Rounds up


class TestDimensionIntegration:
    """Integration tests for dimension handling."""
    
    def teardown_method(self):
        """Clean up environment variables after each test."""
        os.environ.pop('MCMASTER_LABEL_WIDTH', None)
        os.environ.pop('MCMASTER_LABEL_HEIGHT', None)
    
    def test_parse_cache_retrieve_cycle(self):
        """Test full cycle of parsing, caching, and retrieving dimensions."""
        # Parse dimensions
        width = parse_dimension("100mm")
        height = parse_dimension("2.54cm")
        
        # Validate
        validate_dimensions(width, height)
        
        # Cache
        cache_dimensions(width, height)
        
        # Retrieve
        cached_width, cached_height = get_cached_dimensions()
        assert cached_width == pytest.approx(width, rel=1e-6)
        assert cached_height == pytest.approx(height, rel=1e-6)
        
        # Format for display
        assert "in" in format_dimension_for_display(cached_width)
        assert "in" in format_dimension_for_display(cached_height)