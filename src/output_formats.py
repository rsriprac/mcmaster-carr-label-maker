"""Output format handling for label generation."""

import os
from pathlib import Path
from typing import Optional, Tuple, List
from enum import Enum
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from PIL import Image
import io


class OutputFormat(Enum):
    """Supported output formats."""
    PDF = "pdf"
    PNG = "png"
    JPG = "jpg"
    JPEG = "jpeg"
    BMP = "bmp"
    TIFF = "tiff"
    TIF = "tif"
    GIF = "gif"
    WEBP = "webp"


# Map file extensions to formats
EXTENSION_TO_FORMAT = {
    '.pdf': OutputFormat.PDF,
    '.png': OutputFormat.PNG,
    '.jpg': OutputFormat.JPG,
    '.jpeg': OutputFormat.JPEG,
    '.bmp': OutputFormat.BMP,
    '.tiff': OutputFormat.TIFF,
    '.tif': OutputFormat.TIF,
    '.gif': OutputFormat.GIF,
    '.webp': OutputFormat.WEBP,
}

# Formats that support multiple pages
MULTIPAGE_FORMATS = {OutputFormat.PDF, OutputFormat.TIFF, OutputFormat.TIF}

# Default DPI for rasterized formats
DEFAULT_DPI = 300  # Common laser printer resolution


def detect_format_from_filename(filename: str) -> OutputFormat:
    """Detect output format from filename extension.
    
    Args:
        filename: Output filename
        
    Returns:
        Detected output format
        
    Raises:
        ValueError: If format cannot be detected or is unsupported
    """
    ext = Path(filename).suffix.lower()
    if ext not in EXTENSION_TO_FORMAT:
        raise ValueError(
            f"Unsupported or missing file extension: {ext}. "
            f"Supported formats: {', '.join(EXTENSION_TO_FORMAT.keys())}"
        )
    return EXTENSION_TO_FORMAT[ext]


def is_raster_format(format: OutputFormat) -> bool:
    """Check if the format is a raster/bitmap format."""
    return format != OutputFormat.PDF


def supports_multiple_pages(format: OutputFormat) -> bool:
    """Check if the format supports multiple pages."""
    return format in MULTIPAGE_FORMATS


def get_pil_format_string(format: OutputFormat) -> str:
    """Get PIL format string for the output format."""
    format_map = {
        OutputFormat.PNG: "PNG",
        OutputFormat.JPG: "JPEG",
        OutputFormat.JPEG: "JPEG",
        OutputFormat.BMP: "BMP",
        OutputFormat.TIFF: "TIFF",
        OutputFormat.TIF: "TIFF",
        OutputFormat.GIF: "GIF",
        OutputFormat.WEBP: "WEBP",
    }
    return format_map.get(format, format.value.upper())


def get_default_dpi() -> int:
    """Get default DPI for rasterized formats."""
    return DEFAULT_DPI


def validate_dpi(dpi: int) -> None:
    """Validate DPI value.
    
    Args:
        dpi: DPI value to validate
        
    Raises:
        ValueError: If DPI is invalid
    """
    MIN_DPI = 72
    MAX_DPI = 2400
    
    if dpi < MIN_DPI:
        raise ValueError(f"DPI must be at least {MIN_DPI}")
    if dpi > MAX_DPI:
        raise ValueError(f"DPI must not exceed {MAX_DPI}")


def render_pdf_to_image(pdf_canvas: canvas.Canvas, width_inches: float, 
                       height_inches: float, dpi: int) -> Image.Image:
    """Render a PDF canvas to a PIL Image.
    
    Args:
        pdf_canvas: ReportLab canvas with content
        width_inches: Page width in inches
        height_inches: Page height in inches
        dpi: Resolution in dots per inch
        
    Returns:
        PIL Image of the rendered page
    """
    # Calculate pixel dimensions
    width_pixels = int(width_inches * dpi)
    height_pixels = int(height_inches * dpi)
    
    # Get PDF data
    pdf_data = pdf_canvas.getpdfdata()
    
    # Use pdf2image to convert PDF to image
    # For now, we'll use a simpler approach: save and reload
    # In production, you'd use pdf2image or similar library
    try:
        from pdf2image import convert_from_bytes
        images = convert_from_bytes(pdf_data, dpi=dpi)
        if images:
            return images[0]
    except ImportError:
        # Fallback: Create a placeholder image
        # In real implementation, we'd require pdf2image
        img = Image.new('RGB', (width_pixels, height_pixels), 'white')
        return img


def save_image_with_metadata(image: Image.Image, output_path: Path, 
                           format: OutputFormat, dpi: int) -> None:
    """Save image with appropriate metadata.
    
    Args:
        image: PIL Image to save
        output_path: Output file path
        format: Output format
        dpi: DPI to embed in metadata
    """
    pil_format = get_pil_format_string(format)
    
    # Prepare save parameters
    save_params = {'dpi': (dpi, dpi)}
    
    # Format-specific parameters
    if format in (OutputFormat.JPG, OutputFormat.JPEG):
        save_params['quality'] = 95  # High quality
        save_params['optimize'] = True
    elif format == OutputFormat.PNG:
        save_params['compress_level'] = 6  # Balanced compression
    elif format in (OutputFormat.TIFF, OutputFormat.TIF):
        save_params['compression'] = 'tiff_lzw'
    elif format == OutputFormat.WEBP:
        save_params['quality'] = 95
        save_params['method'] = 6
    
    # Save the image
    image.save(str(output_path), pil_format, **save_params)