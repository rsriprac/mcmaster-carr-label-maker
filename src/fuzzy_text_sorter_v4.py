"""
Enhanced fuzzy text sorting v4 - Optimized for ~90% similarity with ordered_products.v2.txt

This implementation uses the same comprehensive logic that generated ordered_products.v2.txt
but packaged as a reusable sorter for the label generation system.
"""

import re
import logging
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class FuzzyTextSorterV4:
    """
    Production-ready sorter based on ordered_products.v2.txt generation logic.
    
    Key principles:
    1. Hierarchical categorization (major category -> subcategory -> item)
    2. Material-aware sorting (corrosion resistance priority)
    3. Proper dimension normalization (thread sizes, lengths, diameters)
    4. Consistent ordering within categories
    """
    
    def __init__(self):
        """Initialize the sorter with comprehensive rules."""
        self.setup_categories()
        self.setup_materials()
        self.enhanced_products = {}
    
    def setup_categories(self):
        """Define category hierarchy matching v2 logic."""
        # Major categories with explicit ordering
        self.major_categories = {
            'socket_screws': 1,
            'button_screws': 2,
            'flat_screws': 3,
            'pan_screws': 4,
            'hex_screws': 5,
            'set_screws': 6,
            'thumb_screws': 7,
            'specialty_screws': 8,
            'bolts': 9,
            'studs': 10,
            'hex_nuts': 11,
            'lock_nuts': 12,
            'specialty_nuts': 13,
            'flat_washers': 14,
            'lock_washers': 15,
            'specialty_washers': 16,
            'pins': 20,
            'keys': 21,
            'anchors': 25,
            'inserts': 26,
            'standoffs': 30,
            'spacers': 31,
            'bushings': 32,
            'bearings': 33,
            'shafts': 34,
            'collars': 35,
            'springs': 40,
            'retaining_rings': 41,
            'o_rings': 50,
            'seals': 51,
            'gaskets': 52,
            'fittings': 60,
            'adapters': 61,
            'valves': 62,
            'hoses': 63,
            'clamps': 64,
            'pipes': 65,
            'chains': 70,
            'sprockets': 71,
            'belts': 72,
            'pulleys': 73,
            'gears': 74,
            'cable_management': 80,
            'wire_products': 81,
            'knobs': 90,
            'handles': 91,
            'rods': 100,
            'bars': 101,
            'sheets': 102,
            'plates': 103,
            'tools': 110,
            'filters': 111,
            'mufflers': 112,
            'misc_hardware': 120
        }
    
    def setup_materials(self):
        """Define material priority (better materials first)."""
        self.material_priority = {
            '316': 1,
            '316l': 1,
            '316 stainless': 1,
            'super-corrosion-resistant': 1,
            '18-8': 2,
            '18-8 stainless': 2,
            '303': 3,
            '304': 3,
            '17-7': 4,
            '17-4': 4,
            '410': 5,
            '440c': 5,
            'stainless': 6,
            'brass': 10,
            'bronze': 11,
            'aluminum': 15,
            'zinc': 20,
            'zinc-plated': 20,
            'steel': 25,
            'alloy steel': 26,
            'grade 8': 27,
            'nylon': 30,
            'plastic': 31,
            'rubber': 35,
            'ptfe': 36,
            'viton': 37,
            'buna': 38,
            'silicone': 39,
            'glass-filled': 40
        }
    
    def sort_products(self, products_data: Dict[str, Dict[str, Any]]) -> List[str]:
        """
        Main sorting method that replicates v2 logic.
        
        Args:
            products_data: Dictionary with product IDs as keys
            
        Returns:
            Sorted list of product IDs
        """
        if not products_data:
            return []
        
        # Enhance all products with normalized data
        self.enhanced_products = {}
        for product_id, data in products_data.items():
            self.enhanced_products[product_id] = self._enhance_product(product_id, data)
        
        # Sort using comprehensive key
        sorted_products = sorted(
            self.enhanced_products.values(),
            key=self._create_sort_key
        )
        
        return [p['product_id'] for p in sorted_products]
    
    def _enhance_product(self, product_id: str, data: Dict) -> Dict:
        """
        Enhance product data with normalized fields for sorting.
        
        Args:
            product_id: Product identifier
            data: Raw product data
            
        Returns:
            Enhanced product dictionary
        """
        info = data.get('info', {})
        
        # Extract basic fields
        enhanced = {
            'product_id': product_id,
            'part_number': info.get('PartNumber', product_id),
            'product_category': info.get('ProductCategory', ''),
            'family': info.get('FamilyDescription', ''),
            'detail': info.get('DetailDescription', ''),
            'status': info.get('ProductStatus', '')
        }
        
        # Parse specifications
        specs = {}
        for spec in info.get('Specifications', []):
            attr = spec.get('Attribute', '')
            values = spec.get('Values', [])
            if values:
                specs[attr] = values[0]
        enhanced['specs'] = specs
        
        # Create searchable text
        enhanced['search_text'] = f"{enhanced['family']} {enhanced['detail']} {enhanced['product_category']}".lower()
        
        # Determine major category
        enhanced['major_category'] = self._determine_major_category(enhanced)
        enhanced['major_category_order'] = self.major_categories.get(
            enhanced['major_category'], 999
        )
        
        # Extract material
        enhanced['material'] = self._extract_material(enhanced)
        enhanced['material_order'] = self._get_material_order(enhanced['material'])
        
        # Extract and normalize dimensions
        enhanced['dimensions'] = self._extract_dimensions(enhanced)
        
        # Extract profile for screws
        enhanced['profile'] = self._extract_profile(enhanced)
        
        return enhanced
    
    def _determine_major_category(self, product: Dict) -> str:
        """
        Determine major category using pattern matching.
        
        Args:
            product: Enhanced product dictionary
            
        Returns:
            Major category identifier
        """
        search_text = product['search_text']
        family = product['family'].lower()
        specs = product['specs']
        
        # Socket screws (must check before generic screws)
        if 'socket' in family and 'head' in family and 'screw' in family:
            if 'set' not in family:
                return 'socket_screws'
        
        # Button head screws
        if 'button' in family and 'head' in family:
            return 'button_screws'
        
        # Flat head screws
        if ('flat' in family or 'countersink' in family or 'torx flat' in family) and 'screw' in family:
            return 'flat_screws'
        
        # Pan head screws
        if 'pan' in family and 'head' in family:
            return 'pan_screws'
        
        # Hex head screws
        if 'hex head' in family and ('screw' in family or 'bolt' in family):
            return 'hex_screws'
        
        # Set screws
        if 'set screw' in family or 'set-screw' in family:
            return 'set_screws'
        
        # Thumb screws
        if 'thumb' in family and 'screw' in family:
            return 'thumb_screws'
        
        # Drilling/wood screws
        if 'drilling' in family or 'wood screw' in family or 'self-drilling' in family:
            return 'specialty_screws'
        
        # Bolts
        if 'bolt' in family:
            if 'u-bolt' in family or 'u bolt' in family:
                return 'bolts'
            elif 'carriage' in family or 't-bolt' in family or 't bolt' in family:
                return 'bolts'
            else:
                return 'bolts'
        
        # Threaded rods/studs
        if 'threaded rod' in family or 'threaded stud' in family or ('stud' in family and 'wood screw' in family):
            return 'studs'
        
        # Nuts
        if 'nut' in family:
            if 'hex nut' in family and 'lock' not in family:
                return 'hex_nuts'
            elif 'lock' in family or 'nylon' in family or 'locknut' in family:
                return 'lock_nuts'
            elif 'wing' in family or 'coupling' in family or 'flange' in family or 'rivet' in family:
                return 'specialty_nuts'
            else:
                return 'hex_nuts'
        
        # Washers
        if 'washer' in family:
            if 'lock' in family or 'split' in family or 'spring' in family:
                return 'lock_washers'
            elif 'flat' in family or 'plain' in family or specs.get('Washer Type') == 'Flat':
                return 'flat_washers'
            else:
                return 'specialty_washers'
        
        # Pins
        if 'pin' in family:
            return 'pins'
        
        # Keys
        if 'key' in family and 'machine' in family:
            return 'keys'
        
        # Anchors
        if 'anchor' in family:
            return 'anchors'
        
        # Inserts
        if 'insert' in family or 'helicoil' in family or 'helical insert' in family:
            return 'inserts'
        
        # Standoffs/spacers
        if 'standoff' in family:
            return 'standoffs'
        if 'spacer' in family:
            return 'spacers'
        
        # Bushings
        if 'bushing' in family:
            return 'bushings'
        
        # Bearings
        if 'bearing' in family:
            return 'bearings'
        
        # Shafts
        if 'shaft' in family and 'collar' not in family:
            return 'shafts'
        
        # Shaft collars
        if 'collar' in family:
            return 'collars'
        
        # Springs
        if 'spring' in family and 'washer' not in family and 'lock' not in family:
            return 'springs'
        
        # Retaining rings
        if 'retaining' in family or 'snap ring' in family:
            return 'retaining_rings'
        
        # O-rings
        if 'o-ring' in family or 'o ring' in family:
            return 'o_rings'
        
        # Seals
        if 'seal' in family and 'o-ring' not in family:
            return 'seals'
        
        # Gaskets
        if 'gasket' in family:
            return 'gaskets'
        
        # Fittings
        if ('fitting' in family or 'connector' in family or 'elbow' in family or 
            'tee' in family or 'nipple' in family or 'muffler' in family or
            'adapter' in family or 'chuck' in family):
            return 'fittings'
        
        # Valves
        if 'valve' in family:
            return 'valves'
        
        # Hoses
        if 'hose' in family or 'coupling' in family:
            return 'hoses'
        
        # Clamps
        if 'clamp' in family:
            return 'clamps'
        
        # Chains
        if 'chain' in family:
            return 'chains'
        
        # Sprockets
        if 'sprocket' in family:
            return 'sprockets'
        
        # Wire products
        if 'wire' in family or 'cable' in family:
            if 'cloth' in family or 'mesh' in family or 'disc' in family:
                return 'wire_products'
            else:
                return 'cable_management'
        
        # Knobs
        if 'knob' in family:
            return 'knobs'
        
        # Rods (non-threaded)
        if 'rod' in family and 'threaded' not in family:
            return 'rods'
        
        # Bars
        if 'bar' in family:
            return 'bars'
        
        # Tools
        if 'tap' in family or 'die' in family:
            return 'tools'
        
        # Filters
        if 'filter' in family or 'strainer' in family:
            return 'filters'
        
        # Default
        return 'misc_hardware'
    
    def _extract_material(self, product: Dict) -> str:
        """
        Extract and normalize material information.
        
        Args:
            product: Enhanced product dictionary
            
        Returns:
            Normalized material string
        """
        # Check specs first
        material_spec = product['specs'].get('Material', '')
        
        # Check descriptions
        search_text = product['search_text']
        family = product['family'].lower()
        
        # Look for specific grades first (most specific to least)
        if '316' in search_text or '316' in material_spec:
            return '316 stainless'
        elif 'super-corrosion-resistant' in search_text:
            return 'super-corrosion-resistant'
        elif '18-8' in search_text or '18-8' in material_spec:
            return '18-8 stainless'
        elif '303' in search_text or '303' in material_spec:
            return '303'
        elif '304' in search_text or '304' in material_spec:
            return '304'
        elif '17-7' in search_text:
            return '17-7'
        elif '17-4' in search_text:
            return '17-4'
        elif '410' in search_text:
            return '410'
        elif '440c' in search_text:
            return '440c'
        elif 'stainless' in search_text:
            return 'stainless'
        elif 'brass' in search_text:
            return 'brass'
        elif 'bronze' in search_text:
            return 'bronze'
        elif 'aluminum' in search_text:
            return 'aluminum'
        elif 'zinc' in search_text:
            if 'yellow' in search_text:
                return 'zinc-plated'
            return 'zinc-plated'
        elif 'grade 8' in search_text:
            return 'grade 8'
        elif 'alloy steel' in search_text:
            return 'alloy steel'
        elif 'nylon' in search_text:
            if 'glass' in search_text:
                return 'glass-filled'
            return 'nylon'
        elif 'plastic' in search_text:
            return 'plastic'
        elif 'rubber' in search_text:
            return 'rubber'
        elif 'ptfe' in search_text:
            return 'ptfe'
        elif 'viton' in search_text:
            return 'viton'
        elif 'buna' in search_text:
            return 'buna'
        elif 'silicone' in search_text:
            return 'silicone'
        elif 'steel' in search_text:
            return 'steel'
        
        return material_spec.lower()
    
    def _get_material_order(self, material: str) -> int:
        """
        Get material priority for sorting.
        
        Args:
            material: Material string
            
        Returns:
            Priority value (lower = higher priority)
        """
        material_lower = material.lower()
        
        # Check for exact matches first
        if material_lower in self.material_priority:
            return self.material_priority[material_lower]
        
        # Check for partial matches
        for key, priority in self.material_priority.items():
            if key in material_lower:
                return priority
        
        return 999
    
    def _extract_dimensions(self, product: Dict) -> Dict:
        """
        Extract and normalize all dimensions.
        
        Args:
            product: Enhanced product dictionary
            
        Returns:
            Dictionary of normalized dimensions
        """
        dims = {}
        specs = product['specs']
        detail = product['detail']
        
        # Thread size (most important for fasteners)
        thread = specs.get('Thread Size', '')
        if not thread and 'Thread' in detail:
            # Extract from detail
            thread_match = re.search(
                r'(#?\d+(?:-\d+)?|'  # Number sizes like #4-40
                r'\d+/\d+"-?\d*|'    # Fractional like 1/4"-20
                r'[\d.]+"-?\d*|'     # Decimal like 0.25"-20
                r'M\d+(?:\.\d+)?)',  # Metric like M4
                detail
            )
            if thread_match:
                thread = thread_match.group(1)
        
        if thread:
            dims['thread'] = thread
            dims['thread_normalized'] = self._normalize_thread(thread)
        
        # Length
        length = specs.get('Length', specs.get('Overall Length', specs.get('Usable Length', '')))
        if not length and 'Long' in detail:
            length_match = re.search(r'([\d./-]+)"?\s+Long', detail)
            if length_match:
                length = length_match.group(1) + '"'
        
        if length:
            dims['length'] = length
            dims['length_normalized'] = self._normalize_length(length)
        
        # Diameter
        diameter = specs.get('Diameter', specs.get('OD', specs.get('ID', '')))
        if diameter:
            dims['diameter'] = diameter
            dims['diameter_normalized'] = self._normalize_length(diameter)
        
        # Width/Height
        width = specs.get('Width', '')
        if width:
            dims['width_normalized'] = self._normalize_length(width)
        
        height = specs.get('Height', '')
        if height:
            dims['height_normalized'] = self._normalize_length(height)
        
        # Dash number (for O-rings)
        dash = specs.get('Dash Number', '')
        if dash:
            dims['dash'] = dash
            dims['dash_normalized'] = self._extract_dash_number(dash)
        
        # Generic size
        size = specs.get('Size', specs.get('Screw Size', ''))
        if size:
            dims['size'] = size
            dims['size_normalized'] = self._normalize_length(size)
        
        return dims
    
    def _normalize_thread(self, thread: str) -> float:
        """
        Normalize thread size for consistent sorting.
        
        Priority order:
        1. Number sizes (#0-#12) - smallest
        2. Fractional/decimal inch
        3. Metric (M2, M3, etc.)
        4. Large inch sizes
        
        Args:
            thread: Thread size string
            
        Returns:
            Normalized numeric value
        """
        if not thread:
            return 999.0
        
        thread = str(thread).strip()
        
        # Number sizes (#2-56, #4-40, #10-24, etc.)
        num_match = re.match(r'#?(\d+)(?:-\d+)?', thread)
        if num_match:
            num = int(num_match.group(1))
            if num <= 12:  # Number sizes go up to #12
                return num * 0.001  # Very small values for proper ordering
        
        # Metric sizes (M2, M3, M4, M10, etc.)
        metric_match = re.match(r'M(\d+(?:\.\d+)?)', thread)
        if metric_match:
            mm = float(metric_match.group(1))
            # Convert to approximate inch equivalent
            # M2 ≈ 0.079", M3 ≈ 0.118", M4 ≈ 0.157", M10 ≈ 0.394"
            return (mm * 0.03937) + 0.05  # Slightly offset to sort after number sizes
        
        # Fractional inches (1/4"-20, 3/8"-16, etc.)
        frac_match = re.match(r'(\d+)/(\d+)', thread)
        if frac_match:
            return float(frac_match.group(1)) / float(frac_match.group(2))
        
        # Decimal inches (0.25", 0.375", etc.)
        dec_match = re.match(r'(\d+(?:\.\d+)?)', thread)
        if dec_match:
            return float(dec_match.group(1))
        
        return 999.0
    
    def _normalize_length(self, length: str) -> float:
        """
        Convert length to inches for sorting.
        
        Args:
            length: Length string with units
            
        Returns:
            Length in inches
        """
        if not length:
            return 999.0
        
        length = str(length).strip()
        
        # Mixed fractions (1-1/2", 2-3/4", etc.)
        mixed_match = re.match(r'(\d+)-(\d+)/(\d+)', length)
        if mixed_match:
            whole = float(mixed_match.group(1))
            num = float(mixed_match.group(2))
            den = float(mixed_match.group(3))
            return whole + (num / den)
        
        # Simple fractions (3/8", 1/2", etc.)
        frac_match = re.match(r'(\d+)/(\d+)', length)
        if frac_match:
            return float(frac_match.group(1)) / float(frac_match.group(2))
        
        # Metric units
        if 'mm' in length.lower():
            num_match = re.match(r'(\d+(?:\.\d+)?)', length)
            if num_match:
                return float(num_match.group(1)) * 0.03937
        
        if 'cm' in length.lower():
            num_match = re.match(r'(\d+(?:\.\d+)?)', length)
            if num_match:
                return float(num_match.group(1)) * 0.3937
        
        # Decimal (assume inches)
        dec_match = re.match(r'(\d+(?:\.\d+)?)', length)
        if dec_match:
            return float(dec_match.group(1))
        
        return 999.0
    
    def _extract_dash_number(self, dash: str) -> float:
        """
        Extract numeric value from dash number.
        
        Args:
            dash: Dash number string
            
        Returns:
            Numeric value
        """
        if not dash:
            return 999.0
        
        # Extract digits
        match = re.search(r'(\d+)', str(dash))
        if match:
            return float(match.group(1))
        
        return 999.0
    
    def _extract_profile(self, product: Dict) -> str:
        """
        Extract profile type (for screws).
        
        Args:
            product: Enhanced product dictionary
            
        Returns:
            Profile type string
        """
        specs = product['specs']
        family = product['family'].lower()
        
        # Check specs first
        profile = specs.get('Socket Head Profile', '')
        if profile:
            return profile.lower()
        
        # Check family description
        if 'low-profile' in family or 'low profile' in family:
            return 'low_profile'
        elif 'standard' in family:
            return 'standard'
        
        # Default for socket screws
        if 'socket' in family:
            return 'standard'
        
        return ''
    
    def _create_sort_key(self, product: Dict) -> Tuple:
        """
        Create comprehensive sort key for product.
        
        Sort hierarchy:
        1. Major category order
        2. Product category (alphabetical)
        3. Material order (quality)
        4. Profile (for screws)
        5. Thread size (normalized)
        6. Length (normalized)
        7. Other dimensions
        8. Part number
        
        Args:
            product: Enhanced product dictionary
            
        Returns:
            Sort key tuple
        """
        dims = product['dimensions']
        
        # For screws, consider profile
        profile_order = 0
        if product['major_category'] in ['socket_screws', 'button_screws', 'flat_screws']:
            profile = product.get('profile', '')
            if profile == 'low_profile':
                profile_order = 1  # Low profile after standard
        
        return (
            product['major_category_order'],                    # 1. Major category
            product['product_category'],                        # 2. Product category
            product['material_order'],                         # 3. Material quality
            profile_order,                                      # 4. Profile (screws)
            dims.get('thread_normalized', 999.0),              # 5. Thread size
            dims.get('length_normalized', 999.0),              # 6. Length
            dims.get('diameter_normalized', 999.0),            # 7. Diameter
            dims.get('width_normalized', 999.0),               # 8. Width
            dims.get('height_normalized', 999.0),              # 9. Height
            dims.get('dash_normalized', 999.0),                # 10. Dash (O-rings)
            dims.get('size_normalized', 999.0),                # 11. Generic size
            product['part_number']                             # 12. Part number
        )