import os
from typing import Tuple, Optional
import pint
from pint import UnitRegistry


# Initialize unit registry
ureg = UnitRegistry()


def parse_dimension(value: str) -> float:
    """Parse a dimension string with units and convert to inches.
    
    Args:
        value: Dimension string (e.g., "1.5in", "100mm", "2.54cm", "1.5")
    
    Returns:
        The dimension in inches as a float
    
    Raises:
        ValueError: If the dimension cannot be parsed or converted
    """
    try:
        # Validate input first
        if not value or not isinstance(value, str):
            raise ValueError("Dimension must be a non-empty string")
        
        value = value.strip()
        
        # Check if the value is just a number (no unit)
        try:
            # Try to parse as float
            numeric_value = float(value)
            # If successful, treat as inches
            return numeric_value
        except ValueError:
            # Not just a number, continue with unit parsing
            pass
        
        # Handle special cases
        if value.endswith('pt'):
            # Points to inches: 1 point = 1/72 inch
            num_str = value[:-2].strip()
            points = float(num_str)
            return points / 72.0
        elif value.endswith('px'):
            # Pixels to inches: assuming 96 DPI (standard screen resolution)
            num_str = value[:-2].strip()
            pixels = float(num_str)
            return pixels / 96.0
        
        # Parse the quantity with units
        quantity = ureg(value)
        
        # Convert to inches
        inches = quantity.to(ureg.inch)
        
        return inches.magnitude
    except Exception as e:
        raise ValueError(f"Invalid dimension '{value}': {str(e)}")


def get_cached_dimensions() -> Tuple[Optional[float], Optional[float]]:
    """Get cached label dimensions from environment variables.
    
    First checks session environment variables (MCMASTER_LABEL_WIDTH/HEIGHT),
    then falls back to config.py defaults if available.
    
    Returns:
        Tuple of (width, height) in inches, or (None, None) if not cached
    """
    # First check environment variables (set by previous runs in this session)
    width_str = os.getenv('MCMASTER_LABEL_WIDTH')
    height_str = os.getenv('MCMASTER_LABEL_HEIGHT')
    
    if width_str and height_str:
        try:
            return float(width_str), float(height_str)
        except ValueError:
            # Invalid cached values, ignore them
            pass
    
    # If no session cache, check if config.py has non-default values
    # This allows config.py to set different defaults
    from .config import config, DEFAULT_CONFIG
    
    config_width = config.get("LABEL_WIDTH_INCHES")
    config_height = config.get("LABEL_HEIGHT_INCHES")
    
    # Only use config values if they differ from the hardcoded defaults
    # This prevents circular logic where config values become "cached"
    if (config_width != DEFAULT_CONFIG["LABEL_WIDTH_INCHES"] or 
        config_height != DEFAULT_CONFIG["LABEL_HEIGHT_INCHES"]):
        return config_width, config_height
    
    return None, None


def cache_dimensions(width: float, height: float) -> None:
    """Cache label dimensions to environment variables for the session.
    
    Args:
        width: Label width in inches
        height: Label height in inches
    """
    os.environ['MCMASTER_LABEL_WIDTH'] = str(width)
    os.environ['MCMASTER_LABEL_HEIGHT'] = str(height)


def format_dimension_for_display(inches: float) -> str:
    """Format a dimension in inches for display.
    
    Args:
        inches: Dimension in inches
    
    Returns:
        Formatted string like "1.5in"
    """
    return f"{inches:.2f}in"


def validate_dimensions(width: float, height: float) -> None:
    """Validate that dimensions are reasonable for labels.
    
    Args:
        width: Label width in inches
        height: Label height in inches
    
    Raises:
        ValueError: If dimensions are invalid
    """
    MIN_SIZE = 0.25  # 1/4 inch minimum
    MAX_SIZE = 12.0  # 12 inches maximum
    
    if width <= 0 or height <= 0:
        raise ValueError("Label dimensions must be positive")
    
    if width < MIN_SIZE or height < MIN_SIZE:
        raise ValueError(f"Label dimensions must be at least {MIN_SIZE} inches")
    
    if width > MAX_SIZE or height > MAX_SIZE:
        raise ValueError(f"Label dimensions must not exceed {MAX_SIZE} inches")
    
    # Warn about unusual aspect ratios but don't fail
    aspect_ratio = width / height
    if aspect_ratio < 0.25 or aspect_ratio > 4.0:
        print(f"Warning: Unusual aspect ratio {aspect_ratio:.2f}:1")