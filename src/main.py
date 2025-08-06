#!/usr/bin/env python3
import click
import logging
import sys
import os
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from .api_client import McMasterAPI
from .label_generator import LabelGenerator
from .dimensions import (
    parse_dimension, get_cached_dimensions, cache_dimensions,
    validate_dimensions, format_dimension_for_display
)
from .credentials import get_credentials
from .output_formats import (
    detect_format_from_filename, get_default_dpi, validate_dpi,
    is_raster_format
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_default_output_filename():
    """Generate default output filename with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"labels-{timestamp}.pdf"


def format_help_with_defaults(ctx, param, value):
    """Show help with current defaults including redacted credentials."""
    if not value or ctx.resilient_parsing:
        return
    
    # Get current defaults
    cached_width, cached_height = get_cached_dimensions()
    default_width = cached_width if cached_width else 1.5
    default_height = cached_height if cached_height else 0.5
    
    # Check for cached credentials
    username = os.getenv('MCMASTER_API_USERNAME', '')
    password = os.getenv('MCMASTER_API_PASSWORD', '')
    cert_password = os.getenv('MCMASTER_CERT_PASSWORD', '')
    
    # Redact credentials
    redacted_username = '*' * len(username) if username else 'Not set'
    redacted_password = '*' * len(password) if password else 'Not set'
    redacted_cert_password = '*' * len(cert_password) if cert_password else 'Not set'
    
    click.echo("McMaster-Carr Label Generator")
    click.echo("\nCurrent defaults:")
    click.echo(f"  Label width: {format_dimension_for_display(default_width)}")
    click.echo(f"  Label height: {format_dimension_for_display(default_height)}")
    click.echo(f"  API Username: {redacted_username}")
    click.echo(f"  API Password: {redacted_password}")
    click.echo(f"  Certificate Password: {redacted_cert_password}")
    click.echo("")
    
    click.echo(ctx.get_help())
    ctx.exit()


@click.command()
@click.argument('product_ids', nargs=-1, required=False)
@click.option(
    '--file', '-f',
    type=click.Path(exists=True, path_type=Path),
    help='Read product IDs from a file (one ID per line)'
)
@click.option(
    '--output', '-o',
    default=None,
    help='Output PDF filename (default: labels-YYYYMMDD-HHMMSS.pdf)'
)
@click.option(
    '--width', '-w',
    default=None,
    help='Label width with units (e.g., "1.5in", "38mm", "3.8cm") - defaults to inches if no unit'
)
@click.option(
    '--height', '-h',
    default=None,
    help='Label height with units (e.g., "0.5in", "13mm", "1.3cm") - defaults to inches if no unit'
)
@click.option(
    '--resolution', '-r',
    type=int,
    default=None,
    help='DPI resolution for image output (default: 300 DPI)'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Enable verbose logging'
)
@click.option(
    '--help-with-defaults',
    is_flag=True,
    callback=format_help_with_defaults,
    expose_value=False,
    is_eager=True,
    help='Show help with current default values'
)
@click.option(
    '--clear-cache',
    is_flag=True,
    help='Clear all cached credentials from system keychain'
)
@click.option(
    '--cache-stats',
    is_flag=True,
    help='Show cache statistics including placeholders'
)
@click.option(
    '--sort-similar',
    is_flag=True,
    help='Sort labels by visual similarity to group similar parts together'
)
@click.option(
    '--similarity-method',
    type=click.Choice(['hierarchical', 'spectral', 'greedy']),
    default='hierarchical',
    help='Method for similarity sorting (default: hierarchical)'
)
@click.option(
    '--sort-text',
    is_flag=True,
    help='Sort labels alphabetically by product description'
)
@click.option(
    '--text-sort-field',
    type=click.Choice(['description', 'product_id', 'family', 'detail']),
    default='description',
    help='Field to use for text sorting (default: description)'
)
@click.option(
    '--sort-fuzzy',
    is_flag=True,
    help='Smart sorting: group similar items by text, then sort by dimensions within groups'
)
@click.option(
    '--fuzzy-threshold',
    type=float,
    default=0.3,
    help='Similarity threshold for fuzzy grouping (0-1, default: 0.3)'
)
def main(product_ids: tuple, file: Path, output: Optional[str], width: Optional[str], height: Optional[str], resolution: Optional[int], verbose: bool, clear_cache: bool, cache_stats: bool, sort_similar: bool, similarity_method: str, sort_text: bool, text_sort_field: str, sort_fuzzy: bool, fuzzy_threshold: float):
    """Generate labels for McMaster-Carr products.
    
    PRODUCT_IDS: One or more McMaster-Carr product IDs to generate labels for.
    
    Examples:
        python -m src.main 91290A115 91290A116 91290A117
        python -m src.main --file product_ids.txt
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Handle clear cache option
    if clear_cache:
        from .keychain import clear_all_credentials
        clear_all_credentials()
        sys.exit(0)
    
    # Handle cache stats option
    if cache_stats:
        from .cache_utils import get_cache_statistics
        from .config import CACHE_DIR
        
        stats = get_cache_statistics(CACHE_DIR)
        click.echo("\nCache Statistics:")
        click.echo("-" * 40)
        click.echo(f"Total files: {stats['total_files']}")
        click.echo(f"Product info: {stats['product_info']}")
        click.echo(f"Images: {stats['images']}")
        click.echo(f"CAD files: {stats['cad_files']}")
        click.echo(f"Placeholders: {stats['placeholders']}")
        if stats['expired_placeholders'] > 0:
            click.echo(f"  - Expired: {stats['expired_placeholders']} (will be cleaned on next run)")
        click.echo(f"Total size: {stats['total_size_mb']} MB")
        sys.exit(0)
    
    # Show configuration sources in verbose mode
    from .config import config
    config.print_config_sources(verbose)
    
    # Validate sorting options - only one sorting method allowed
    sort_options = [sort_similar, sort_text, sort_fuzzy]
    if sum(sort_options) > 1:
        click.echo("Error: Can only use one sorting option at a time (--sort-similar, --sort-text, or --sort-fuzzy)", err=True)
        sys.exit(1)
    
    # Handle input sources - either command line args or file
    # User can provide product IDs directly or via a text file (one per line)
    if file and product_ids:
        click.echo("Error: Cannot specify both product IDs and --file option", err=True)
        sys.exit(1)
    
    if file:
        # Read product IDs from file - supports comments and blank lines
        try:
            with open(file, 'r') as f:
                file_product_ids = []
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    # Skip empty lines and comments (lines starting with #)
                    if line and not line.startswith('#'):
                        file_product_ids.append(line)
                product_ids = file_product_ids
                logger.info(f"Read {len(product_ids)} product IDs from {file}")
        except Exception as e:
            click.echo(f"Error reading file {file}: {e}", err=True)
            sys.exit(1)
    else:
        # Convert tuple to list for easier handling
        product_ids = list(product_ids)
    
    # Validate we have product IDs
    if not product_ids:
        click.echo("Error: No product IDs provided. Use either command line arguments or --file option.", err=True)
        click.echo("Use --help for usage information.", err=True)
        click.echo("\nUsage: python -m src.main [PRODUCT_IDS]... [OPTIONS]", err=True)
        click.echo("\nTry: python -m src.main --help", err=True)
        sys.exit(1)
    
    # Handle dimensions
    label_width = None
    label_height = None
    
    # Check for provided dimensions
    if width and height:
        try:
            label_width = parse_dimension(width)
            label_height = parse_dimension(height)
            validate_dimensions(label_width, label_height)
            # Cache for future use
            cache_dimensions(label_width, label_height)
            logger.info(f"Using provided dimensions: {format_dimension_for_display(label_width)} x {format_dimension_for_display(label_height)}")
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    elif width or height:
        click.echo("Error: Both --width and --height must be specified together", err=True)
        sys.exit(1)
    else:
        # Check for cached dimensions
        cached_width, cached_height = get_cached_dimensions()
        if cached_width and cached_height:
            label_width = cached_width
            label_height = cached_height
            logger.info(f"Using cached dimensions: {format_dimension_for_display(label_width)} x {format_dimension_for_display(label_height)}")
        else:
            # Use defaults
            label_width = 1.5
            label_height = 0.5
            logger.info(f"Using default dimensions: {format_dimension_for_display(label_width)} x {format_dimension_for_display(label_height)}")
    
    # Handle output filename
    if not output:
        output = get_default_output_filename()
        logger.info(f"Using auto-generated output filename: {output}")
    
    # Detect output format from filename
    try:
        output_format = detect_format_from_filename(output)
        logger.info(f"Output format: {output_format.value}")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    
    # Handle DPI for raster formats
    if is_raster_format(output_format):
        if resolution is None:
            resolution = get_default_dpi()
            logger.info(f"Using default DPI: {resolution}")
        else:
            try:
                validate_dpi(resolution)
                logger.info(f"Using specified DPI: {resolution}")
            except ValueError as e:
                click.echo(f"Error: {e}", err=True)
                sys.exit(1)
    else:
        # PDF doesn't use DPI parameter
        if resolution is not None:
            logger.warning("DPI parameter ignored for PDF output")
        resolution = None
    
    # Get credentials - will prompt if not in environment variables
    from .credentials import get_credentials
    from .config import CERT_PATH
    
    click.echo("Checking credentials...")
    credentials = get_credentials()
    API_USERNAME = credentials['API_USERNAME']
    API_PASSWORD = credentials['API_PASSWORD']
    CERT_PASSWORD = credentials['CERT_PASSWORD']
    
    # Validate that client certificate file exists
    # This .pfx file is required for McMaster API authentication
    if not CERT_PATH.exists():
        click.echo(f"Error: Certificate file not found: {CERT_PATH}", err=True)
        click.echo("Please ensure your certificate file is in the cert/ directory.", err=True)
        sys.exit(1)
    
    click.echo(f"McMaster-Carr Label Generator")
    click.echo(f"Processing {len(product_ids)} products...")
    
    # Initialize API client with credentials
    api = McMasterAPI(API_USERNAME, API_PASSWORD, CERT_PASSWORD)
    
    # Clean expired placeholders before processing
    expired_cleaned = api.clean_cache_placeholders()
    if expired_cleaned > 0 and verbose:
        logger.info(f"Cleaned {expired_cleaned} expired placeholder files")
    
    # Login
    click.echo("Authenticating with McMaster-Carr API...")
    if not api.login():
        click.echo("Failed to authenticate. Please check your credentials.", err=True)
        sys.exit(1)
    
    # Process products - fetch data from API or use cached data
    # Shows progress bar for user feedback during potentially slow API calls
    click.echo("Fetching product data...")
    with click.progressbar(product_ids, label='Processing products') as bar:
        products_data = {}
        for product_id in bar:
            # Process single product - this handles caching automatically
            # API client will use cache when available, make API calls when needed
            result = api.process_products([product_id])
            if product_id in result:
                products_data[product_id] = result[product_id]
            else:
                logger.warning(f"Failed to process product: {product_id}")
    
    if not products_data:
        click.echo("No products were successfully processed.", err=True)
        sys.exit(1)
    
    # Generate labels
    click.echo(f"Generating {output_format.value.upper()} labels...")
    if sort_similar:
        click.echo(f"  - Sorting by visual similarity ({similarity_method} method)")
    elif sort_text:
        click.echo(f"  - Sorting alphabetically by {text_sort_field}")
    elif sort_fuzzy:
        click.echo(f"  - Smart sorting: grouping similar items, then sorting by dimensions (threshold: {fuzzy_threshold})")
    generator = LabelGenerator(width_inches=label_width, height_inches=label_height)
    output_path = generator.generate_labels(
        products_data, 
        output, 
        output_format=output_format,
        dpi=resolution,
        sort_by_similarity=sort_similar,
        similarity_method=similarity_method,
        sort_by_text=sort_text,
        text_sort_field=text_sort_field,
        sort_by_fuzzy=sort_fuzzy,
        fuzzy_threshold=fuzzy_threshold
    )
    
    click.echo(f"✓ Labels generated successfully: {output_path}")
    click.echo(f"  - Total products: {len(products_data)}")
    click.echo(f"  - Label size: {format_dimension_for_display(label_width)} x {format_dimension_for_display(label_height)}")
    if resolution:
        click.echo(f"  - Resolution: {resolution} DPI")
    
    # Logout when done
    api.logout()
    

if __name__ == '__main__':
    main()