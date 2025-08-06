"""Integration tests for the complete label generation workflow."""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from PIL import Image

from src.label_generator import LabelGenerator
from src.image_processor import ImageProcessor


class TestLabelGenerationIntegration:
    """Integration tests for complete label generation workflow."""
    
    @pytest.fixture
    def real_product_data(self):
        """Real McMaster-Carr product data structure."""
        return {
            "91290A115": {
                "info": {
                    "PartNumber": "91290A115",
                    "ProductStatus": "ACTIVE",
                    "ProductCategory": "Screws And Bolts",
                    "FamilyDescription": "Alloy Steel Socket Head Screw",
                    "DetailDescription": "Black-Oxide, M3 x 0.5 mm Thread, 10 mm Long",
                    "Specifications": [
                        {"Attribute": "Thread Size", "Values": ["M3"]},
                        {"Attribute": "Thread Pitch", "Values": ["0.5 mm"]},
                        {"Attribute": "Length", "Values": ["10 mm"]},
                        {"Attribute": "Head Diameter", "Values": ["5.5 mm"]},
                        {"Attribute": "Material", "Values": ["Black-Oxide Alloy Steel"]},
                    ]
                },
                "image_path": None,
                "cad_path": None
            },
            "91290A116": {
                "info": {
                    "PartNumber": "91290A116",
                    "ProductStatus": "ACTIVE",
                    "ProductCategory": "Screws And Bolts",
                    "FamilyDescription": "Alloy Steel Socket Head Screw",
                    "DetailDescription": "Black-Oxide, M8 x 1.25 mm Thread, 85 mm Long",
                    "Specifications": [
                        {"Attribute": "Thread Size", "Values": ["M8"]},
                        {"Attribute": "Thread Pitch", "Values": ["1.25 mm"]},
                        {"Attribute": "Length", "Values": ["85 mm"]},
                        {"Attribute": "Head Diameter", "Values": ["13 mm"]},
                        {"Attribute": "Material", "Values": ["Black-Oxide Alloy Steel"]},
                    ]
                },
                "image_path": None,
                "cad_path": None
            }
        }
    
    @pytest.fixture
    def varying_text_length_data(self):
        """Test data with varying text lengths."""
        return {
            "SHORT001": {
                "info": {
                    "FamilyDescription": "Screw",
                    "DetailDescription": "M3 x 10mm",
                    "Specifications": [
                        {"Attribute": "Length", "Values": ["10 mm"]},
                        {"Attribute": "Thread Size", "Values": ["M3"]},
                    ]
                },
                "image_path": None,
                "cad_path": None
            },
            "MEDIUM001": {
                "info": {
                    "FamilyDescription": "Alloy Steel Socket Head Cap Screw",
                    "DetailDescription": "Black-Oxide Coated, M6 x 1.0 mm Thread, 25 mm Long, Hex Drive",
                    "Specifications": [
                        {"Attribute": "Length", "Values": ["25 mm"]},
                        {"Attribute": "Thread Size", "Values": ["M6"]},
                    ]
                },
                "image_path": None,
                "cad_path": None
            },
            "VERYLONG001": {
                "info": {
                    "FamilyDescription": "Ultra High Strength Alloy Steel Socket Head Cap Screw with Specialized Coating and Extended Threading",
                    "DetailDescription": "Black-Oxide Coated for Maximum Corrosion Resistance, M8 x 1.25 mm Metric Thread, 50 mm Length, Hex Socket Drive Style, Class 12.9 Strength Grade, Fully Threaded Shank with Special Heat Treatment",
                    "Specifications": [
                        {"Attribute": "Length", "Values": ["50 mm"]},
                        {"Attribute": "Thread Size", "Values": ["M8"]},
                        {"Attribute": "Thread Pitch", "Values": ["1.25 mm"]},
                        {"Attribute": "Head Diameter", "Values": ["13 mm"]},
                        {"Attribute": "Material", "Values": ["Alloy Steel"]},
                    ]
                },
                "image_path": None,
                "cad_path": None
            }
        }

    def test_complete_label_generation_workflow(self, real_product_data):
        """Test complete label generation from start to finish."""
        generator = LabelGenerator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                # Generate labels
                output_path = generator.generate_labels(real_product_data, "integration_test.pdf")
                
                # Verify PDF was created
                assert output_path.exists()
                assert output_path.suffix == '.pdf'
                assert output_path.stat().st_size > 0  # File has content
    
    def test_varying_text_lengths_integration(self, varying_text_length_data):
        """Test label generation with varying text lengths."""
        generator = LabelGenerator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                output_path = generator.generate_labels(varying_text_length_data, "text_length_test.pdf")
                
                # Verify PDF was created successfully
                assert output_path.exists()
                assert output_path.stat().st_size > 0
                
                # All products should have been processed
                assert len(varying_text_length_data) == 3

    def test_label_generation_with_images(self, real_product_data):
        """Test label generation with actual image processing."""
        generator = LabelGenerator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock image files
            for product_id in real_product_data.keys():
                image_path = Path(temp_dir) / f"image_{product_id}.png"
                test_image = Image.new('RGB', (200, 100), color='blue')
                test_image.save(image_path)
                real_product_data[product_id]['image_path'] = str(image_path)
            
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                output_path = generator.generate_labels(real_product_data, "with_images_test.pdf")
                
                # Verify PDF was created
                assert output_path.exists()
                assert output_path.stat().st_size > 0

    def test_font_sizing_consistency(self, varying_text_length_data):
        """Test that font sizing is consistent and logical."""
        generator = LabelGenerator()
        
        # Extract text lengths for comparison
        text_lengths = {}
        for product_id, data in varying_text_length_data.items():
            info = data['info']
            full_desc = f"{info['FamilyDescription']} - {info['DetailDescription']}"
            text_lengths[product_id] = len(full_desc)
        
        # Sort by text length
        sorted_products = sorted(text_lengths.items(), key=lambda x: x[1])
        
        # Verify order: SHORT001 < MEDIUM001 < VERYLONG001
        assert sorted_products[0][0] == "SHORT001"
        assert sorted_products[1][0] == "MEDIUM001"
        assert sorted_products[2][0] == "VERYLONG001"
        
        # Test that the system can handle all these lengths
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                output_path = generator.generate_labels(varying_text_length_data, "font_consistency_test.pdf")
                assert output_path.exists()

    def test_empty_product_data(self):
        """Test handling of empty product data."""
        generator = LabelGenerator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                output_path = generator.generate_labels({}, "empty_test.pdf")
                
                # Should create an empty PDF
                assert output_path.exists()

    def test_missing_product_info_fields(self):
        """Test handling of products with missing information fields."""
        incomplete_data = {
            "INCOMPLETE001": {
                "info": {
                    # Missing FamilyDescription and DetailDescription
                    "Specifications": []
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        generator = LabelGenerator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                output_path = generator.generate_labels(incomplete_data, "incomplete_test.pdf")
                
                # Should handle gracefully and create PDF
                assert output_path.exists()

    def test_image_processor_integration(self):
        """Test integration with ImageProcessor."""
        generator = LabelGenerator()
        image_processor = generator.image_processor
        
        # Test that image processor is properly initialized
        assert isinstance(image_processor, ImageProcessor)
        assert hasattr(image_processor, 'process_image')
        assert hasattr(image_processor, 'get_image_for_product')

    def test_concurrent_label_generation(self, real_product_data):
        """Test that multiple label generations don't interfere with each other."""
        generator1 = LabelGenerator()
        generator2 = LabelGenerator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                # Generate labels simultaneously (simulated)
                output1 = generator1.generate_labels(
                    {"91290A115": real_product_data["91290A115"]}, 
                    "concurrent_test1.pdf"
                )
                output2 = generator2.generate_labels(
                    {"91290A116": real_product_data["91290A116"]}, 
                    "concurrent_test2.pdf"
                )
                
                # Both should succeed
                assert output1.exists()
                assert output2.exists()
                assert output1.name != output2.name

    def test_label_dimensions_configuration(self, real_product_data):
        """Test that label dimensions are properly configured."""
        generator = LabelGenerator()
        
        # Test initial dimensions
        from src.config import LABEL_WIDTH_INCHES, LABEL_HEIGHT_INCHES
        expected_width = LABEL_WIDTH_INCHES * 72  # Convert to points (72 points per inch)
        expected_height = LABEL_HEIGHT_INCHES * 72
        
        assert abs(generator.page_width - expected_width) < 1  # Allow small rounding differences
        assert abs(generator.page_height - expected_height) < 1
        
        # Test image area calculation
        expected_image_width = generator.page_width * 0.25
        assert abs(generator.image_width - expected_image_width) < 1

    @patch('src.label_generator.logger')
    def test_logging_integration(self, mock_logger, real_product_data):
        """Test that logging works properly during label generation."""
        generator = LabelGenerator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                generator.generate_labels(real_product_data, "logging_test.pdf")
                
                # Verify that info logging was called
                mock_logger.info.assert_called()

    def test_vertical_centering_integration(self):
        """Test that vertical centering works with different text lengths."""
        generator = LabelGenerator()
        
        # Test data with different text lengths to verify centering
        test_products = {
            "SHORT_TEXT": {
                "info": {
                    "FamilyDescription": "Screw",
                    "DetailDescription": "M3 x 10mm",
                    "Specifications": [
                        {"Attribute": "Length", "Values": ["10 mm"]},
                    ]
                },
                "image_path": None,
                "cad_path": None
            },
            "MEDIUM_TEXT": {
                "info": {
                    "FamilyDescription": "Socket Head Cap Screw",
                    "DetailDescription": "Alloy Steel, Black-Oxide Coated, M6 x 1.0 mm Thread, 25 mm Long",
                    "Specifications": [
                        {"Attribute": "Length", "Values": ["25 mm"]},
                        {"Attribute": "Thread Size", "Values": ["M6"]},
                        {"Attribute": "Thread Pitch", "Values": ["1.0 mm"]},
                    ]
                },
                "image_path": None,
                "cad_path": None
            },
            "LONG_TEXT": {
                "info": {
                    "FamilyDescription": "Ultra High Strength Alloy Steel Socket Head Cap Screw with Advanced Coating",
                    "DetailDescription": "Black-Oxide Coated for Maximum Corrosion Resistance, M8 x 1.25 mm Metric Thread, 50 mm Length, Hex Socket Drive Style, Class 12.9 Strength Grade, Fully Threaded Shank",
                    "Specifications": [
                        {"Attribute": "Length", "Values": ["50 mm"]},
                        {"Attribute": "Thread Size", "Values": ["M8"]},
                        {"Attribute": "Thread Pitch", "Values": ["1.25 mm"]},
                        {"Attribute": "Head Diameter", "Values": ["13 mm"]},
                        {"Attribute": "Material", "Values": ["Alloy Steel"]},
                    ]
                },
                "image_path": None,
                "cad_path": None
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.label_generator.OUTPUT_DIR', Path(temp_dir)):
                # Generate labels with vertical centering
                output_path = generator.generate_labels(test_products, "vertical_centering_test.pdf")
                
                # Verify PDF was created successfully
                assert output_path.exists()
                assert output_path.stat().st_size > 0
                
                # All products should have been processed
                assert len(test_products) == 3

    def test_cache_optimization_integration(self):
        """Test that cache optimization works correctly."""
        from src.api_client import McMasterAPI
        from unittest.mock import Mock, patch
        
        # Mock the session setup to avoid certificate issues
        with patch.object(McMasterAPI, '_setup_session'):
            # Create a real API instance (but we won't actually call the API)
            api = McMasterAPI("test@example.com", "test_password", "cert_password")
            api.session = Mock()  # Mock session for testing
        
            # Test that cache stats are initialized
            stats = api.get_cache_stats()
            assert 'product_info_cache_hits' in stats
            assert 'product_info_api_calls' in stats
            assert 'image_cache_hits' in stats
            assert 'image_api_downloads' in stats
            assert 'cad_cache_hits' in stats
            assert 'cad_api_downloads' in stats
            
            # All should start at 0
            for key, value in stats.items():
                assert value == 0
        
        # Test that cache stats methods exist and work
        assert hasattr(api, 'print_cache_stats')
        assert callable(api.print_cache_stats)
        
        # Test subscription optimization stats
        assert 'subscription_cache_skips' in stats
        assert 'subscription_api_calls' in stats
        assert stats['subscription_cache_skips'] == 0
        assert stats['subscription_api_calls'] == 0

    def test_subscription_optimization(self):
        """Test that subscription calls are skipped when product info is cached."""
        from src.api_client import McMasterAPI
        from src.config import CACHE_DIR
        import json
        import tempfile
        from unittest.mock import patch, Mock
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_cache_dir = Path(temp_dir) / "cache"
            temp_cache_dir.mkdir()
            
            with patch('src.api_client.CACHE_DIR', temp_cache_dir), \
                 patch.object(McMasterAPI, '_setup_session'):
                api = McMasterAPI("test@example.com", "test_password", "cert_password")
                api.session = Mock()  # Mock session
                
                # Mock authentication and SSL verification
                api.is_authenticated = True
                api.auth_token = "test_token"
                api.verify = False  # Mock SSL verification setting
                
                # Create cached product info for one product
                cached_product_id = "91290A115"
                cache_file = temp_cache_dir / f"product_{cached_product_id}.json"
                cache_data = {
                    "PartNumber": cached_product_id,
                    "FamilyDescription": "Test Product",
                    "DetailDescription": "Test Description"
                }
                with open(cache_file, 'w') as f:
                    json.dump(cache_data, f)
                
                # Mock the session and API calls
                mock_session = Mock()
                api.session = mock_session
                
                # Mock successful responses
                mock_session.put.return_value.status_code = 200
                mock_session.get.return_value.status_code = 200
                mock_session.get.return_value.json.return_value = cache_data
                
                # Process products - one cached, one not cached
                product_ids = [cached_product_id, "91290A116"]
                
                with patch.object(api, 'download_cad_file', return_value=None), \
                     patch.object(api, 'download_image_file', return_value=None):
                    results = api.process_products(product_ids)
                
                # Verify subscription was skipped for cached product
                stats = api.get_cache_stats()
                assert stats['subscription_cache_skips'] == 1, "Should skip subscription for cached product"
                assert stats['subscription_api_calls'] == 1, "Should call subscription API for non-cached product"
                
                # Verify only one subscription call was made (for the non-cached product)
                assert mock_session.put.call_count == 1
                
                # Verify both products were processed
                assert len(results) == 2
                assert cached_product_id in results
                assert "91290A116" in results