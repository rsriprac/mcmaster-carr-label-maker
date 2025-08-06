import logging
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageOps
import io

from .config import LABEL_WIDTH_INCHES, LABEL_HEIGHT_INCHES, LABEL_IMAGE_WIDTH_RATIO

logger = logging.getLogger(__name__)

# DPI for label printing
DPI = 300


class ImageProcessor:
    """Process and prepare images for label generation."""
    
    def __init__(self):
        # Calculate pixel dimensions based on physical label size and print DPI
        # Calculate dimensions based on configured label size and DPI
        self.label_width_px = int(LABEL_WIDTH_INCHES * DPI)
        self.label_height_px = int(LABEL_HEIGHT_INCHES * DPI)
        # Images occupy 25% of label width (left side)
        self.image_width_px = int(self.label_width_px * LABEL_IMAGE_WIDTH_RATIO)
        
    def process_image(self, image_path: Path) -> Optional[Image.Image]:
        """Process an image file for high-resolution label use."""
        try:
            if not image_path.exists():
                logger.error(f"Image file not found: {image_path}")
                return None
                
            # Open image with maximum quality preservation
            # Keep original resolution for best PDF output quality
            img = Image.open(image_path)
            
            # Log original image dimensions for debugging
            logger.debug(f"Processing image {image_path.name}: {img.size[0]}x{img.size[1]} pixels")
            
            # Convert to RGB if necessary (handles transparency and other color modes)
            # Labels print better with solid backgrounds rather than transparency
            if img.mode in ('RGBA', 'LA'):
                # Create white background for transparent images
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    # Use alpha channel as mask for proper blending
                    background.paste(img, mask=img.split()[3])
                else:
                    # LA mode: use luminance alpha channel
                    background.paste(img, mask=img.split()[1])
                img = background
            elif img.mode != 'RGB':
                # Convert other modes (grayscale, CMYK, etc.) to RGB
                img = img.convert('RGB')
            
            # Resize to fit label dimensions
            img = self._resize_to_fit(img)
            
            return img
            
        except Exception as e:
            logger.error(f"Error processing image {image_path}: {str(e)}")
            return None
    
    def _resize_to_fit(self, img: Image.Image) -> Image.Image:
        """Prepare image for high-resolution PDF output.
        
        Instead of pre-resizing to exact pixel dimensions, we preserve the source
        resolution and let ReportLab handle the final scaling for optimal quality.
        """
        # For maximum resolution preservation, avoid unnecessary resizing
        # Only resize if the source image is much larger than needed to save memory
        img_width, img_height = img.size
        
        # Target dimensions at 300 DPI for reference
        target_width = self.image_width_px
        target_height = self.label_height_px
        
        # Calculate if we need to downscale for memory efficiency
        # Only downscale if image is more than 3x larger than target
        max_efficient_width = target_width * 3
        max_efficient_height = target_height * 3
        
        if img_width > max_efficient_width or img_height > max_efficient_height:
            # Calculate scaling to fit within efficient bounds while maintaining aspect ratio
            width_ratio = max_efficient_width / img_width
            height_ratio = max_efficient_height / img_height
            scale_ratio = min(width_ratio, height_ratio)
            
            new_width = int(img_width * scale_ratio)
            new_height = int(img_height * scale_ratio)
            
            # Resize with highest quality - LANCZOS provides best quality for scaling
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Return the high-resolution image for ReportLab to handle final sizing
        # This preserves maximum quality in the PDF output
        return img
    
    def process_cad_placeholder(self) -> Image.Image:
        """Create a placeholder image when CAD conversion isn't available."""
        # Create a simple placeholder with a border
        img = Image.new('RGB', (self.image_width_px, self.label_height_px), (255, 255, 255))
        
        # Draw a simple border
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        border_width = 2
        draw.rectangle(
            [border_width, border_width, 
             self.image_width_px - border_width, self.label_height_px - border_width],
            outline=(200, 200, 200),
            width=border_width
        )
        
        # Add "CAD" text in center
        text = "CAD"
        # Simple text placement (would need font for better rendering)
        draw.text(
            (self.image_width_px // 2 - 15, self.label_height_px // 2 - 5),
            text,
            fill=(150, 150, 150)
        )
        
        return img
    
    def get_image_for_product(self, image_path: Optional[Path], cad_path: Optional[Path]) -> Optional[Image.Image]:
        """Get the best available image for a product."""
        # Priority: Use PNG/JPG image if available (pre-rendered, ready to use)
        if image_path and Path(image_path).exists():
            img = self.process_image(Path(image_path))
            if img:
                return img
        
        # Fallback: Create placeholder if no usable image found
        # TODO: Future enhancement could convert CAD files to images
        # For now, just indicate that CAD data exists
        logger.info("Using CAD placeholder as image not available")
        return self.process_cad_placeholder()