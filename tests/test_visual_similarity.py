"""
Tests for visual similarity analysis and sorting.
"""

import pytest
import tempfile
import numpy as np
from pathlib import Path
from PIL import Image
import cv2

from src.visual_similarity import VisualSimilarityAnalyzer


class TestVisualSimilarity:
    """Test visual similarity analysis."""
    
    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return VisualSimilarityAnalyzer(feature_size=32)
    
    @pytest.fixture
    def sample_images(self):
        """Create sample images for testing."""
        temp_dir = tempfile.mkdtemp()
        images = {}
        
        # Create similar screws (vertical lines)
        for i in range(3):
            img = np.ones((100, 100), dtype=np.uint8) * 255
            cv2.line(img, (50, 20), (50, 80), 0, 2)
            cv2.line(img, (45, 20), (45, 30), 0, 1)  # Thread marks
            cv2.line(img, (55, 20), (55, 30), 0, 1)
            path = f"{temp_dir}/screw_{i}.png"
            cv2.imwrite(path, img)
            images[f"screw_{i}"] = path
        
        # Create similar nuts (hexagons)
        for i in range(3):
            img = np.ones((100, 100), dtype=np.uint8) * 255
            # Draw hexagon
            pts = np.array([[50, 20], [70, 35], [70, 65], 
                           [50, 80], [30, 65], [30, 35]], np.int32)
            cv2.fillPoly(img, [pts], 128)
            cv2.polylines(img, [pts], True, 0, 2)
            path = f"{temp_dir}/nut_{i}.png"
            cv2.imwrite(path, img)
            images[f"nut_{i}"] = path
        
        # Create different item (circle/washer)
        img = np.ones((100, 100), dtype=np.uint8) * 255
        cv2.circle(img, (50, 50), 30, 0, 2)
        cv2.circle(img, (50, 50), 15, 0, 2)
        path = f"{temp_dir}/washer.png"
        cv2.imwrite(path, img)
        images["washer"] = path
        
        return images, temp_dir
    
    def test_feature_extraction(self, analyzer, sample_images):
        """Test feature extraction from images."""
        images, _ = sample_images
        
        # Extract features from a screw image
        features = analyzer.extract_features(images["screw_0"])
        
        # Check feature vector properties
        assert isinstance(features, np.ndarray)
        assert features.shape[0] > 0
        assert not np.all(features == 0)
        
        # Test caching
        features2 = analyzer.extract_features(images["screw_0"])
        np.testing.assert_array_equal(features, features2)
    
    def test_missing_image_handling(self, analyzer):
        """Test handling of missing images."""
        features = analyzer.extract_features("/nonexistent/image.png")
        assert isinstance(features, np.ndarray)
        assert np.all(features == 0)
    
    def test_similarity_matrix(self, analyzer, sample_images):
        """Test similarity matrix computation."""
        images, _ = sample_images
        
        products_data = {
            "screw_1": {"image_path": images["screw_0"]},
            "screw_2": {"image_path": images["screw_1"]},
            "nut_1": {"image_path": images["nut_0"]},
            "washer": {"image_path": images["washer"]},
        }
        
        similarity_matrix, product_ids = analyzer.compute_similarity_matrix(products_data)
        
        # Check matrix properties
        n = len(product_ids)
        assert similarity_matrix.shape == (n, n)
        assert np.all(np.diag(similarity_matrix) >= 0.99)  # Self-similarity ~1
        assert np.all(similarity_matrix >= 0)
        assert np.all(similarity_matrix <= 1)
        
        # Check symmetry
        assert np.allclose(similarity_matrix, similarity_matrix.T)
        
        # Similar items should have higher similarity
        screw_indices = [product_ids.index("screw_1"), product_ids.index("screw_2")]
        screw_similarity = similarity_matrix[screw_indices[0], screw_indices[1]]
        
        washer_idx = product_ids.index("washer")
        screw_washer_similarity = similarity_matrix[screw_indices[0], washer_idx]
        
        assert screw_similarity > screw_washer_similarity
    
    def test_hierarchical_sorting(self, analyzer, sample_images):
        """Test hierarchical sorting method."""
        images, _ = sample_images
        
        products_data = {
            "screw_1": {"image_path": images["screw_0"]},
            "nut_1": {"image_path": images["nut_0"]},
            "screw_2": {"image_path": images["screw_1"]},
            "nut_2": {"image_path": images["nut_1"]},
            "washer": {"image_path": images["washer"]},
        }
        
        sorted_ids = analyzer.sort_by_similarity(products_data, method='hierarchical')
        
        # Check all products are included
        assert len(sorted_ids) == len(products_data)
        assert set(sorted_ids) == set(products_data.keys())
        
        # Similar items should be adjacent
        # Find positions of similar items
        screw_positions = [sorted_ids.index("screw_1"), sorted_ids.index("screw_2")]
        nut_positions = [sorted_ids.index("nut_1"), sorted_ids.index("nut_2")]
        
        # Distance between similar items should be small
        assert abs(screw_positions[0] - screw_positions[1]) <= 2
        assert abs(nut_positions[0] - nut_positions[1]) <= 2
    
    def test_spectral_sorting(self, analyzer, sample_images):
        """Test spectral sorting method."""
        images, _ = sample_images
        
        products_data = {
            "item_1": {"image_path": images["screw_0"]},
            "item_2": {"image_path": images["nut_0"]},
            "item_3": {"image_path": images["washer"]},
        }
        
        sorted_ids = analyzer.sort_by_similarity(products_data, method='spectral')
        
        assert len(sorted_ids) == len(products_data)
        assert set(sorted_ids) == set(products_data.keys())
    
    def test_greedy_sorting(self, analyzer, sample_images):
        """Test greedy sorting method."""
        images, _ = sample_images
        
        products_data = {
            "item_1": {"image_path": images["screw_0"]},
            "item_2": {"image_path": images["nut_0"]},
            "item_3": {"image_path": images["washer"]},
        }
        
        sorted_ids = analyzer.sort_by_similarity(products_data, method='greedy')
        
        assert len(sorted_ids) == len(products_data)
        assert set(sorted_ids) == set(products_data.keys())
    
    def test_grouping_by_similarity(self, analyzer, sample_images):
        """Test grouping products by similarity."""
        images, _ = sample_images
        
        products_data = {
            "screw_1": {"image_path": images["screw_0"]},
            "screw_2": {"image_path": images["screw_1"]},
            "screw_3": {"image_path": images["screw_2"]},
            "nut_1": {"image_path": images["nut_0"]},
            "nut_2": {"image_path": images["nut_1"]},
            "washer": {"image_path": images["washer"]},
        }
        
        # Group into 3 clusters
        groups = analyzer.group_by_similarity(products_data, n_groups=3)
        
        assert len(groups) == 3
        
        # All products should be assigned
        all_grouped = []
        for group_items in groups.values():
            all_grouped.extend(group_items)
        assert set(all_grouped) == set(products_data.keys())
        
        # Similar items should be in same group
        screw_groups = set()
        nut_groups = set()
        
        for group_id, items in groups.items():
            if "screw_1" in items:
                screw_groups.add(group_id)
            if "screw_2" in items:
                screw_groups.add(group_id)
            if "nut_1" in items:
                nut_groups.add(group_id)
            if "nut_2" in items:
                nut_groups.add(group_id)
        
        # Similar items should be in same group
        assert len(screw_groups) == 1, "All screws should be in same group"
        assert len(nut_groups) == 1, "All nuts should be in same group"
    
    def test_empty_products(self, analyzer):
        """Test handling of empty product list."""
        sorted_ids = analyzer.sort_by_similarity({})
        assert sorted_ids == []
    
    def test_single_product(self, analyzer, sample_images):
        """Test handling of single product."""
        images, _ = sample_images
        
        products_data = {
            "single": {"image_path": images["screw_0"]}
        }
        
        sorted_ids = analyzer.sort_by_similarity(products_data)
        assert sorted_ids == ["single"]
    
    def test_products_without_images(self, analyzer):
        """Test handling of products without images."""
        products_data = {
            "no_image_1": {"info": "Product 1"},
            "no_image_2": {"info": "Product 2"},
            "no_image_3": {"info": "Product 3"},
        }
        
        sorted_ids = analyzer.sort_by_similarity(products_data)
        
        # Should still return all products
        assert len(sorted_ids) == len(products_data)
        assert set(sorted_ids) == set(products_data.keys())
    
    def test_mixed_with_without_images(self, analyzer, sample_images):
        """Test mix of products with and without images."""
        images, _ = sample_images
        
        products_data = {
            "with_image_1": {"image_path": images["screw_0"]},
            "no_image": {"info": "No image"},
            "with_image_2": {"image_path": images["screw_1"]},
        }
        
        sorted_ids = analyzer.sort_by_similarity(products_data)
        
        assert len(sorted_ids) == len(products_data)
        assert set(sorted_ids) == set(products_data.keys())