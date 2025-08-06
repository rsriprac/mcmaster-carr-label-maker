"""Tests for the ImageProcessor class."""

import pytest
import tempfile
from pathlib import Path
from PIL import Image

from src.image_processor import ImageProcessor


class TestImageProcessor:
    """Test the ImageProcessor class."""
    
    @pytest.fixture
    def processor(self):
        """Create an ImageProcessor instance."""
        return ImageProcessor()
    
    @pytest.fixture
    def test_image(self):
        """Create a test image."""
        return Image.new('RGB', (200, 100), color='red')
    
    @pytest.fixture
    def test_image_with_alpha(self):
        """Create a test image with alpha channel."""
        return Image.new('RGBA', (200, 100), color=(255, 0, 0, 128))

    def test_initialization(self, processor):
        """Test ImageProcessor initialization."""
        assert processor.label_width_px > 0
        assert processor.label_height_px > 0
        assert processor.image_width_px > 0
        assert processor.image_width_px < processor.label_width_px

    def test_process_image_rgb(self, processor, test_image):
        """Test processing RGB image."""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            test_image.save(temp_path)
            
            try:
                processed = processor.process_image(temp_path)
                assert processed is not None
                assert processed.mode == 'RGB'
                # Image should not be upscaled, only downscaled if too large
                assert processed.size[0] == test_image.size[0]  # 200px original
                assert processed.size[1] == test_image.size[1]  # 100px original
            finally:
                temp_path.unlink()

    def test_process_image_rgba(self, processor, test_image_with_alpha):
        """Test processing RGBA image (with transparency)."""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            test_image_with_alpha.save(temp_path)
            
            try:
                processed = processor.process_image(temp_path)
                assert processed is not None
                assert processed.mode == 'RGB'  # Should be converted to RGB
            finally:
                temp_path.unlink()

    def test_process_image_nonexistent(self, processor):
        """Test processing nonexistent image file."""
        result = processor.process_image(Path("/nonexistent/path.png"))
        assert result is None

    def test_process_cad_placeholder(self, processor):
        """Test CAD placeholder generation."""
        placeholder = processor.process_cad_placeholder()
        assert placeholder is not None
        assert placeholder.mode == 'RGB'
        assert placeholder.size == (processor.image_width_px, processor.label_height_px)

    def test_get_image_for_product_with_image(self, processor, test_image):
        """Test getting image for product when image file exists."""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            test_image.save(temp_path)
            
            try:
                result = processor.get_image_for_product(temp_path, None)
                assert result is not None
                assert result.mode == 'RGB'
            finally:
                temp_path.unlink()

    def test_get_image_for_product_no_image(self, processor):
        """Test getting image for product when no image file exists."""
        result = processor.get_image_for_product(None, None)
        assert result is not None  # Should return CAD placeholder
        assert result.mode == 'RGB'

    def test_get_image_for_product_with_cad(self, processor):
        """Test getting image for product with CAD file (should use placeholder)."""
        cad_path = Path("/some/cad/file.step")  # Doesn't need to exist for this test
        result = processor.get_image_for_product(None, cad_path)
        assert result is not None  # Should return CAD placeholder
        assert result.mode == 'RGB'

    def test_resize_to_fit_large_image(self, processor):
        """Test resizing large image to fit label dimensions."""
        # Create an image much larger than 3x the target size
        large_image = Image.new('RGB', (3000, 2000), color='blue')
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            large_image.save(temp_path)
            
            try:
                processed = processor.process_image(temp_path)
                assert processed is not None
                # Should be scaled down to fit within 3x the target dimensions
                assert processed.size[0] <= processor.image_width_px * 3
                assert processed.size[1] <= processor.label_height_px * 3
                # But should maintain aspect ratio
                orig_ratio = large_image.size[0] / large_image.size[1]
                new_ratio = processed.size[0] / processed.size[1]
                assert abs(orig_ratio - new_ratio) < 0.01
            finally:
                temp_path.unlink()

    def test_resize_to_fit_small_image(self, processor):
        """Test resizing small image (should be scaled up)."""
        small_image = Image.new('RGB', (50, 25), color='green')
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            small_image.save(temp_path)
            
            try:
                processed = processor.process_image(temp_path)
                assert processed is not None
                # Should maintain aspect ratio and fit within bounds
                assert processed.size[0] <= processor.image_width_px
                assert processed.size[1] <= processor.label_height_px
            finally:
                temp_path.unlink()

    def test_aspect_ratio_preservation(self, processor):
        """Test that the processed image maintains aspect ratio."""
        # Create image smaller than 3x target to avoid resizing
        # Target is 112.5px wide at 300 DPI, so 3x is 337.5px
        original_width, original_height = 300, 150
        
        test_image = Image.new('RGB', (original_width, original_height), color='purple')
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            test_image.save(temp_path)
            
            try:
                processed = processor.process_image(temp_path)
                assert processed is not None
                
                # Since 300x150 is smaller than 3x target, it should not be resized
                assert processed.size[0] == original_width
                assert processed.size[1] == original_height
                
                # The processed image should have reasonable dimensions (not empty)
                assert processed.size[0] > 0
                assert processed.size[1] > 0
            finally:
                temp_path.unlink()

    def test_image_formats(self, processor):
        """Test processing different image formats."""
        formats_to_test = ['PNG', 'JPEG']
        
        for format_name in formats_to_test:
            test_image = Image.new('RGB', (100, 50), color='orange')
            
            with tempfile.NamedTemporaryFile(suffix=f'.{format_name.lower()}', delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                test_image.save(temp_path, format=format_name)
                
                try:
                    processed = processor.process_image(temp_path)
                    assert processed is not None, f"Failed to process {format_name} image"
                    assert processed.mode == 'RGB'
                finally:
                    temp_path.unlink()

    def test_grayscale_image_conversion(self, processor):
        """Test processing grayscale images."""
        grayscale_image = Image.new('L', (100, 50), color=128)
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            grayscale_image.save(temp_path)
            
            try:
                processed = processor.process_image(temp_path)
                assert processed is not None
                assert processed.mode == 'RGB'  # Should be converted to RGB
            finally:
                temp_path.unlink()

    def test_la_image_conversion(self, processor):
        """Test processing LA (grayscale with alpha) images."""
        la_image = Image.new('LA', (100, 50), color=(128, 255))
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            la_image.save(temp_path)
            
            try:
                processed = processor.process_image(temp_path)
                assert processed is not None
                assert processed.mode == 'RGB'  # Should be converted to RGB
            finally:
                temp_path.unlink()

    def test_corrupted_image_handling(self, processor):
        """Test handling of corrupted image files."""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            # Write invalid image data
            temp_file.write(b"This is not a valid image file")
            temp_file.flush()
            
            try:
                result = processor.process_image(temp_path)
                assert result is None  # Should handle gracefully
            finally:
                temp_path.unlink()