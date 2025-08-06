import os
from pathlib import Path
from typing import Dict, Any, Optional

# Base paths
BASE_DIR = Path(__file__).parent.parent

# API Configuration - McMaster-Carr API endpoints
API_BASE_URL = "https://api.mcmaster.com"
API_ENDPOINTS = {
    "login": "/v1/login",                          # Authenticate and get bearer token
    "add_product": "/v1/products",                 # Subscribe to product for data access
    "product_info": "/v1/products/{product_id}",   # Get detailed product information
    "cad_download": "/v1/cad/{product_id}",        # Download CAD files (STEP, PDF, etc.)
    "image_download": "/v1/images/{product_id}"     # Download product images (PNG, JPG)
}

# Default configuration values (can be overridden by environment variables)
DEFAULT_CONFIG = {
    # Certificate Configuration
    "CERT_FILENAME": "cert.pfx",  # Generic certificate filename
    "CA_FILENAME": "ca.pem",
    
    # API Configuration
    "API_RATE_LIMIT_SECONDS": 0.5,
    "SSL_VERIFY": "false",  # String to match env var format
    
    # Label Configuration - physical dimensions for printing
    "LABEL_WIDTH_INCHES": 1.5,
    "LABEL_HEIGHT_INCHES": 0.5,
    "LABEL_IMAGE_WIDTH_RATIO": 0.25,  # Image takes 25% of label width
    
    # Directory Configuration
    "OUTPUT_DIR": "output",
    "CACHE_DIR": "cache",
    
    # Cache Configuration
    "PLACEHOLDER_EXPIRY_DAYS": 14,  # Days before placeholders expire (default: 2 weeks)
    
    # Non-sensitive user info (username is OK, passwords are NOT)
    "API_USERNAME": "",  # Can be stored, but passwords must not be
}

# Configuration with environment variable override
class Config:
    """Configuration manager with environment variable precedence."""
    
    def __init__(self):
        self._config = DEFAULT_CONFIG.copy()
        self._sources = {}  # Track where each config value came from
        self._load_env_overrides()
    
    def _load_env_overrides(self):
        """Load environment variable overrides."""
        # Map of config keys to environment variable names
        env_mappings = {
            "CERT_FILENAME": "MCMASTER_CERT_FILENAME",
            "CA_FILENAME": "MCMASTER_CA_FILENAME",
            "API_RATE_LIMIT_SECONDS": "MCMASTER_API_RATE_LIMIT",
            "SSL_VERIFY": "MCMASTER_SSL_VERIFY",
            "LABEL_WIDTH_INCHES": "MCMASTER_LABEL_WIDTH",
            "LABEL_HEIGHT_INCHES": "MCMASTER_LABEL_HEIGHT",
            "LABEL_IMAGE_WIDTH_RATIO": "MCMASTER_IMAGE_RATIO",
            "OUTPUT_DIR": "MCMASTER_OUTPUT_DIR",
            "CACHE_DIR": "MCMASTER_CACHE_DIR",
            "PLACEHOLDER_EXPIRY_DAYS": "MCMASTER_PLACEHOLDER_EXPIRY_DAYS",
            "API_USERNAME": "MCMASTER_API_USERNAME",
        }
        
        for config_key, env_var in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                # Convert numeric values
                if config_key in ["API_RATE_LIMIT_SECONDS", "LABEL_WIDTH_INCHES", 
                                 "LABEL_HEIGHT_INCHES", "LABEL_IMAGE_WIDTH_RATIO"]:
                    try:
                        self._config[config_key] = float(env_value)
                        self._sources[config_key] = f"environment variable {env_var}"
                    except ValueError:
                        # Keep default if conversion fails
                        self._sources[config_key] = "default (env var conversion failed)"
                elif config_key == "PLACEHOLDER_EXPIRY_DAYS":
                    try:
                        self._config[config_key] = int(env_value)
                        self._sources[config_key] = f"environment variable {env_var}"
                    except ValueError:
                        # Keep default if conversion fails
                        self._sources[config_key] = "default (env var conversion failed)"
                else:
                    self._config[config_key] = env_value
                    self._sources[config_key] = f"environment variable {env_var}"
            else:
                self._sources[config_key] = "config.py default"
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._config.get(key, default)
    
    def get_source(self, key: str) -> str:
        """Get the source of a configuration value."""
        return self._sources.get(key, "unknown")
    
    def get_all_with_sources(self) -> Dict[str, tuple]:
        """Get all configuration values with their sources."""
        return {key: (value, self._sources.get(key, "unknown")) 
                for key, value in self._config.items()}
    
    def print_config_sources(self, verbose: bool = False):
        """Print configuration values and their sources."""
        if not verbose:
            return
            
        print("\n=== Configuration Settings ===")
        print("(Environment variables take precedence over config.py defaults)")
        print("")
        
        # Group by category
        categories = {
            "Paths": ["CERT_FILENAME", "CA_FILENAME", "OUTPUT_DIR", "CACHE_DIR"],
            "API Settings": ["API_RATE_LIMIT_SECONDS", "SSL_VERIFY", "API_USERNAME"],
            "Label Dimensions": ["LABEL_WIDTH_INCHES", "LABEL_HEIGHT_INCHES", "LABEL_IMAGE_WIDTH_RATIO"],
        }
        
        for category, keys in categories.items():
            print(f"{category}:")
            for key in keys:
                value = self._config.get(key, "Not set")
                source = self._sources.get(key, "unknown")
                
                # Mask username if needed
                display_value = value
                if key == "API_USERNAME" and value and len(str(value)) > 0:
                    # Show partial username
                    username = str(value)
                    if '@' in username:
                        parts = username.split('@')
                        display_value = parts[0][:3] + '*' * (len(parts[0]) - 3) + '@' + parts[1]
                    else:
                        display_value = username[:3] + '*' * (len(username) - 3)
                
                print(f"  {key}: {display_value} (from {source})")
            print()

# Create global config instance
config = Config()

# Path configurations using the config values
CERT_PATH = BASE_DIR / "cert" / config.get("CERT_FILENAME")
CA_BUNDLE_PATH = BASE_DIR / "ca" / config.get("CA_FILENAME")
OUTPUT_DIR = BASE_DIR / config.get("OUTPUT_DIR")
CACHE_DIR = BASE_DIR / config.get("CACHE_DIR")

# Create directories if they don't exist
OUTPUT_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

# Export configuration values for backward compatibility
API_RATE_LIMIT_SECONDS = config.get("API_RATE_LIMIT_SECONDS")
LABEL_WIDTH_INCHES = config.get("LABEL_WIDTH_INCHES")
LABEL_HEIGHT_INCHES = config.get("LABEL_HEIGHT_INCHES")
LABEL_IMAGE_WIDTH_RATIO = config.get("LABEL_IMAGE_WIDTH_RATIO")