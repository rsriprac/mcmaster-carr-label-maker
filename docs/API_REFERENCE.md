# API Reference

## Command Line Interface

### Basic Usage
```bash
python -m src.main [PRODUCT_IDS]... [OPTIONS]
```

### Arguments

- `PRODUCT_IDS`: One or more McMaster-Carr product IDs (e.g., 91290A115)

### Options

#### Input Options
- `-f, --file PATH`: Read product IDs from a file (one per line)

#### Output Options
- `-o, --output FILENAME`: Output filename (default: `labels-YYYYMMDD-HHMMSS.{ext}`)
- `-w, --width SIZE`: Label width with units (e.g., "1.5in", "38mm", "3.8cm") - defaults to inches if no unit
- `-h, --height SIZE`: Label height with units (e.g., "0.5in", "13mm", "1.3cm") - defaults to inches if no unit
- `-r, --resolution DPI`: DPI resolution for image output (default: 300)

#### Other Options
- `-v, --verbose`: Enable verbose logging
- `--help`: Show help message
- `--help-with-defaults`: Show help with current default values
- `--clear-cache`: Clear all cached credentials from system keychain

### Examples

```bash
# Basic usage
python -m src.main 91290A115

# Multiple products
python -m src.main 91290A115 91290A116 91290A117

# Custom dimensions
python -m src.main 91290A115 -w 2in -h 1in

# High-resolution PNG
python -m src.main 91290A115 -o labels.png -r 600

# Read from file
python -m src.main -f product_list.txt
```

## Supported Formats

### Output Formats
- **PDF** (.pdf) - Vector format, supports multiple pages
- **PNG** (.png) - Lossless raster format
- **JPEG** (.jpg, .jpeg) - Compressed raster format
- **BMP** (.bmp) - Uncompressed raster format
- **TIFF** (.tiff, .tif) - Supports multiple pages
- **GIF** (.gif) - Limited color raster format
- **WebP** (.webp) - Modern compressed format

### Unit Support
- **Imperial**: inches (in), feet (ft)
- **Metric**: millimeters (mm), centimeters (cm), meters (m)
- **Typography**: points (pt), pixels (px)

### DPI Ranges
- Minimum: 72 DPI
- Maximum: 2400 DPI
- Default: 300 DPI (standard laser printer resolution)

## Python API

### LabelGenerator Class

```python
from src.label_generator import LabelGenerator
from src.output_formats import OutputFormat

# Create generator with custom dimensions
generator = LabelGenerator(width_inches=2.0, height_inches=1.0)

# Generate labels
products_data = {
    "91290A115": {
        "info": {
            "short_description": "Hex Nut",
            "dimensional_description": "1/4-20 Thread Size",
            "mcmaster_id": "91290A115"
        },
        "image_path": "/path/to/cached/image.png",  # Optional
        "cad_path": "/path/to/cached/cad.step"      # Optional
    }
}

# Generate PDF
generator.generate_labels(products_data, "output.pdf", OutputFormat.PDF)

# Generate PNG at 600 DPI
generator.generate_labels(products_data, "output.png", OutputFormat.PNG, dpi=600)
```

### Dimension Utilities

```python
from src.dimensions import parse_dimension, validate_dimensions

# Parse dimension with units
width_inches = parse_dimension("50mm")  # Returns 1.9685...
width_inches = parse_dimension("2")     # Returns 2.0 (defaults to inches)

# Validate dimensions
validate_dimensions(width_inches, height_inches)  # Raises ValueError if invalid
```