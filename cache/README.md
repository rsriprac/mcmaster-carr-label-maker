# Cache Directory

This directory stores cached data from the McMaster-Carr API to improve performance and reduce redundant API calls.

## Purpose

The cache directory contains:
- Product information JSON files (`product_*.json`)
- Product images (`image_*.png`)
- CAD files (`cad_*.step`, `cad_*.iges`, etc.)
- Other temporary data files

## Cache Structure

```
cache/
├── product_<PART_NUMBER>.json    # Product metadata and specifications
├── image_<PART_NUMBER>.png       # Product images
├── cad_<PART_NUMBER>.<ext>       # CAD files (STEP, IGES, etc.)
└── README.md                      # This file
```

## Important Notes

- **All cache files are automatically excluded from version control**
- Cache files can be safely deleted at any time
- The application will recreate cache files as needed
- Cached data helps reduce API calls and speeds up repeated operations

## Cache Management

To clear the cache:
```bash
# Remove all cache files (safe operation)
rm -f cache/*.json cache/*.png cache/*.step cache/*.iges

# Or use the application's clear cache option
python -m src.main --clear-cache
```

## Performance Benefits

Caching provides:
- Faster label generation for previously processed products
- Reduced API calls (important for rate limiting)
- Offline access to previously fetched product data
- Consistent data across multiple label generation runs

## Cache Lifetime

Cache files do not expire automatically. They remain valid until:
- Manually deleted
- Application cache is cleared
- Product data is explicitly refreshed

For the most up-to-date product information, periodically clear the cache or use the refresh options in the application.