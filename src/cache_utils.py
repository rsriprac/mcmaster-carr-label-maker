"""
Cache utilities for managing placeholder files and cache expiration.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Placeholder file extensions
PLACEHOLDER_EXT = '.notfound'
DEFAULT_PLACEHOLDER_EXPIRY_DAYS = 14  # Placeholders expire after 2 weeks by default
MIN_PLACEHOLDER_EXPIRY_DAYS = 7  # Minimum 1 week before expiry


def create_placeholder(cache_dir: Path, prefix: str, product_id: str, 
                      expiry_days: int = None) -> Path:
    """
    Create a placeholder file indicating that an asset doesn't exist.
    
    Args:
        cache_dir: Cache directory path
        prefix: File prefix ('image' or 'cad')
        product_id: Product ID
        expiry_days: Days until expiry (default: 14 days)
        
    Returns:
        Path to created placeholder file
    """
    if expiry_days is None:
        expiry_days = DEFAULT_PLACEHOLDER_EXPIRY_DAYS
    elif expiry_days < MIN_PLACEHOLDER_EXPIRY_DAYS:
        expiry_days = MIN_PLACEHOLDER_EXPIRY_DAYS
        logger.warning(f"Expiry days {expiry_days} too low, using minimum {MIN_PLACEHOLDER_EXPIRY_DAYS}")
    
    placeholder_path = cache_dir / f"{prefix}_{product_id}{PLACEHOLDER_EXT}"
    
    # Create placeholder with metadata
    placeholder_data = {
        'product_id': product_id,
        'asset_type': prefix,
        'created_at': datetime.now().isoformat(),
        'message': f'No {prefix} available for this product',
        'expiry_days': expiry_days
    }
    
    with open(placeholder_path, 'w') as f:
        json.dump(placeholder_data, f, indent=2)
    
    logger.debug(f"Created placeholder for missing {prefix}: {placeholder_path} (expires in {expiry_days} days)")
    return placeholder_path


def is_placeholder_valid(placeholder_path: Path) -> bool:
    """
    Check if a placeholder file exists and is still valid (not expired).
    
    Args:
        placeholder_path: Path to placeholder file
        
    Returns:
        True if placeholder exists and is not expired, False otherwise
    """
    if not placeholder_path.exists():
        return False
    
    try:
        # Read placeholder metadata
        with open(placeholder_path, 'r') as f:
            data = json.load(f)
        
        # Get expiry days from the file or use default
        expiry_days = data.get('expiry_days', DEFAULT_PLACEHOLDER_EXPIRY_DAYS)
        
        # Check creation time
        created_at = datetime.fromisoformat(data['created_at'])
        expiry_time = created_at + timedelta(days=expiry_days)
        
        if datetime.now() > expiry_time:
            age_days = (datetime.now() - created_at).days
            logger.debug(f"Placeholder expired: {placeholder_path} (age: {age_days} days, expiry: {expiry_days} days)")
            # Delete expired placeholder
            placeholder_path.unlink()
            return False
        
        # Log that we're using a valid placeholder
        age_days = (datetime.now() - created_at).days
        logger.debug(f"Using valid placeholder: {placeholder_path} (age: {age_days} days, expires in {expiry_days - age_days} days)")
        return True
        
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"Invalid placeholder file {placeholder_path}: {e}")
        # Delete invalid placeholder
        try:
            placeholder_path.unlink()
        except:
            pass
        return False


def check_for_placeholder(cache_dir: Path, prefix: str, product_id: str) -> bool:
    """
    Check if a valid placeholder exists for a product asset.
    
    Args:
        cache_dir: Cache directory path
        prefix: File prefix ('image' or 'cad')
        product_id: Product ID
        
    Returns:
        True if valid placeholder exists, False otherwise
    """
    placeholder_path = cache_dir / f"{prefix}_{product_id}{PLACEHOLDER_EXT}"
    return is_placeholder_valid(placeholder_path)


def check_cache_with_placeholders(cache_dir: Path, prefix: str, product_id: str, 
                                 extensions: list) -> Optional[Path]:
    """
    Check cache for actual files or valid placeholders.
    
    Args:
        cache_dir: Cache directory path
        prefix: File prefix ('image' or 'cad')
        product_id: Product ID
        extensions: List of file extensions to check
        
    Returns:
        Path to cached file if found, None if not found or placeholder exists
    """
    # First check for placeholder
    if check_for_placeholder(cache_dir, prefix, product_id):
        logger.debug(f"Valid placeholder found for {prefix}_{product_id}, skipping download")
        return None  # Placeholder indicates no asset available
    
    # Check for actual cached files
    for ext in extensions:
        cached_path = cache_dir / f"{prefix}_{product_id}{ext}"
        if cached_path.exists():
            logger.debug(f"Found cached {prefix} for {product_id}: {cached_path}")
            return cached_path
    
    return None  # No cache or placeholder found


def clean_expired_placeholders(cache_dir: Path) -> int:
    """
    Clean up all expired placeholder files in the cache directory.
    
    Args:
        cache_dir: Cache directory path
        
    Returns:
        Number of placeholders cleaned
    """
    if not cache_dir.exists():
        return 0
    
    cleaned = 0
    for placeholder_path in cache_dir.glob(f"*{PLACEHOLDER_EXT}"):
        if not is_placeholder_valid(placeholder_path):
            cleaned += 1
    
    if cleaned > 0:
        logger.info(f"Cleaned {cleaned} expired placeholder files")
    
    return cleaned


def get_cache_statistics(cache_dir: Path) -> Dict[str, Any]:
    """
    Get statistics about cache usage including placeholders.
    
    Args:
        cache_dir: Cache directory path
        
    Returns:
        Dictionary with cache statistics
    """
    if not cache_dir.exists():
        return {
            'total_files': 0,
            'placeholders': 0,
            'images': 0,
            'cad_files': 0,
            'product_info': 0,
            'total_size_mb': 0
        }
    
    stats = {
        'total_files': 0,
        'placeholders': 0,
        'expired_placeholders': 0,
        'images': 0,
        'cad_files': 0,
        'product_info': 0,
        'total_size_mb': 0
    }
    
    total_size = 0
    
    for file_path in cache_dir.iterdir():
        if file_path.is_file():
            stats['total_files'] += 1
            total_size += file_path.stat().st_size
            
            if file_path.suffix == PLACEHOLDER_EXT:
                stats['placeholders'] += 1
                if not is_placeholder_valid(file_path):
                    stats['expired_placeholders'] += 1
            elif file_path.name.startswith('image_'):
                stats['images'] += 1
            elif file_path.name.startswith('cad_'):
                stats['cad_files'] += 1
            elif file_path.name.startswith('product_'):
                stats['product_info'] += 1
    
    stats['total_size_mb'] = round(total_size / (1024 * 1024), 2)
    
    return stats