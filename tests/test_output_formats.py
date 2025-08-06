import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
import tempfile
import os

from src.output_formats import (
    OutputFormat, detect_format_from_filename, is_raster_format,
    supports_multiple_pages, get_pil_format_string, get_default_dpi,
    validate_dpi, save_image_with_metadata
)
from src.label_generator import LabelGenerator


class TestOutputFormatDetection:
    """Test output format detection from filenames."""
    
    def test_detect_pdf_format(self):
        assert detect_format_from_filename("labels.pdf") == OutputFormat.PDF
        assert detect_format_from_filename("Labels.PDF") == OutputFormat.PDF
        assert detect_format_from_filename("/path/to/file.pdf") == OutputFormat.PDF
    
    def test_detect_image_formats(self):
        assert detect_format_from_filename("label.png") == OutputFormat.PNG
        assert detect_format_from_filename("label.jpg") == OutputFormat.JPG
        assert detect_format_from_filename("label.jpeg") == OutputFormat.JPEG
        assert detect_format_from_filename("label.bmp") == OutputFormat.BMP
        assert detect_format_from_filename("label.tiff") == OutputFormat.TIFF
        assert detect_format_from_filename("label.tif") == OutputFormat.TIF
        assert detect_format_from_filename("label.gif") == OutputFormat.GIF
        assert detect_format_from_filename("label.webp") == OutputFormat.WEBP
    
    def test_detect_case_insensitive(self):
        assert detect_format_from_filename("label.PNG") == OutputFormat.PNG
        assert detect_format_from_filename("label.Jpg") == OutputFormat.JPG
        assert detect_format_from_filename("label.TIFF") == OutputFormat.TIFF
    
    def test_detect_invalid_format(self):
        with pytest.raises(ValueError, match="Unsupported"):
            detect_format_from_filename("label.txt")
        with pytest.raises(ValueError, match="Unsupported"):
            detect_format_from_filename("label.doc")
        with pytest.raises(ValueError, match="Unsupported"):
            detect_format_from_filename("label")  # No extension
    
    def test_detect_with_path(self):
        assert detect_format_from_filename("/some/path/to/labels.png") == OutputFormat.PNG
        assert detect_format_from_filename("C:\\Windows\\labels.jpg") == OutputFormat.JPG


class TestFormatProperties:
    """Test format property queries."""
    
    def test_is_raster_format(self):
        assert not is_raster_format(OutputFormat.PDF)
        assert is_raster_format(OutputFormat.PNG)
        assert is_raster_format(OutputFormat.JPG)
        assert is_raster_format(OutputFormat.JPEG)
        assert is_raster_format(OutputFormat.BMP)
        assert is_raster_format(OutputFormat.TIFF)
        assert is_raster_format(OutputFormat.GIF)
        assert is_raster_format(OutputFormat.WEBP)
    
    def test_supports_multiple_pages(self):
        assert supports_multiple_pages(OutputFormat.PDF)
        assert supports_multiple_pages(OutputFormat.TIFF)
        assert supports_multiple_pages(OutputFormat.TIF)
        assert not supports_multiple_pages(OutputFormat.PNG)
        assert not supports_multiple_pages(OutputFormat.JPG)
        assert not supports_multiple_pages(OutputFormat.BMP)
        assert not supports_multiple_pages(OutputFormat.GIF)
        assert not supports_multiple_pages(OutputFormat.WEBP)
    
    def test_get_pil_format_string(self):
        assert get_pil_format_string(OutputFormat.PNG) == "PNG"
        assert get_pil_format_string(OutputFormat.JPG) == "JPEG"
        assert get_pil_format_string(OutputFormat.JPEG) == "JPEG"
        assert get_pil_format_string(OutputFormat.BMP) == "BMP"
        assert get_pil_format_string(OutputFormat.TIFF) == "TIFF"
        assert get_pil_format_string(OutputFormat.TIF) == "TIFF"
        assert get_pil_format_string(OutputFormat.GIF) == "GIF"
        assert get_pil_format_string(OutputFormat.WEBP) == "WEBP"


class TestDPIHandling:
    """Test DPI validation and defaults."""
    
    def test_default_dpi(self):
        assert get_default_dpi() == 300  # Common laser printer resolution
    
    def test_validate_dpi_valid(self):
        # Should not raise
        validate_dpi(72)
        validate_dpi(150)
        validate_dpi(300)
        validate_dpi(600)
        validate_dpi(1200)
        validate_dpi(2400)
    
    def test_validate_dpi_too_low(self):
        with pytest.raises(ValueError, match="at least"):
            validate_dpi(50)
        with pytest.raises(ValueError, match="at least"):
            validate_dpi(0)
        with pytest.raises(ValueError, match="at least"):
            validate_dpi(-100)
    
    def test_validate_dpi_too_high(self):
        with pytest.raises(ValueError, match="not exceed"):
            validate_dpi(2401)
        with pytest.raises(ValueError, match="not exceed"):
            validate_dpi(5000)


class TestImageSaving:
    """Test image saving with metadata."""
    
    def test_save_png_with_dpi(self):
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            try:
                # Create test image
                img = Image.new('RGB', (300, 150), 'white')
                
                # Save with DPI
                save_image_with_metadata(img, Path(tmp.name), OutputFormat.PNG, 300)
                
                # Verify saved image
                saved_img = Image.open(tmp.name)
                dpi_info = saved_img.info.get('dpi')
                assert dpi_info is not None
                # Allow for floating point precision differences
                assert abs(dpi_info[0] - 300) < 0.01
                assert abs(dpi_info[1] - 300) < 0.01
                assert saved_img.size == (300, 150)
            finally:
                os.unlink(tmp.name)
    
    def test_save_jpg_with_quality(self):
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            try:
                # Create test image
                img = Image.new('RGB', (300, 150), 'white')
                
                # Save with DPI
                save_image_with_metadata(img, Path(tmp.name), OutputFormat.JPG, 150)
                
                # Verify saved image
                saved_img = Image.open(tmp.name)
                assert saved_img.info.get('dpi') == (150, 150)
                assert saved_img.size == (300, 150)
            finally:
                os.unlink(tmp.name)


class TestLabelGeneratorFormats:
    """Test label generation in different formats."""
    
    @pytest.fixture
    def mock_products_data(self):
        """Create mock product data."""
        return {
            "91290A115": {
                "info": {
                    "short_description": "Test Part",
                    "specs": [{"name": "Size", "value": "1/4\""}]
                },
                "image_path": None,
                "cad_path": None
            }
        }
    
    @pytest.fixture
    def generator(self):
        """Create label generator."""
        return LabelGenerator(width_inches=1.5, height_inches=0.5)
    
    def test_generate_pdf(self, generator, mock_products_data):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.pdf"
            
            # Mock OUTPUT_DIR
            with patch('src.label_generator.OUTPUT_DIR', Path(tmpdir)):
                result = generator.generate_labels(
                    mock_products_data,
                    "test.pdf",
                    OutputFormat.PDF
                )
            
            assert result.name == "test.pdf"
            assert result.exists()
            assert result.stat().st_size > 0
    
    @patch('src.label_generator.ImageFont')
    def test_generate_png(self, mock_font, generator, mock_products_data):
        # Mock font loading
        mock_font.load_default.return_value = MagicMock()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.png"
            
            # Mock OUTPUT_DIR
            with patch('src.label_generator.OUTPUT_DIR', Path(tmpdir)):
                result = generator.generate_labels(
                    mock_products_data,
                    "test.png",
                    OutputFormat.PNG,
                    dpi=150
                )
            
            assert result.name == "test.png"
            assert result.exists()
            
            # Check image properties
            img = Image.open(result)
            assert img.format == "PNG"
            dpi_info = img.info.get('dpi', (150, 150))
            # Allow for floating point precision differences
            assert abs(dpi_info[0] - 150) < 1
            assert abs(dpi_info[1] - 150) < 1
            # Check dimensions match label size at DPI
            assert img.size == (int(1.5 * 150), int(0.5 * 150))
    
    @patch('src.label_generator.ImageFont')
    def test_generate_multiple_images(self, mock_font, generator):
        """Test generating multiple images for non-multipage formats."""
        # Mock font loading
        mock_font.load_default.return_value = MagicMock()
        
        # Multiple products
        products_data = {
            "PART1": {"info": {"short_description": "Part 1"}},
            "PART2": {"info": {"short_description": "Part 2"}},
            "PART3": {"info": {"short_description": "Part 3"}}
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock OUTPUT_DIR
            with patch('src.label_generator.OUTPUT_DIR', Path(tmpdir)):
                result = generator.generate_labels(
                    products_data,
                    "test.png",
                    OutputFormat.PNG,
                    dpi=100
                )
            
            # Should create numbered files
            assert (Path(tmpdir) / "test_001.png").exists()
            assert (Path(tmpdir) / "test_002.png").exists()
            assert (Path(tmpdir) / "test_003.png").exists()


class TestDimensionFormatCombinations:
    """Test various combinations of dimensions, formats, and DPI."""
    
    # Test matrix: dimensions x formats x DPI
    test_cases = [
        # (width, height, format, dpi, expected_pixels)
        (1.5, 0.5, OutputFormat.PNG, 300, (450, 150)),
        (2.0, 1.0, OutputFormat.PNG, 150, (300, 150)),
        (1.0, 1.0, OutputFormat.JPG, 300, (300, 300)),
        (3.0, 1.5, OutputFormat.BMP, 100, (300, 150)),
        (0.5, 0.5, OutputFormat.PNG, 600, (300, 300)),
        (4.0, 2.0, OutputFormat.TIFF, 150, (600, 300)),
        # Metric sizes
        (1.97, 0.79, OutputFormat.PNG, 300, (591, 237)),  # 50mm x 20mm
        (3.94, 1.97, OutputFormat.JPG, 150, (591, 296)),  # 100mm x 50mm
    ]
    
    @pytest.mark.parametrize("width,height,format,dpi,expected_pixels", test_cases)
    @patch('src.label_generator.ImageFont')
    def test_dimension_format_dpi_combination(self, mock_font, width, height, 
                                            format, dpi, expected_pixels):
        """Test specific combinations of dimensions, formats, and DPI."""
        # Mock font loading
        mock_font.load_default.return_value = MagicMock()
        
        generator = LabelGenerator(width_inches=width, height_inches=height)
        
        products_data = {
            "TEST": {"info": {"short_description": "Test Part"}}
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = f"test.{format.value}"
            
            # Mock OUTPUT_DIR
            with patch('src.label_generator.OUTPUT_DIR', Path(tmpdir)):
                result = generator.generate_labels(
                    products_data,
                    filename,
                    format,
                    dpi=dpi
                )
            
            # For single product, file should exist directly
            if format not in (OutputFormat.TIFF, OutputFormat.TIF):
                assert result.name == filename
            assert result.exists() or result.is_dir()
            
            # Check generated image
            if result.is_file():
                img = Image.open(result)
                # Allow small rounding differences
                assert abs(img.width - expected_pixels[0]) <= 1
                assert abs(img.height - expected_pixels[1]) <= 1
                if hasattr(img, 'info') and 'dpi' in img.info:
                    dpi_info = img.info['dpi']
                    # Allow for floating point precision differences
                    assert abs(dpi_info[0] - dpi) < 1
                    assert abs(dpi_info[1] - dpi) < 1