import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
import reportlab.lib.pagesizes
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image, ImageDraw, ImageFont
import io
import tempfile

from .config import LABEL_WIDTH_INCHES, LABEL_HEIGHT_INCHES, OUTPUT_DIR
from .image_processor import ImageProcessor
from .output_formats import (
    OutputFormat, save_image_with_metadata, supports_multiple_pages,
    get_pil_format_string
)
from .dynamic_label_layout_v3 import DynamicLabelLayoutV3
from .visual_similarity import VisualSimilarityAnalyzer
from .fuzzy_text_sorter import FuzzyTextSorter
from .fuzzy_text_sorter_v4 import FuzzyTextSorterV4

logger = logging.getLogger(__name__)


class LabelGenerator:
    """Generate labels for McMaster-Carr parts in various formats (PDF, PNG, JPG, etc.)."""
    
    def __init__(self, width_inches: float = None, height_inches: float = None):
        self.image_processor = ImageProcessor()
        # Use provided dimensions or fall back to config defaults
        self.width_inches = width_inches if width_inches is not None else LABEL_WIDTH_INCHES
        self.height_inches = height_inches if height_inches is not None else LABEL_HEIGHT_INCHES
        self.page_width = self.width_inches * inch
        self.page_height = self.height_inches * inch
        self.margin = 0.05 * inch  # 0.05 inch margin
        self.image_width = self.page_width * 0.25  # 25% for image
        self.text_start_x = self.image_width + self.margin
        
        # Initialize dynamic layout engine
        self.layout_engine = DynamicLabelLayoutV3(
            width_inches=self.width_inches,
            height_inches=self.height_inches
        )
        
    def generate_labels(self, products_data: Dict[str, Dict[str, Any]], 
                       output_filename: str = "labels.pdf",
                       output_format: Optional[OutputFormat] = None,
                       dpi: Optional[int] = None,
                       sort_by_similarity: bool = False,
                       similarity_method: str = 'hierarchical',
                       sort_by_text: bool = False,
                       text_sort_field: str = 'description',
                       sort_by_fuzzy: bool = False,
                       fuzzy_threshold: float = 0.3) -> Path:
        """Generate labels in the specified format.
        
        Args:
            products_data: Product data dictionary
            output_filename: Output filename
            output_format: Output format (default: PDF)
            dpi: DPI for raster formats
            sort_by_similarity: Whether to sort pages by visual similarity
            similarity_method: Method for similarity sorting ('hierarchical', 'spectral', or 'greedy')
            sort_by_text: Whether to sort pages alphabetically by text
            text_sort_field: Field to use for text sorting ('description', 'product_id', 'family', 'detail')
            sort_by_fuzzy: Whether to use fuzzy text grouping with dimension sorting
            fuzzy_threshold: Similarity threshold for fuzzy grouping (0-1)
            
        Returns:
            Path to generated file
        """
        output_path = OUTPUT_DIR / output_filename
        
        # Sort products by visual similarity if requested
        if sort_by_similarity and len(products_data) > 1:
            logger.info(f"Sorting {len(products_data)} products by visual similarity using {similarity_method} method")
            analyzer = VisualSimilarityAnalyzer()
            sorted_product_ids = analyzer.sort_by_similarity(products_data, method=similarity_method)
            
            # Reorder products_data
            sorted_products_data = {}
            for product_id in sorted_product_ids:
                sorted_products_data[product_id] = products_data[product_id]
            products_data = sorted_products_data
            
            logger.info("Products sorted by visual similarity")
        
        # Sort products by text if requested
        elif sort_by_text and len(products_data) > 1:
            logger.info(f"Sorting {len(products_data)} products alphabetically by {text_sort_field}")
            
            # Create list of tuples (product_id, sort_key)
            sort_items = []
            for product_id, data in products_data.items():
                info = data.get('info', {})
                
                # Extract the sort key based on the field
                if text_sort_field == 'product_id':
                    sort_key = product_id
                elif text_sort_field == 'family':
                    sort_key = info.get('FamilyDescription', '')
                elif text_sort_field == 'detail':
                    sort_key = info.get('DetailDescription', '')
                else:  # 'description' - combines family and detail
                    family = info.get('FamilyDescription', '')
                    detail = info.get('DetailDescription', '')
                    if family and detail:
                        sort_key = f"{family} - {detail}"
                    else:
                        sort_key = family or detail or ''
                
                # Handle None values
                if sort_key is None:
                    sort_key = ''
                    
                sort_items.append((product_id, sort_key.lower()))  # Case-insensitive sort
            
            # Sort by the sort key
            sort_items.sort(key=lambda x: x[1])
            
            # Reorder products_data
            sorted_products_data = {}
            for product_id, _ in sort_items:
                sorted_products_data[product_id] = products_data[product_id]
            products_data = sorted_products_data
            
            logger.info(f"Products sorted alphabetically by {text_sort_field}")
        
        # Sort products using fuzzy text grouping if requested
        elif sort_by_fuzzy and len(products_data) > 1:
            logger.info(f"Sorting {len(products_data)} products using enhanced fuzzy text grouping (v4)")
            
            # Use the improved v4 sorter for better performance
            sorter = FuzzyTextSorterV4()
            sorted_product_ids = sorter.sort_products(products_data)
            
            # Log category distribution for debugging
            if logger.isEnabledFor(logging.DEBUG):
                # Count products by major category
                category_counts = {}
                for pid in sorted_product_ids:
                    if pid in sorter.enhanced_products:
                        cat = sorter.enhanced_products[pid].get('major_category', 'unknown')
                        category_counts[cat] = category_counts.get(cat, 0) + 1
                for cat, count in sorted(category_counts.items()):
                    logger.debug(f"Category {cat}: {count} items")
            
            # Reorder products_data
            sorted_products_data = {}
            for product_id in sorted_product_ids:
                sorted_products_data[product_id] = products_data[product_id]
            products_data = sorted_products_data
            
            logger.info(f"Products sorted using fuzzy grouping (threshold: {fuzzy_threshold})")
        
        # Default to PDF if not specified
        if output_format is None:
            output_format = OutputFormat.PDF
        
        if output_format == OutputFormat.PDF:
            return self._generate_pdf(products_data, output_path)
        else:
            return self._generate_images(products_data, output_path, output_format, dpi or 300)
    
    def _generate_pdf(self, products_data: Dict[str, Dict[str, Any]], 
                     output_path: Path) -> Path:
        """Generate PDF with labels for all products."""
        # Create PDF with custom page size
        c = canvas.Canvas(
            str(output_path),
            pagesize=(self.page_width, self.page_height)
        )
        
        for product_id, data in products_data.items():
            self._create_label_page(c, product_id, data)
            c.showPage()  # New page for each label
        
        c.save()
        logger.info(f"Generated labels PDF: {output_path}")
        return output_path
    
    def _generate_images(self, products_data: Dict[str, Dict[str, Any]], 
                        output_path: Path, output_format: OutputFormat,
                        dpi: int) -> Path:
        """Generate image labels by first creating PDF then converting to ensure consistency."""
        import tempfile
        import fitz  # PyMuPDF
        
        # Create a temporary PDF first
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_pdf:
            tmp_pdf_path = Path(tmp_pdf.name)
        
        try:
            # Generate PDF to temporary file
            self._generate_pdf(products_data, tmp_pdf_path)
            
            # Open PDF with PyMuPDF
            pdf_document = fitz.open(str(tmp_pdf_path))
            
            images = []
            # Convert each page to image at specified DPI
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                # Render page to image at specified DPI
                mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)  # 72 DPI is PDF default
                pix = page.get_pixmap(matrix=mat, alpha=False)
                
                # Convert to PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                images.append(img)
            
            pdf_document.close()
            
            # Save based on format capabilities
            if len(images) == 1:
                # Single image
                save_image_with_metadata(images[0], output_path, output_format, dpi)
            elif supports_multiple_pages(output_format):
                # Multi-page TIFF
                images[0].save(
                    str(output_path), 
                    save_all=True, 
                    append_images=images[1:],
                    dpi=(dpi, dpi)
                )
            else:
                # Multiple files with numbered names
                base_path = output_path.parent / output_path.stem
                suffix = output_path.suffix
                for i, img in enumerate(images):
                    numbered_path = Path(f"{base_path}_{i+1:03d}{suffix}")
                    save_image_with_metadata(img, numbered_path, output_format, dpi)
                logger.info(f"Generated {len(images)} image files")
                return output_path.parent  # Return directory
            
            logger.info(f"Generated labels {output_format.value.upper()}: {output_path}")
            return output_path
            
        finally:
            # Clean up temporary PDF
            if tmp_pdf_path.exists():
                tmp_pdf_path.unlink()
    
    def _create_label_image(self, img: Image.Image, draw: ImageDraw.Draw, 
                           product_id: str, data: Dict[str, Any], dpi: int):
        """Create label content on a PIL image."""
        # Get product info
        product_info = data.get('info', {})
        
        # Get dynamic layout
        description = self._get_product_description(product_info)
        dimensions = self._get_dimensions_text(product_info)
        
        # Create a dummy canvas for layout calculations
        from reportlab.pdfgen import canvas as pdf_canvas
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=True) as tmp:
            c = pdf_canvas.Canvas(tmp.name)
            layout = self.layout_engine.calculate_layout(c, description, dimensions, product_id)
        
        # Add product image
        image_path = data.get('image_path')
        cad_path = data.get('cad_path')
        
        if image_path or cad_path:
            product_img = self.image_processor.get_image_for_product(
                Path(image_path) if image_path else None,
                Path(cad_path) if cad_path else None
            )
            if product_img:
                # Scale and position the product image
                self._add_image_to_pil(img, product_img, layout, dpi)
        
        # Add text using PIL with dynamic layout
        self.layout_engine.render_to_pil(draw, layout, dpi)
    
    def _add_image_to_pil(self, label_img: Image.Image, product_img: Image.Image, 
                         layout: Dict[str, Any], dpi: int):
        """Add product image to PIL label image using dynamic layout."""
        image_area = layout['image_area']
        
        # Convert inches to pixels
        available_width_px = int(image_area['width'] * dpi)
        available_height_px = int(image_area['height'] * dpi)
        x_px = int(image_area['x'] * dpi)
        y_px = int(image_area['y'] * dpi)
        
        # Calculate optimal size maintaining aspect ratio
        img_width, img_height = product_img.size
        scale_width = available_width_px / img_width
        scale_height = available_height_px / img_height
        scale = min(scale_width, scale_height) * 0.95  # 95% to ensure margin
        
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)
        
        # Resize image with high quality
        scaled_img = product_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Center the image within the available area
        x_offset = x_px + (available_width_px - new_width) // 2
        y_offset = y_px + (available_height_px - new_height) // 2
        
        # Paste the image
        label_img.paste(scaled_img, (x_offset, y_offset))
    
    def _add_text_to_pil_dynamic(self, draw: ImageDraw.Draw, text_layout: Dict[str, Any], dpi: int):
        """Add text to PIL image using dynamic layout."""
        # Convert font sizes from points to PIL sizes
        font_sizes = self.layout_engine.get_pil_font_sizes(text_layout, dpi)
        
        # Get text blocks
        desc_block = text_layout.get('description')
        dim_block = text_layout.get('dimensions')
        id_block = text_layout.get('product_id')
        
        # Calculate text start position
        text_start_x = int(self.width_inches * 0.25 * dpi) + int(0.05 * dpi)
        
        # Try to load appropriate fonts
        fonts = {}
        for block_name, block in [('description', desc_block), ('dimensions', dim_block), ('product_id', id_block)]:
            if block:
                try:
                    if block.is_bold:
                        fonts[block_name] = ImageFont.truetype("Arial-Bold.ttf", font_sizes[block_name])
                    else:
                        fonts[block_name] = ImageFont.truetype("Arial.ttf", font_sizes[block_name])
                except:
                    # Fallback to default font
                    try:
                        # Try to get a larger default font
                        fonts[block_name] = ImageFont.load_default()
                    except:
                        fonts[block_name] = ImageFont.load_default()
        
        # Draw text blocks
        if desc_block:
            y_pos = int((self.height_inches * dpi - desc_block.y_position))
            for line in desc_block.lines:
                draw.text((text_start_x, y_pos), line, fill='black', font=fonts.get('description'))
                y_pos += int(desc_block.line_height)
        
        if dim_block:
            y_pos = int((self.height_inches * dpi - dim_block.y_position))
            for line in dim_block.lines:
                draw.text((text_start_x, y_pos), line, fill='black', font=fonts.get('dimensions'))
                y_pos += int(dim_block.line_height)
        
        if id_block:
            y_pos = int((self.height_inches * dpi - id_block.y_position))
            for line in id_block.lines:
                draw.text((text_start_x, y_pos), line, fill='black', font=fonts.get('product_id'))
                y_pos += int(id_block.line_height)
    
    def _add_text_to_pil(self, draw: ImageDraw.Draw, product_id: str, 
                        product_info: Dict[str, Any], text_start_x: int, 
                        margin_px: int, dpi: int):
        """Add text to PIL image."""
        # Try to use a good font, fallback to default
        try:
            # Scale font sizes based on DPI (assuming 72 DPI as base)
            scale = dpi / 72.0
            font_regular = ImageFont.truetype("Arial.ttf", int(10 * scale))
            font_bold = ImageFont.truetype("Arial-Bold.ttf", int(11 * scale))
        except:
            # Fallback to default font
            font_regular = ImageFont.load_default()
            font_bold = font_regular
        
        # Get text content
        description = product_info.get('short_description', 'McMaster-Carr Part')
        dimension_text = self._get_dimension_text(product_info)
        
        # Calculate text positions
        img_width = int(self.width_inches * dpi)
        img_height = int(self.height_inches * dpi)
        text_width = img_width - text_start_x - margin_px
        
        # Simple text layout - vertically centered
        line_height = int(14 * scale)
        total_height = line_height * 3
        y_start = (img_height - total_height) // 2
        
        # Draw text lines
        y = y_start
        
        # Description (bold)
        self._draw_wrapped_text(draw, description, text_start_x, y, text_width, font_bold)
        y += line_height
        
        # Dimensions
        if dimension_text:
            self._draw_wrapped_text(draw, dimension_text, text_start_x, y, text_width, font_regular)
            y += line_height
        
        # Product ID
        self._draw_wrapped_text(draw, f"#{product_id}", text_start_x, y, text_width, font_regular)
    
    def _draw_wrapped_text(self, draw: ImageDraw.Draw, text: str, x: int, y: int, 
                          max_width: int, font: ImageFont.FreeTypeFont):
        """Draw text with simple wrapping."""
        # Simple implementation - just truncate if too long
        # In production, you'd implement proper word wrapping
        try:
            text_width = draw.textlength(text, font=font)
            if text_width <= max_width:
                draw.text((x, y), text, fill='black', font=font)
            else:
                # Truncate with ellipsis
                while text and draw.textlength(text + '...', font=font) > max_width:
                    text = text[:-1]
                draw.text((x, y), text + '...', fill='black', font=font)
        except:
            # Fallback for older PIL versions
            draw.text((x, y), text, fill='black', font=font)
    
    def _create_label_page(self, c: canvas.Canvas, product_id: str, data: Dict[str, Any]):
        """Create a single label page."""
        # Get product info
        product_info = data.get('info', {})
        
        # Get dynamic layout for the whole label
        description = self._get_product_description(product_info)
        dimensions = self._get_dimensions_text(product_info)
        layout = self.layout_engine.calculate_layout(c, description, dimensions, product_id)
        
        # Add image
        image_path = data.get('image_path')
        cad_path = data.get('cad_path')
        
        if image_path or cad_path:
            img = self.image_processor.get_image_for_product(
                Path(image_path) if image_path else None,
                Path(cad_path) if cad_path else None
            )
            if img:
                self._add_image_to_pdf(c, img, layout)
        
        # Add text information
        self._add_product_text(c, product_id, product_info)
    
    def _add_image_to_pdf(self, c: canvas.Canvas, img: Image.Image, layout: Dict[str, Any] = None):
        """Add PIL image to PDF canvas with maximum resolution preservation."""
        # For maximum quality, try to pass image directly to ReportLab
        # This avoids any file compression artifacts
        use_temp_file = False
        try:
            # Create an in-memory buffer with the image
            img_buffer = io.BytesIO()
            # Save as PNG with maximum quality (no compression)
            img.save(img_buffer, format='PNG', compress_level=0, optimize=False)
            img_buffer.seek(0)
            
            # Use ImageReader for direct image handling (higher quality)
            image_source = ImageReader(img_buffer)
            
        except Exception as e:
            logger.warning(f"Failed to use direct image method, falling back to temp file: {e}")
            # Fallback: Save image to temporary file for ReportLab with maximum quality
            temp_image_path = OUTPUT_DIR / f"temp_image_{id(img)}.png"
            img.save(temp_image_path, format='PNG', compress_level=0, optimize=False)
            image_source = str(temp_image_path)
            use_temp_file = True
        
        try:
            # Use dynamic layout if provided
            if layout:
                image_area = layout['image_area']
                available_width = image_area['width'] * inch
                available_height = image_area['height'] * inch
                x_offset = image_area['x'] * inch
                y_offset = image_area['y'] * inch
            else:
                # Fallback to old layout
                available_width = self.image_width * 0.9
                available_height = self.page_height * 0.9
                x_offset = self.margin
                y_offset = self.margin
            
            img_width, img_height = img.size
            aspect_ratio = img_width / img_height
            
            # Determine the actual drawn size - fit image within available space
            # Choose the smaller scale factor to ensure image fits in both dimensions
            width_scale = available_width / img_width
            height_scale = available_height / img_height
            scale_factor = min(width_scale, height_scale)
            
            # Calculate final drawn dimensions
            drawn_width = img_width * scale_factor
            drawn_height = img_height * scale_factor
            
            # Center the image within its allocated space (25% of page width)
            # Calculate offsets to center both horizontally and vertically
            y_offset = (self.page_height - drawn_height) / 2
            x_offset = (self.image_width - drawn_width) / 2
            
            # Draw image on canvas with maximum quality preservation
            # ReportLab coordinate system: (0,0) is bottom-left corner
            c.drawImage(
                image_source,  # Use direct image source for best quality
                x_offset,  # x position (centered within image area)
                y_offset,  # y position (vertically centered)
                width=drawn_width,
                height=drawn_height,
                preserveAspectRatio=True,  # Maintain aspect ratio
                mask='auto'  # Handle transparency if present
            )
        finally:
            # Clean up temporary file only if we used one
            if use_temp_file and 'temp_image_path' in locals() and temp_image_path.exists():
                temp_image_path.unlink()
    
    def _add_product_text(self, c: canvas.Canvas, product_id: str, product_info: Dict[str, Any]):
        """Add product text to the label with dynamic font sizing."""
        # Get dynamic layout
        description = self._get_product_description(product_info)
        dimensions = self._get_dimensions_text(product_info)
        
        layout = self.layout_engine.calculate_layout(c, description, dimensions, product_id)
        
        # Render the text using the dynamic layout
        self.layout_engine.render_to_pdf(c, layout)
    
    def _render_dynamic_text_layout(self, c: canvas.Canvas, text_layout: Dict[str, Any]):
        """Render text blocks using dynamic layout calculations."""
        # Get text blocks
        desc_block = text_layout.get('description')
        dim_block = text_layout.get('dimensions')
        id_block = text_layout.get('product_id')
        
        # Calculate text start position
        text_start_x = self.width_inches * 0.25 * inch + 0.05 * inch
        
        # Render each block
        if desc_block:
            c.setFont(desc_block.font_name, desc_block.font_size)
            y_pos = desc_block.y_position
            for line in desc_block.lines:
                c.drawString(text_start_x, y_pos, line)
                y_pos -= desc_block.line_height
        
        if dim_block:
            c.setFont(dim_block.font_name, dim_block.font_size)
            y_pos = dim_block.y_position
            for line in dim_block.lines:
                c.drawString(text_start_x, y_pos, line)
                y_pos -= dim_block.line_height
        
        if id_block:
            c.setFont(id_block.font_name, id_block.font_size)
            y_pos = id_block.y_position
            for line in id_block.lines:
                c.drawString(text_start_x, y_pos, line)
                y_pos -= id_block.line_height
    
    def _calculate_optimal_text_layout(self, c: canvas.Canvas, description: str, dimensions: str, 
                                     product_id_text: str, text_width: float, text_height: float) -> Dict:
        """Multi-pass optimization for optimal font sizes and layout."""
        
        # Multi-pass approach: cleaner code, better space utilization
        has_dimensions = bool(dimensions and dimensions.strip())
        
        # PASS 1: Baseline fitting - establish safe layout
        baseline_layout = self._pass1_baseline_fitting(
            c, description, dimensions, product_id_text, text_width, text_height, has_dimensions
        )
        
        # PASS 2: Space distribution - optimize available space
        optimized_layout = self._pass2_space_distribution(
            c, baseline_layout, text_width, text_height, description, dimensions
        )
        
        # PASS 3: Fine-tuning - perfect the layout
        final_layout = self._pass3_fine_tuning(
            c, optimized_layout, text_width, text_height
        )
        
        return final_layout
    
    def _pass1_baseline_fitting(self, c: canvas.Canvas, description: str, dimensions: str,
                               product_id_text: str, text_width: float, text_height: float,
                               has_dimensions: bool) -> Dict:
        """Pass 1: Create safe baseline layout that definitely fits."""
        
        if has_dimensions:
            # Start with conservative baseline sizes
            dim_font_size = 5
            desc_font_size = 4
            id_font_size = 4
        else:
            # No dimensions
            dim_font_size = 0
            desc_font_size = 4
            id_font_size = 4
        
        # Calculate baseline layout
        desc_lines = self._wrap_text_with_font(c, description, text_width, desc_font_size, "Helvetica-Bold")
        desc_line_height = desc_font_size * 1.2
        
        if has_dimensions:
            dim_lines = self._wrap_text_with_font(c, dimensions, text_width, dim_font_size, "Helvetica-Bold")
            dim_line_height = dim_font_size * 1.2
        else:
            dim_lines = []
            dim_line_height = 0
        
        id_lines = [product_id_text]
        id_line_height = id_font_size * 1.2
        
        # Calculate gaps
        gap_after_desc = (dim_line_height * 0.3) if dim_lines else (id_line_height * 0.3)
        gap_after_dim = (id_line_height * 0.3) if dim_lines else 0
        
        # Calculate total content height
        total_desc_height = len(desc_lines) * desc_line_height
        total_dim_height = len(dim_lines) * dim_line_height if dim_lines else 0
        total_id_height = id_line_height
        total_content_height = total_desc_height + total_dim_height + total_id_height + gap_after_desc + gap_after_dim
        
        return {
            'description': {'font_size': desc_font_size, 'lines': desc_lines, 'line_height': desc_line_height},
            'dimensions': {'font_size': dim_font_size, 'lines': dim_lines, 'line_height': dim_line_height} if dim_lines else None,
            'product_id': {'font_size': id_font_size, 'lines': id_lines, 'line_height': id_line_height},
            'total_content_height': total_content_height,
            'gap_after_desc': gap_after_desc,
            'gap_after_dim': gap_after_dim,
            'text_width': text_width,
            'text_height': text_height,
            'has_dimensions': has_dimensions
        }
    
    def _pass2_space_distribution(self, c: canvas.Canvas, baseline_layout: Dict, 
                                 text_width: float, text_height: float, 
                                 original_description: str = "", original_dimensions: str = "") -> Dict:
        """Pass 2: Distribute unused space optimally by priority."""
        
        # Calculate available space
        used_height = baseline_layout['total_content_height'] + (baseline_layout['description']['font_size'] * 0.75)
        available_space = text_height - used_height
        
        if available_space <= 1.0:  # Not much space to redistribute
            return baseline_layout
        
        # Distribute space by priority: dimensions > description > ID
        desc = baseline_layout['description'].copy()
        dim = baseline_layout['dimensions'].copy() if baseline_layout['dimensions'] else None
        pid = baseline_layout['product_id'].copy()
        
        # Try increasing fonts sizes while maintaining hierarchy
        max_attempts = int(available_space / 2)  # Conservative estimate
        
        for attempt in range(max_attempts):
            improved = False
            
            # Try increasing dimensions first (highest priority)
            if dim and dim['font_size'] < 8:
                new_dim_size = dim['font_size'] + 1
                new_dim_lines = self._wrap_text_with_font(c, original_dimensions, 
                                                        text_width, new_dim_size, "Helvetica-Bold")
                new_height = self._calculate_layout_height(desc, {'font_size': new_dim_size, 'lines': new_dim_lines}, pid)
                
                if new_height + (desc['font_size'] * 0.75) <= text_height:
                    dim['font_size'] = new_dim_size
                    dim['lines'] = new_dim_lines
                    dim['line_height'] = new_dim_size * 1.2
                    improved = True
            
            # Try increasing description (second priority)
            elif desc['font_size'] < (dim['font_size'] if dim else 8) and desc['font_size'] < 8:
                new_desc_size = desc['font_size'] + 1
                new_desc_lines = self._wrap_text_with_font(c, original_description, text_width, new_desc_size, "Helvetica-Bold")
                new_height = self._calculate_layout_height({'font_size': new_desc_size, 'lines': new_desc_lines}, dim, pid)
                
                if new_height + (new_desc_size * 0.75) <= text_height:
                    desc['font_size'] = new_desc_size
                    desc['lines'] = new_desc_lines
                    desc['line_height'] = new_desc_size * 1.2
                    improved = True
            
            # Try increasing ID (lowest priority) 
            elif pid['font_size'] < desc['font_size'] - 1 and pid['font_size'] < 6:
                new_id_size = pid['font_size'] + 1
                new_height = self._calculate_layout_height(desc, dim, {'font_size': new_id_size, 'lines': pid['lines']})
                
                if new_height + (desc['font_size'] * 0.75) <= text_height:
                    pid['font_size'] = new_id_size
                    pid['line_height'] = new_id_size * 1.2
                    improved = True
            
            if not improved:
                break
        
        # Update the layout
        updated_layout = baseline_layout.copy()
        updated_layout['description'] = desc
        updated_layout['dimensions'] = dim
        updated_layout['product_id'] = pid
        
        return updated_layout
    
    def _pass3_fine_tuning(self, c: canvas.Canvas, optimized_layout: Dict, 
                          text_width: float, text_height: float) -> Dict:
        """Pass 3: Fine-tune positioning and create final layout."""
        
        desc = optimized_layout['description']
        dim = optimized_layout['dimensions']
        pid = optimized_layout['product_id']
        
        # Calculate final positioning
        total_desc_height = len(desc['lines']) * desc['line_height']
        total_dim_height = len(dim['lines']) * dim['line_height'] if dim else 0
        total_id_height = pid['line_height']
        
        gap_after_desc = (dim['line_height'] * 0.3) if dim else (pid['line_height'] * 0.3)
        gap_after_dim = (pid['line_height'] * 0.3) if dim else 0
        
        total_content_height = total_desc_height + total_dim_height + total_id_height + gap_after_desc + gap_after_dim
        first_line_ascent = desc['font_size'] * 0.75
        
        # Position text block - center vertically if it fits, otherwise align to top
        available_height = text_height
        if total_content_height + first_line_ascent <= available_height:
            # Text fits with room to spare - center it vertically
            vertical_padding = (available_height - total_content_height - first_line_ascent) / 2
            y_start = self.page_height - self.margin - first_line_ascent - vertical_padding
        else:
            # Text is tight - position from top margin to maximize readability
            y_start = self.page_height - self.margin - first_line_ascent
        
        # Calculate element positions - stack from top to bottom
        # Description at top, then dimensions, then product ID at bottom
        desc_y = y_start
        dim_y = desc_y - total_desc_height - gap_after_desc if dim else None
        id_y = desc_y - total_desc_height - gap_after_desc - total_dim_height - gap_after_dim
        
        # Return final layout
        return {
            'description': {
                'lines': desc['lines'],
                'font_size': desc['font_size'],
                'font_name': 'Helvetica-Bold',
                'line_height': desc['line_height'],
                'y_start': desc_y,
                'x': self.text_start_x
            },
            'dimensions': {
                'lines': dim['lines'],
                'font_size': dim['font_size'],
                'font_name': 'Helvetica-Bold',
                'line_height': dim['line_height'],
                'y_start': dim_y,
                'x': self.text_start_x
            } if dim else None,
            'product_id': {
                'lines': pid['lines'],
                'font_size': pid['font_size'],
                'font_name': 'Helvetica',
                'line_height': pid['line_height'],
                'y_start': id_y,
                'x': self.text_start_x
            }
        }
    
    def _calculate_layout_height(self, desc: Dict, dim: Dict, pid: Dict) -> float:
        """Helper to calculate total layout height."""
        total_height = 0
        
        # Calculate line height if not provided
        desc_line_height = desc.get('line_height', desc['font_size'] * 1.2)
        pid_line_height = pid.get('line_height', pid['font_size'] * 1.2)
        
        # Description height
        total_height += len(desc['lines']) * desc_line_height
        
        # Dimensions height and gap
        if dim and dim.get('lines'):
            dim_line_height = dim.get('line_height', dim['font_size'] * 1.2)
            total_height += desc_line_height * 0.3  # gap after description
            total_height += len(dim['lines']) * dim_line_height
            total_height += dim_line_height * 0.3  # gap after dimensions
        else:
            total_height += desc_line_height * 0.3  # gap before ID
        
        # Product ID height
        total_height += pid_line_height
        
        return total_height
    
    def _fallback_layout_algorithm(self, c: canvas.Canvas, description: str, dimensions: str, 
                                  product_id_text: str, text_width: float, text_height: float) -> Dict:
        """Fallback to the original layout algorithm when optimization fails."""
        # Simplified version that respects font priority
        has_dimensions = bool(dimensions and dimensions.strip())
        
        if has_dimensions:
            # Priority: dimensions > description > ID - but ensure it fits!
            dim_font_size = 5  # Conservative but prominent
            dim_lines = self._wrap_text_with_font(c, dimensions, text_width, dim_font_size, "Helvetica-Bold")
            dim_line_height = dim_font_size * 1.2
            dim_height = len(dim_lines) * dim_line_height
            
            desc_font_size = 4  # Smaller
            desc_lines = self._wrap_text_with_font(c, description, text_width, desc_font_size, "Helvetica-Bold")
            desc_line_height = desc_font_size * 1.2
            desc_height = len(desc_lines) * desc_line_height
            
            id_font_size = 4  # Smallest
            id_line_height = id_font_size * 1.2
            id_height = id_line_height
            
            gap_space = dim_line_height * 0.3 + desc_line_height * 0.3
            total_content_height = desc_height + dim_height + id_height + gap_space
            gap_after_desc = desc_line_height * 0.3
            gap_after_dim = dim_line_height * 0.3
        else:
            # Priority: description > ID (no dimensions) - conservative sizes
            desc_font_size = 4  # Conservative size that should fit
            desc_lines = self._wrap_text_with_font(c, description, text_width, desc_font_size, "Helvetica-Bold")
            desc_line_height = desc_font_size * 1.2
            desc_height = len(desc_lines) * desc_line_height
            
            id_font_size = 4  # Same size for simplicity
            id_line_height = id_font_size * 1.2
            id_height = id_line_height
            
            dim_font_size = 0
            dim_lines = []
            dim_line_height = 0
            dim_height = 0
            
            gap_space = desc_line_height * 0.3
            total_content_height = desc_height + id_height + gap_space
            gap_after_desc = desc_line_height * 0.3
            gap_after_dim = 0
        
        # Position text
        first_line_ascent = desc_font_size * 0.75
        available_height = self.page_height - (2 * self.margin)
        
        if total_content_height <= available_height - first_line_ascent:
            vertical_offset = (available_height - total_content_height - first_line_ascent) / 2
            y_start = self.page_height - self.margin - first_line_ascent - vertical_offset
        else:
            y_start = self.page_height - self.margin - first_line_ascent
        
        return {
            'description': {
                'lines': desc_lines,
                'font_size': desc_font_size,
                'font_name': 'Helvetica-Bold',
                'line_height': desc_line_height,
                'y_start': y_start,
                'x': self.text_start_x
            },
            'dimensions': {
                'lines': dim_lines,
                'font_size': dim_font_size,
                'font_name': 'Helvetica-Bold',
                'line_height': dim_line_height,
                'y_start': y_start - desc_height - gap_after_desc,
                'x': self.text_start_x
            } if dim_lines else None,
            'product_id': {
                'lines': [product_id_text],
                'font_size': id_font_size,
                'font_name': 'Helvetica',
                'line_height': id_line_height,
                'y_start': y_start - desc_height - gap_after_desc - dim_height - gap_after_dim,
                'x': self.text_start_x
            }
        }
    
    def _find_optimal_font_size(self, c: canvas.Canvas, text: str, max_width: float, 
                               max_height: float, font_name: str, min_size: int = 3, max_size: int = 12) -> int:
        """Find the largest font size that fits the text within the given constraints."""
        if not text:
            return min_size
            
        for font_size in range(max_size, min_size - 1, -1):
            lines = self._wrap_text_with_font(c, text, max_width, font_size, font_name)
            line_height = font_size * 1.2
            total_height = len(lines) * line_height
            
            if total_height <= max_height:
                return font_size
                
        return min_size
    
    def _wrap_text_with_font(self, c: canvas.Canvas, text: str, max_width: float, 
                           font_size: int, font_name: str) -> List[str]:
        """Wrap text to fit within max width using specific font."""
        if not text:
            return []
            
        words = text.split()
        lines = []
        current_line = []
        
        # Build lines by adding words until width limit is reached
        for word in words:
            test_line = ' '.join(current_line + [word])
            # Use ReportLab's stringWidth to measure actual rendered width
            if c.stringWidth(test_line, font_name, font_size) <= max_width:
                current_line.append(word)  # Word fits on current line
            else:
                if current_line:
                    lines.append(' '.join(current_line))  # Save current line
                    current_line = [word]  # Start new line with this word
                else:
                    # Single word is too long for the width - force it anyway
                    lines.append(word)
        
        # Don't forget the last line
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def _render_text_layout(self, c: canvas.Canvas, layout: Dict):
        """Render the calculated text layout."""
        # Render description
        if layout['description']:
            desc = layout['description']
            c.setFont(desc['font_name'], desc['font_size'])
            y = desc['y_start']
            for line in desc['lines']:
                c.drawString(desc['x'], y, line)
                y -= desc['line_height']
        
        # Render dimensions
        if layout['dimensions']:
            dim = layout['dimensions']
            c.setFont(dim['font_name'], dim['font_size'])
            y = dim['y_start']
            for line in dim['lines']:
                c.drawString(dim['x'], y, line)
                y -= dim['line_height']
        
        # Render product ID
        if layout['product_id']:
            pid = layout['product_id']
            c.setFont(pid['font_name'], pid['font_size'])
            y = pid['y_start']
            for line in pid['lines']:
                c.drawString(pid['x'], y, line)
                y -= pid['line_height']
    
    def _wrap_text(self, c: canvas.Canvas, text: str, max_width: float, font_size: int) -> List[str]:
        """Wrap text to fit within max width."""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            if c.stringWidth(test_line, "Helvetica", font_size) <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def _get_product_description(self, product_info: Dict[str, Any]) -> str:
        """Extract product description from API data."""
        # Combine FamilyDescription and DetailDescription from actual API response
        family_desc = product_info.get('FamilyDescription') or ''
        detail_desc = product_info.get('DetailDescription') or ''
        
        # Handle None values by converting to empty string
        if family_desc is None:
            family_desc = ''
        if detail_desc is None:
            detail_desc = ''
        
        if family_desc and detail_desc:
            return f"{family_desc} - {detail_desc}"
        elif family_desc:
            return family_desc
        elif detail_desc:
            return detail_desc
        else:
            return "McMaster-Carr Part"
    
    def _get_dimensions_text(self, product_info: Dict[str, Any]) -> str:
        """Extract dimensional information from API data."""
        dimensions = []
        
        # Extract from Specifications array in McMaster API response
        # This contains structured product attribute data
        specifications = product_info.get('Specifications', [])
        
        # Handle case where specifications is None (malformed API response)
        if specifications is None:
            return ""
        
        # Priority dimensional attributes to display on label
        # Order matters - most important dimensions first
        dimension_attrs = ['Length', 'Thread Size', 'Thread Pitch', 'Head Diameter', 
                          'Width', 'Height', 'Diameter', 'Size']
        
        # Search through all specifications for dimensional data
        for spec in specifications:
            attr_name = spec.get('Attribute', '')
            if attr_name in dimension_attrs and spec.get('Values'):
                # Take first value if multiple options exist
                value = spec['Values'][0]
                
                # Create shortened labels to fit on small label
                # Some attributes (Thread Size/Pitch) don't need prefixes
                if attr_name == 'Thread Size':
                    dimensions.append(value)  # e.g. "M8 x 1.25mm"
                elif attr_name == 'Thread Pitch':
                    dimensions.append(value)  # e.g. "1.25mm pitch"
                elif attr_name == 'Length':
                    dimensions.append(f"L: {value}")  # e.g. "L: 50mm"
                elif attr_name == 'Width':
                    dimensions.append(f"W: {value}")   # e.g. "W: 10mm"
                elif attr_name == 'Height':
                    dimensions.append(f"H: {value}")   # e.g. "H: 5mm"
                elif attr_name == 'Diameter':
                    dimensions.append(f"D: {value}")   # e.g. "D: 12mm"
                elif attr_name == 'Head Diameter':
                    dimensions.append(f"HD: {value}")  # e.g. "HD: 15mm"
                elif attr_name == 'Size':
                    dimensions.append(f"Size: {value}") # e.g. "Size: #10"
        
        # Limit to 3 most important dimensions that fit on small label
        # Use pipe separator for clean appearance
        return " | ".join(dimensions[:3]) if dimensions else ""