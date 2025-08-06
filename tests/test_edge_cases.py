"""Edge case tests for label generation."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from PIL import Image

from src.label_generator import LabelGenerator


class TestLabelGenerationEdgeCases:
    """Test edge cases and boundary conditions for label generation."""
    
    @pytest.fixture
    def generator(self):
        """Create a LabelGenerator instance."""
        return LabelGenerator()
    
    @pytest.fixture
    def mock_canvas(self):
        """Create a mock canvas."""
        mock_canvas = Mock()
        mock_canvas.stringWidth = Mock(return_value=50)
        return mock_canvas

    def test_extremely_long_text(self, generator):
        """Test handling of extremely long product descriptions."""
        extreme_data = {
            "EXTREME001": {
                "info": {
                    "FamilyDescription": "Ultra High Performance " * 20 + "Socket Head Cap Screw",
                    "DetailDescription": "Black-Oxide Coated with Advanced Corrosion Resistance Technology " * 10 + "M10 x 1.5 mm Thread",
                    "Specifications": [
                        {"Attribute": "Length", "Values": ["Very long specification text " * 5 + "100 mm"]},
                        {"Attribute": "Thread Size", "Values": ["M10 with extended specifications " * 3]},
                    ]
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                output_path = generator.generate_labels(extreme_data, "extreme_text_test.pdf")
                assert output_path.exists()
                assert output_path.stat().st_size > 0

    def test_unicode_characters(self, generator):
        """Test handling of Unicode characters in product descriptions."""
        unicode_data = {
            "UNICODE001": {
                "info": {
                    "FamilyDescription": "Screw with Special Characters: ±²³™®©",
                    "DetailDescription": "Metric Thread: M6×1.0mm, Length: 25±0.1mm, Temperature: -40°C to +120°C",
                    "Specifications": [
                        {"Attribute": "Length", "Values": ["25±0.1 mm"]},
                        {"Attribute": "Temperature Range", "Values": ["-40°C to +120°C"]},
                        {"Attribute": "Material", "Values": ["Stainless Steel 316L™"]},
                    ]
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                output_path = generator.generate_labels(unicode_data, "unicode_test.pdf")
                assert output_path.exists()

    def test_empty_strings(self, generator):
        """Test handling of empty strings in product data."""
        empty_string_data = {
            "EMPTY001": {
                "info": {
                    "FamilyDescription": "",
                    "DetailDescription": "",
                    "Specifications": [
                        {"Attribute": "Length", "Values": [""]},
                        {"Attribute": "Thread Size", "Values": []},
                    ]
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                output_path = generator.generate_labels(empty_string_data, "empty_strings_test.pdf")
                assert output_path.exists()

    def test_none_values(self, generator):
        """Test handling of None values in product data."""
        none_data = {
            "NONE001": {
                "info": {
                    "FamilyDescription": None,
                    "DetailDescription": "Valid description",
                    "Specifications": None
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                output_path = generator.generate_labels(none_data, "none_values_test.pdf")
                assert output_path.exists()

    def test_single_character_text(self, generator):
        """Test handling of very short text."""
        short_data = {
            "SHORT001": {
                "info": {
                    "FamilyDescription": "A",
                    "DetailDescription": "B",
                    "Specifications": [
                        {"Attribute": "X", "Values": ["Y"]},
                    ]
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                output_path = generator.generate_labels(short_data, "single_char_test.pdf")
                assert output_path.exists()

    def test_numeric_only_text(self, generator):
        """Test handling of numeric-only text."""
        numeric_data = {
            "NUMERIC001": {
                "info": {
                    "FamilyDescription": "123456789",
                    "DetailDescription": "98765.43210",
                    "Specifications": [
                        {"Attribute": "123", "Values": ["456.789"]},
                    ]
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                output_path = generator.generate_labels(numeric_data, "numeric_test.pdf")
                assert output_path.exists()

    def test_special_characters_only(self, generator):
        """Test handling of special characters only."""
        special_data = {
            "SPECIAL001": {
                "info": {
                    "FamilyDescription": "!@#$%^&*()",
                    "DetailDescription": "<>?:\"{}|",
                    "Specifications": [
                        {"Attribute": "~`[]\\;',./", "Values": ["+=_)(*&^%$#@!"]},
                    ]
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                output_path = generator.generate_labels(special_data, "special_chars_test.pdf")
                assert output_path.exists()

    def test_whitespace_only_text(self, generator):
        """Test handling of whitespace-only text."""
        whitespace_data = {
            "WHITESPACE001": {
                "info": {
                    "FamilyDescription": "   ",
                    "DetailDescription": "\t\n\r",
                    "Specifications": [
                        {"Attribute": "  ", "Values": ["   "]},
                    ]
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                output_path = generator.generate_labels(whitespace_data, "whitespace_test.pdf")
                assert output_path.exists()

    def test_very_large_specifications_array(self, generator):
        """Test handling of products with many specifications."""
        large_specs = [{"Attribute": f"Attr{i}", "Values": [f"Value{i}"]} for i in range(50)]
        large_specs_data = {
            "LARGESPECS001": {
                "info": {
                    "FamilyDescription": "Product with Many Specifications",
                    "DetailDescription": "This product has an unusually large number of specifications",
                    "Specifications": large_specs
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                output_path = generator.generate_labels(large_specs_data, "large_specs_test.pdf")
                assert output_path.exists()

    def test_corrupted_image_file(self, generator):
        """Test handling of corrupted image files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a corrupted image file
            corrupted_image_path = Path(temp_dir) / "corrupted.png"
            with open(corrupted_image_path, 'wb') as f:
                f.write(b"This is not a valid image file")
            
            corrupted_data = {
                "CORRUPTED001": {
                    "info": {
                        "FamilyDescription": "Product with Corrupted Image",
                        "DetailDescription": "Test corrupted image handling",
                        "Specifications": []
                    },
                    "image_path": str(corrupted_image_path),
                    "cad_path": None
                }
            }
            
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                # Should handle gracefully and still create PDF
                output_path = generator.generate_labels(corrupted_data, "corrupted_image_test.pdf")
                assert output_path.exists()

    def test_nonexistent_image_file(self, generator):
        """Test handling of nonexistent image files."""
        nonexistent_data = {
            "NONEXISTENT001": {
                "info": {
                    "FamilyDescription": "Product with Nonexistent Image",
                    "DetailDescription": "Test missing image file handling",
                    "Specifications": []
                },
                "image_path": "/path/that/does/not/exist.png",
                "cad_path": None
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                output_path = generator.generate_labels(nonexistent_data, "nonexistent_image_test.pdf")
                assert output_path.exists()

    def test_minimum_font_size_boundary(self, generator, mock_canvas):
        """Test behavior at minimum font size boundary."""
        # Mock stringWidth to always return a large value, forcing minimum font size
        mock_canvas.stringWidth.return_value = 1000  # Very wide text
        
        font_size = generator._find_optimal_font_size(
            mock_canvas, "Very long text that won't fit", 50, 20, "Helvetica", 
            min_size=3, max_size=12
        )
        
        assert font_size == 3  # Should hit minimum

    def test_maximum_font_size_boundary(self, generator, mock_canvas):
        """Test behavior at maximum font size boundary."""
        # Mock stringWidth to always return a small value, allowing maximum font size
        mock_canvas.stringWidth.return_value = 10  # Very narrow text
        
        font_size = generator._find_optimal_font_size(
            mock_canvas, "Short", 200, 100, "Helvetica", 
            min_size=6, max_size=12
        )
        
        assert font_size == 12  # Should hit maximum

    def test_zero_dimensions(self, generator, mock_canvas):
        """Test handling of zero dimensions."""
        font_size = generator._find_optimal_font_size(
            mock_canvas, "Test text", 0, 0, "Helvetica", min_size=6, max_size=12
        )
        
        assert font_size == 6  # Should return minimum size

    def test_negative_dimensions(self, generator, mock_canvas):
        """Test handling of negative dimensions."""
        font_size = generator._find_optimal_font_size(
            mock_canvas, "Test text", -10, -10, "Helvetica", min_size=6, max_size=12
        )
        
        assert font_size == 6  # Should return minimum size

    def test_single_word_too_long(self, generator, mock_canvas):
        """Test handling of single word that's too long to fit."""
        def mock_string_width(text, font, size):
            return len(text) * 10  # Make single words very wide
        
        mock_canvas.stringWidth.side_effect = mock_string_width
        
        lines = generator._wrap_text_with_font(
            mock_canvas, "Supercalifragilisticexpialidocious", 50, 10, "Helvetica"
        )
        
        # Should still include the word even if it doesn't fit
        assert len(lines) >= 1
        assert "Supercalifragilisticexpialidocious" in lines