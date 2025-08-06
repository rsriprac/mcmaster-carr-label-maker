"""
Fuzzy text sorting with intelligent dimension-based sub-sorting.

This module groups similar items by text description and sorts within groups
by numerical dimensions with unit awareness.
"""

import re
import logging
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

logger = logging.getLogger(__name__)


class FuzzyTextSorter:
    """Sort products by text similarity with dimension-aware sub-sorting."""
    
    # Common measurement patterns with unit normalization
    DIMENSION_PATTERNS = [
        # Metric thread sizes (M2, M3, M4, M8, M10, etc.)
        (r'M(\d+(?:\.\d+)?)', 'metric_thread', lambda x: float(x)),
        
        # Thread sizes with pitch (M8 x 1.25)
        (r'M(\d+)\s*x\s*(\d+(?:\.\d+)?)', 'metric_thread_pitch', lambda x, y: (float(x), float(y))),
        
        # Fractional inches (1/4", 3/8", 1/2", etc.)
        (r'(\d+)/(\d+)(?:\s*"|\s*in\b)?', 'fractional_inch', lambda n, d: float(n) / float(d)),
        
        # Decimal inches (0.25", 1.5 in, etc.)
        (r'(\d+(?:\.\d+)?)\s*(?:"|\bin\b)', 'decimal_inch', lambda x: float(x)),
        
        # Millimeters (10mm, 25 mm, etc.)
        (r'(\d+(?:\.\d+)?)\s*mm\b', 'millimeter', lambda x: float(x)),
        
        # Centimeters (2.5cm, 10 cm, etc.)
        (r'(\d+(?:\.\d+)?)\s*cm\b', 'centimeter', lambda x: float(x) * 10),  # Convert to mm
        
        # Length/Width/Height/Diameter with units
        (r'(?:L|Length)[:\s]+(\d+(?:\.\d+)?)\s*(mm|cm|in|")', 'length', None),
        (r'(?:W|Width)[:\s]+(\d+(?:\.\d+)?)\s*(mm|cm|in|")', 'width', None),
        (r'(?:H|Height)[:\s]+(\d+(?:\.\d+)?)\s*(mm|cm|in|")', 'height', None),
        (r'(?:D|Dia|Diameter)[:\s]+(\d+(?:\.\d+)?)\s*(mm|cm|in|")', 'diameter', None),
        
        # Thread count/pitch
        (r'(\d+)-(\d+)\s*(?:UNC|UNF|NC|NF)', 'unified_thread', lambda x, y: (float(x), float(y))),
        
        # Number sizes (#4, #6, #8, #10, etc.)
        (r'#(\d+)', 'number_size', lambda x: float(x)),
        
        # Wire gauge (AWG)
        (r'(\d+)\s*(?:AWG|GA|Gauge)', 'wire_gauge', lambda x: -float(x)),  # Smaller number = larger wire
    ]
    
    # Unit conversion factors to normalize to millimeters
    UNIT_TO_MM = {
        'mm': 1.0,
        'cm': 10.0,
        'in': 25.4,
        '"': 25.4,
        'm': 1000.0,
    }
    
    def __init__(self, similarity_threshold: float = 0.3):
        """
        Initialize the fuzzy text sorter.
        
        Args:
            similarity_threshold: Threshold for grouping similar text (0-1)
        """
        self.similarity_threshold = similarity_threshold
        
    def sort_products(self, products_data: Dict[str, Dict[str, Any]]) -> List[str]:
        """
        Sort products using fuzzy text grouping and dimension-based sub-sorting.
        
        Args:
            products_data: Dictionary of product data
            
        Returns:
            Ordered list of product IDs
        """
        if len(products_data) <= 1:
            return list(products_data.keys())
            
        # Step 1: Extract text descriptions and create similarity groups
        groups = self._create_similarity_groups(products_data)
        
        # Step 2: Sort within each group by dimensions
        sorted_groups = []
        for group in groups:
            if len(group) > 1:
                sorted_group = self._sort_group_by_dimensions(group, products_data)
            else:
                sorted_group = group
            sorted_groups.append(sorted_group)
        
        # Step 3: Sort groups by their representative text
        sorted_groups = self._sort_groups(sorted_groups, products_data)
        
        # Step 4: Flatten the result
        result = []
        for group in sorted_groups:
            result.extend(group)
            
        return result
    
    def _create_similarity_groups(self, products_data: Dict[str, Dict[str, Any]]) -> List[List[str]]:
        """Create groups of products with similar text descriptions."""
        product_ids = list(products_data.keys())
        
        # Extract text descriptions with enhanced categorization
        descriptions = []
        categories = []
        for product_id in product_ids:
            info = products_data[product_id].get('info', {})
            family = info.get('FamilyDescription', '')
            detail = info.get('DetailDescription', '')
            
            # Combine descriptions
            if family and detail:
                text = f"{family} {detail}"
            else:
                text = family or detail or product_id
                
            descriptions.append(text)
            
            # Extract category for better grouping
            category = self._extract_category(text.lower())
            categories.append(category)
        
        # Group by category first
        category_groups = defaultdict(list)
        for idx, (product_id, category) in enumerate(zip(product_ids, categories)):
            category_groups[category].append(idx)
        
        # Create similarity groups within each category
        all_groups = []
        for category, indices in category_groups.items():
            if len(indices) <= 1:
                all_groups.append([product_ids[idx] for idx in indices])
                continue
            
            # Get descriptions for this category
            cat_descriptions = [descriptions[idx] for idx in indices]
            cat_product_ids = [product_ids[idx] for idx in indices]
            
            try:
                if len(cat_descriptions) >= 2:
                    vectorizer = TfidfVectorizer(
                        lowercase=True,
                        stop_words='english',
                        ngram_range=(1, 2),
                        max_features=50
                    )
                    tfidf_matrix = vectorizer.fit_transform(cat_descriptions)
                    
                    # Compute similarity matrix
                    similarity_matrix = cosine_similarity(tfidf_matrix)
                    
                    # Create distance matrix ensuring no negative values
                    distance_matrix = np.clip(1 - similarity_matrix, 0, 2)
                    np.fill_diagonal(distance_matrix, 0)
                    
                    # Hierarchical clustering
                    if len(cat_product_ids) > 2:
                        condensed_dist = squareform(distance_matrix)
                        linkage_matrix = linkage(condensed_dist, method='average')
                        clusters = fcluster(linkage_matrix, 1 - self.similarity_threshold, criterion='distance')
                        
                        # Group by cluster
                        cluster_groups = defaultdict(list)
                        for idx, cluster_id in enumerate(clusters):
                            cluster_groups[cluster_id].append(cat_product_ids[idx])
                        
                        all_groups.extend(list(cluster_groups.values()))
                    else:
                        all_groups.append(cat_product_ids)
                else:
                    all_groups.append(cat_product_ids)
                    
            except Exception as e:
                logger.debug(f"Clustering failed for category {category}: {e}")
                all_groups.append(cat_product_ids)
        
        return all_groups
    
    def _extract_category(self, text: str) -> str:
        """Extract primary category from text."""
        # Priority order matters
        if 'socket' in text and 'cap' in text:
            return 'socket_cap_screw'
        elif 'socket' in text and 'head' in text:
            return 'socket_head_screw'
        elif 'button' in text and 'head' in text:
            return 'button_head_screw'
        elif 'flat' in text and 'head' in text:
            return 'flat_head_screw'
        elif 'pan' in text and 'head' in text:
            return 'pan_head_screw'
        elif 'hex' in text and ('bolt' in text or 'screw' in text):
            return 'hex_bolt'
        elif 'set' in text and 'screw' in text:
            return 'set_screw'
        elif 'thumb' in text and 'screw' in text:
            return 'thumb_screw'
        elif 'screw' in text or 'bolt' in text:
            return 'other_screw'
        elif 'hex' in text and 'nut' in text:
            return 'hex_nut'
        elif 'lock' in text and 'nut' in text:
            return 'lock_nut'
        elif 'wing' in text and 'nut' in text:
            return 'wing_nut'
        elif 'coupling' in text and 'nut' in text:
            return 'coupling_nut'
        elif 'nut' in text:
            return 'other_nut'
        elif 'washer' in text:
            return 'washer'
        elif 'pin' in text:
            return 'pin'
        elif 'o-ring' in text or 'seal' in text:
            return 'seal'
        elif 'fitting' in text:
            return 'fitting'
        elif 'spring' in text:
            return 'spring'
        elif 'bearing' in text:
            return 'bearing'
        elif 'bushing' in text:
            return 'bushing'
        else:
            return 'other'
    
    def _sort_group_by_dimensions(self, group: List[str], 
                                 products_data: Dict[str, Dict[str, Any]]) -> List[str]:
        """Sort products within a group by their dimensions."""
        if len(group) <= 1:
            return group
            
        # Extract dimensions for each product
        product_dimensions = []
        for product_id in group:
            dimensions = self._extract_dimensions(product_id, products_data[product_id])
            product_dimensions.append((product_id, dimensions))
        
        # Sort by dimensions
        product_dimensions.sort(key=lambda x: self._create_sort_key(x[1]))
        
        return [pid for pid, _ in product_dimensions]
    
    def _extract_dimensions(self, product_id: str, 
                          product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract dimensional information from product data."""
        dimensions = {}
        info = product_data.get('info', {})
        
        # First check structured specifications
        specifications = info.get('Specifications', [])
        if specifications:
            for spec in specifications:
                attr = spec.get('Attribute', '')
                values = spec.get('Values', [])
                if values and values[0]:
                    value = values[0]
                    # Map specification attributes to dimension types
                    if attr == 'Thread Size':
                        dimensions['thread_size'] = self._parse_thread_size(value)
                    elif attr == 'Length':
                        dimensions['length'] = self._parse_length(value)
                    elif attr == 'Overall Length':
                        dimensions['length'] = self._parse_length(value)
                    elif attr == 'Diameter':
                        dimensions['diameter'] = self._parse_length(value)
                    elif attr in ['Inside Diameter', 'ID']:
                        dimensions['inside_diameter'] = self._parse_length(value)
                    elif attr in ['Outside Diameter', 'OD']:
                        dimensions['outside_diameter'] = self._parse_length(value)
                    elif attr == 'Width':
                        dimensions['width'] = self._parse_length(value)
                    elif attr == 'Height':
                        dimensions['height'] = self._parse_length(value)
                    elif attr == 'Screw Size':
                        dimensions['screw_size'] = self._parse_screw_size(value)
        
        # If no thread size found in specs, try to extract from text
        if 'thread_size' not in dimensions:
            family = info.get('FamilyDescription', '')
            detail = info.get('DetailDescription', '')
            full_text = f"{family} {detail} {product_id}"
            
            # Extract dimensions using patterns
            for pattern, dim_type, converter in self.DIMENSION_PATTERNS:
                matches = re.finditer(pattern, full_text, re.IGNORECASE)
                for match in matches:
                    groups = match.groups()
                    
                    # Handle special cases for length/width/height/diameter
                    if dim_type in ['length', 'width', 'height', 'diameter']:
                        if dim_type not in dimensions:  # Don't override spec values
                            value = float(groups[0])
                            unit = groups[1].lower()
                            # Convert to mm for normalization
                            value_mm = value * self.UNIT_TO_MM.get(unit, 1.0)
                            dimensions[dim_type] = value_mm
                    elif converter and dim_type not in dimensions:
                        try:
                            if len(groups) == 1:
                                dimensions[dim_type] = converter(groups[0])
                            elif len(groups) == 2:
                                dimensions[dim_type] = converter(groups[0], groups[1])
                        except (ValueError, ZeroDivisionError):
                            pass
        
        return dimensions
    
    def _parse_thread_size(self, value: str) -> float:
        """Parse thread size to sortable numeric value."""
        if not value:
            return float('inf')
        
        # Metric threads (M2, M3, M4, etc.)
        if value.startswith('M'):
            match = re.match(r'M(\d+(?:\.\d+)?)', value)
            if match:
                return float(match.group(1))
        
        # Fractional inches (1/4"-20, etc.)
        frac_match = re.match(r'(\d+)/(\d+)["\s-]', value)
        if frac_match:
            return float(frac_match.group(1)) / float(frac_match.group(2))
        
        # Decimal inches
        dec_match = re.match(r'(\d+(?:\.\d+)?)["\s-]', value)
        if dec_match:
            return float(dec_match.group(1))
        
        # Number sizes (#4, #6, etc.)
        num_match = re.match(r'#(\d+)', value)
        if num_match:
            return float(num_match.group(1)) / 100  # Normalize to be smaller than fractions
        
        # UNC/UNF threads (e.g., "10-24")
        unc_match = re.match(r'(\d+)-(\d+)', value)
        if unc_match:
            return float(unc_match.group(1)) / 100  # Treat as number size
        
        return float('inf')
    
    def _parse_screw_size(self, value: str) -> float:
        """Parse screw size to sortable numeric value."""
        # Similar to thread size but for wood screws, etc.
        if value.startswith('#'):
            num_match = re.match(r'#(\d+)', value)
            if num_match:
                return float(num_match.group(1)) / 100
        
        # Fractional or decimal
        return self._parse_thread_size(value)
    
    def _parse_length(self, value: str) -> float:
        """Parse length/dimension to mm."""
        if not value:
            return float('inf')
        
        # Extract number and unit
        match = re.match(r'([\d\.]+)\s*([a-zA-Z"]*)\s*', value)
        if match:
            num = float(match.group(1))
            unit = match.group(2).lower().strip()
            
            # Convert to mm
            if 'mm' in unit:
                return num
            elif 'cm' in unit:
                return num * 10
            elif 'in' in unit or '"' in unit or not unit:
                return num * 25.4  # Default to inches if no unit
            elif 'm' in unit:
                return num * 1000
        
        # Try fractional
        frac_match = re.match(r'(\d+)/(\d+)', value)
        if frac_match:
            return (float(frac_match.group(1)) / float(frac_match.group(2))) * 25.4
        
        return float('inf')
    
    def _create_sort_key(self, dimensions: Dict[str, Any]) -> Tuple:
        """Create a sort key from dimensions dictionary."""
        # Priority order for sorting
        priority = [
            'metric_thread',
            'metric_thread_pitch', 
            'unified_thread',
            'number_size',
            'fractional_inch',
            'decimal_inch',
            'diameter',
            'length',
            'width',
            'height',
            'millimeter',
            'centimeter',
            'wire_gauge'
        ]
        
        sort_key = []
        
        # Add dimensions in priority order
        for dim_type in priority:
            if dim_type in dimensions:
                value = dimensions[dim_type]
                if isinstance(value, tuple):
                    # For compound values like thread pitch
                    sort_key.extend(value)
                else:
                    sort_key.append(value)
            else:
                # Add placeholder for missing dimension
                sort_key.append(float('inf'))
        
        return tuple(sort_key)
    
    def _sort_groups(self, groups: List[List[str]], 
                    products_data: Dict[str, Dict[str, Any]]) -> List[List[str]]:
        """Sort groups by their representative text."""
        # Get representative text for each group (first item's description)
        group_texts = []
        for group in groups:
            product_id = group[0]
            info = products_data[product_id].get('info', {})
            family = info.get('FamilyDescription', '')
            detail = info.get('DetailDescription', '')
            
            if family and detail:
                text = f"{family} {detail}"
            else:
                text = family or detail or product_id
                
            group_texts.append((group, text.lower()))
        
        # Sort groups by text
        group_texts.sort(key=lambda x: x[1])
        
        return [group for group, _ in group_texts]
    
    def get_group_summary(self, products_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get a summary of similarity groups for debugging/visualization."""
        groups = self._create_similarity_groups(products_data)
        
        summary = []
        for i, group in enumerate(groups, 1):
            # Get common description for group
            if group:
                product_id = group[0]
                info = products_data[product_id].get('info', {})
                family = info.get('FamilyDescription', 'Unknown')
                
                group_info = {
                    'group_id': i,
                    'size': len(group),
                    'family': family,
                    'products': group,
                    'dimensions': [self._extract_dimensions(pid, products_data[pid]) 
                                 for pid in group]
                }
                summary.append(group_info)
                
        return summary