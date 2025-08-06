# Output Directory

This directory is the default location for generated label files.

## Purpose

The output directory contains:
- Generated PDF label files (`labels-*.pdf`)
- Generated image files (PNG, JPG, TIFF, etc.)
- Any other output files from the label generation process

## File Naming Convention

Default output files follow this naming pattern:
- `labels-YYYYMMDD-HHMMSS.pdf` - Timestamped PDF files
- `labels-YYYYMMDD-HHMMSS.png` - Image format outputs
- Custom names when specified with the `--output` option

## Important Notes

- **All output files are automatically excluded from version control**
- Output files can be safely deleted at any time
- Files are overwritten if the same filename is used
- Consider backing up important generated labels

## Directory Management

To clean up old output files:
```bash
# Remove all PDF files older than 30 days
find output -name "*.pdf" -mtime +30 -delete

# Remove all output files
rm -f output/*
```

## Usage Examples

The application uses this directory by default:
```bash
# Generate labels (output to this directory)
python -m src.main 91290A115 91290A116

# Specify custom output location
python -m src.main 91290A115 --output output/custom_labels.pdf
```

## Backup Recommendation

If you need to keep generated labels long-term:
1. Move them to a dedicated backup location
2. Consider using version control for important label templates
3. Keep a record of the product IDs used for generation