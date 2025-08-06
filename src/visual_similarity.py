"""
Visual similarity analysis for sorting labels by appearance.
"""

import logging
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import numpy as np
from PIL import Image
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from scipy.spatial.distance import pdist, squareform
from scipy.cluster.hierarchy import dendrogram, linkage, fcluster
import cv2

logger = logging.getLogger(__name__)


class VisualSimilarityAnalyzer:
    """Analyze visual similarity of product images for smart sorting."""
    
    def __init__(self, feature_size: int = 64):
        """
        Initialize the analyzer.
        
        Args:
            feature_size: Size to resize images for feature extraction
        """
        self.feature_size = feature_size
        self.features_cache = {}
        
    def extract_features(self, image_path: Optional[str]) -> np.ndarray:
        """
        Extract visual features from an image.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Feature vector for the image
        """
        if not image_path or not Path(image_path).exists():
            # Return zero features for missing images
            return np.zeros(self.feature_size * self.feature_size)
            
        if image_path in self.features_cache:
            return self.features_cache[image_path]
            
        try:
            # Load and preprocess image
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                img = np.array(Image.open(image_path).convert('L'))
            
            # Resize to standard size
            img_resized = cv2.resize(img, (self.feature_size, self.feature_size))
            
            # Extract multiple feature types
            features = []
            
            # 1. Raw pixel features (downsampled)
            pixel_features = img_resized.flatten()
            features.extend(pixel_features)
            
            # 2. Edge features using Canny
            edges = cv2.Canny(img_resized, 50, 150)
            edge_features = edges.flatten()
            features.extend(edge_features)
            
            # 3. Histogram features
            hist = cv2.calcHist([img_resized], [0], None, [32], [0, 256])
            hist_features = hist.flatten()
            features.extend(hist_features)
            
            # 4. Hu moments (shape features)
            moments = cv2.moments(img_resized)
            hu_moments = cv2.HuMoments(moments).flatten()
            features.extend(hu_moments)
            
            # 5. Simple texture features (variance in local regions)
            h, w = img_resized.shape
            block_size = 8
            texture_features = []
            for i in range(0, h, block_size):
                for j in range(0, w, block_size):
                    block = img_resized[i:i+block_size, j:j+block_size]
                    texture_features.append(np.var(block))
            features.extend(texture_features)
            
            feature_vector = np.array(features)
            
            # Cache the features
            self.features_cache[image_path] = feature_vector
            
            return feature_vector
            
        except Exception as e:
            logger.warning(f"Failed to extract features from {image_path}: {e}")
            return np.zeros(self.feature_size * self.feature_size)
    
    def compute_similarity_matrix(self, products_data: Dict[str, Dict[str, Any]]) -> Tuple[np.ndarray, List[str]]:
        """
        Compute similarity matrix for all products.
        
        Args:
            products_data: Dictionary of product data
            
        Returns:
            Similarity matrix and ordered list of product IDs
        """
        product_ids = list(products_data.keys())
        n_products = len(product_ids)
        
        # Extract features for all products
        all_features = []
        valid_indices = []
        
        for i, product_id in enumerate(product_ids):
            image_path = products_data[product_id].get('image_path')
            features = self.extract_features(image_path)
            
            # Only include products with valid features
            if np.any(features != 0):
                all_features.append(features)
                valid_indices.append(i)
        
        if not all_features:
            # No valid features, return identity matrix
            return np.eye(n_products), product_ids
        
        # Convert to numpy array
        feature_matrix = np.array(all_features)
        
        # Normalize features
        scaler = StandardScaler()
        normalized_features = scaler.fit_transform(feature_matrix)
        
        # Apply PCA for dimensionality reduction
        n_components = min(50, normalized_features.shape[0] - 1, normalized_features.shape[1])
        if n_components > 0:
            pca = PCA(n_components=n_components)
            reduced_features = pca.fit_transform(normalized_features)
        else:
            reduced_features = normalized_features
        
        # Compute pairwise distances
        distances = pdist(reduced_features, metric='euclidean')
        distance_matrix = squareform(distances)
        
        # Convert distances to similarities (0 to 1, where 1 is most similar)
        max_dist = np.max(distance_matrix) if np.max(distance_matrix) > 0 else 1
        similarity_matrix = 1 - (distance_matrix / max_dist)
        
        # Create full similarity matrix including products without features
        full_similarity_matrix = np.eye(n_products) * 0.5  # Default similarity
        
        for i, idx_i in enumerate(valid_indices):
            for j, idx_j in enumerate(valid_indices):
                full_similarity_matrix[idx_i, idx_j] = similarity_matrix[i, j]
        
        return full_similarity_matrix, product_ids
    
    def sort_by_similarity(self, products_data: Dict[str, Dict[str, Any]], 
                          method: str = 'hierarchical') -> List[str]:
        """
        Sort products by visual similarity.
        
        Args:
            products_data: Dictionary of product data
            method: Sorting method ('hierarchical', 'spectral', or 'greedy')
            
        Returns:
            Ordered list of product IDs
        """
        similarity_matrix, product_ids = self.compute_similarity_matrix(products_data)
        
        if method == 'hierarchical':
            return self._hierarchical_sort(similarity_matrix, product_ids)
        elif method == 'spectral':
            return self._spectral_sort(similarity_matrix, product_ids)
        elif method == 'greedy':
            return self._greedy_sort(similarity_matrix, product_ids)
        else:
            logger.warning(f"Unknown sorting method: {method}. Using hierarchical.")
            return self._hierarchical_sort(similarity_matrix, product_ids)
    
    def _hierarchical_sort(self, similarity_matrix: np.ndarray, 
                          product_ids: List[str]) -> List[str]:
        """Sort using hierarchical clustering."""
        # Convert similarity to distance
        distance_matrix = 1 - similarity_matrix
        
        # Ensure diagonal is zero
        np.fill_diagonal(distance_matrix, 0)
        
        # Convert to condensed distance matrix
        condensed_dist = squareform(distance_matrix)
        
        # Perform hierarchical clustering
        linkage_matrix = linkage(condensed_dist, method='average')
        
        # Get dendrogram order
        dendrogram_data = dendrogram(linkage_matrix, no_plot=True)
        order = dendrogram_data['leaves']
        
        return [product_ids[i] for i in order]
    
    def _spectral_sort(self, similarity_matrix: np.ndarray, 
                      product_ids: List[str]) -> List[str]:
        """Sort using spectral ordering (1D embedding)."""
        # Add small value to diagonal for numerical stability
        similarity_matrix = similarity_matrix + np.eye(len(similarity_matrix)) * 0.01
        
        # Compute degree matrix
        degree_matrix = np.diag(np.sum(similarity_matrix, axis=1))
        
        # Compute normalized Laplacian
        laplacian = degree_matrix - similarity_matrix
        
        # Compute eigenvalues and eigenvectors
        eigenvalues, eigenvectors = np.linalg.eigh(laplacian)
        
        # Use second smallest eigenvector (Fiedler vector) for ordering
        fiedler_vector = eigenvectors[:, 1]
        
        # Sort by Fiedler vector values
        order = np.argsort(fiedler_vector)
        
        return [product_ids[i] for i in order]
    
    def _greedy_sort(self, similarity_matrix: np.ndarray, 
                    product_ids: List[str]) -> List[str]:
        """Sort using greedy nearest neighbor approach."""
        n = len(product_ids)
        if n <= 1:
            return product_ids
        
        # Start with the product that has highest average similarity
        avg_similarities = np.mean(similarity_matrix, axis=1)
        current = np.argmax(avg_similarities)
        
        visited = {current}
        path = [current]
        
        # Greedily add nearest unvisited neighbor
        while len(visited) < n:
            # Find most similar unvisited product
            similarities = similarity_matrix[current].copy()
            for v in visited:
                similarities[v] = -1  # Mark as visited
            
            next_idx = np.argmax(similarities)
            visited.add(next_idx)
            path.append(next_idx)
            current = next_idx
        
        return [product_ids[i] for i in path]
    
    def group_by_similarity(self, products_data: Dict[str, Dict[str, Any]], 
                           n_groups: Optional[int] = None, 
                           threshold: Optional[float] = None) -> Dict[int, List[str]]:
        """
        Group products by visual similarity.
        
        Args:
            products_data: Dictionary of product data
            n_groups: Number of groups (if None, determined automatically)
            threshold: Similarity threshold for grouping
            
        Returns:
            Dictionary mapping group ID to list of product IDs
        """
        similarity_matrix, product_ids = self.compute_similarity_matrix(products_data)
        
        # Convert similarity to distance
        distance_matrix = 1 - similarity_matrix
        np.fill_diagonal(distance_matrix, 0)
        condensed_dist = squareform(distance_matrix)
        
        # Perform hierarchical clustering
        linkage_matrix = linkage(condensed_dist, method='average')
        
        # Determine clusters
        if n_groups is not None:
            clusters = fcluster(linkage_matrix, n_groups, criterion='maxclust')
        elif threshold is not None:
            clusters = fcluster(linkage_matrix, threshold, criterion='distance')
        else:
            # Automatically determine number of clusters using elbow method
            # (simplified version)
            n_groups = min(5, len(product_ids) // 3)  # Reasonable default
            clusters = fcluster(linkage_matrix, n_groups, criterion='maxclust')
        
        # Group products by cluster
        groups = {}
        for i, cluster_id in enumerate(clusters):
            if cluster_id not in groups:
                groups[cluster_id] = []
            groups[cluster_id].append(product_ids[i])
        
        return groups