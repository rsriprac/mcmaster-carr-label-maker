import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from requests import Session
from requests_pkcs12 import Pkcs12Adapter
import time
import ssl

from .config import (
    API_BASE_URL, API_ENDPOINTS, CERT_PATH, CACHE_DIR, CA_BUNDLE_PATH
)
from .cache_utils import (
    create_placeholder, check_for_placeholder,
    clean_expired_placeholders
)

logger = logging.getLogger(__name__)


class McMasterAPI:
    """Client for interacting with McMaster-Carr API using certificate authentication."""
    
    def __init__(self, api_username: str, api_password: str, cert_password: str):
        self.api_username = api_username
        self.api_password = api_password
        self.cert_password = cert_password
        self.session = None
        self.is_authenticated = False
        self.auth_token = None
        # Cache statistics
        self.cache_stats = {
            'product_info_cache_hits': 0,
            'product_info_api_calls': 0,
            'image_cache_hits': 0,
            'image_api_downloads': 0,
            'cad_cache_hits': 0,
            'cad_api_downloads': 0,
            'subscription_cache_skips': 0,
            'subscription_api_calls': 0
        }
        self._setup_session()
    
    def _setup_session(self):
        """Initialize session with certificate authentication."""
        self.session = Session()
        
        # The McMaster-Carr API requires client certificate authentication
        # The server will verify our client certificate, so we need to present it
        # However, we may need to disable server certificate verification if
        # their server certificate chain isn't in standard CA bundles
        
        # For McMaster-Carr API, we'll use a pragmatic approach:
        # 1. Always present our client certificate (required for authentication)
        # 2. Try to verify server certificate if possible, but allow disabling
        
        # Check if we should verify server certificates
        # Use config system which handles environment variable precedence
        from .config import config
        
        if config.get('SSL_VERIFY', 'false').lower() == 'true':
            # SSL verification enabled - determine which CA bundle to use
            # Priority order:
            # 1. Custom CA bundle file if it exists
            # 2. System CA bundle (most portable option)
            # 3. Python's default verification
            
            if CA_BUNDLE_PATH.exists():
                # Use custom CA bundle for private/internal CAs
                self.verify = str(CA_BUNDLE_PATH)
                logger.info(f"Using custom CA bundle: {CA_BUNDLE_PATH}")
            else:
                # Check for system-specified CA bundle via environment variables
                # This respects standard SSL_CERT_FILE and REQUESTS_CA_BUNDLE
                import os
                system_ca_file = (
                    os.environ.get('REQUESTS_CA_BUNDLE') or 
                    os.environ.get('SSL_CERT_FILE') or
                    os.environ.get('CURL_CA_BUNDLE')
                )
                
                if system_ca_file and os.path.exists(system_ca_file):
                    # Use system-specified CA bundle
                    self.verify = system_ca_file
                    logger.info(f"Using system CA bundle from environment: {system_ca_file}")
                else:
                    # Use system CA certificates for maximum portability
                    # Setting verify=True uses the CA bundle from certifi package,
                    # which is automatically updated and works across platforms
                    self.verify = True
                    
                    # Log which CA bundle is being used
                    try:
                        import certifi
                        ca_bundle = certifi.where()
                        logger.info(f"Using certifi CA bundle: {ca_bundle}")
                    except ImportError:
                        # Fall back to requests/urllib default
                        logger.info("Using system default CA certificates")
        else:
            # Disable SSL verification for server certificate
            # This is often needed for private APIs with self-signed or internal CAs
            self.verify = False
            logger.info("SSL server certificate verification disabled")
            
            # Disable SSL warnings when verification is off
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Set default verify for the session
        self.session.verify = self.verify
        
        # Create adapter with client certificate - this is always required
        # PKCS12 (.pfx) files contain both private key and certificate for client auth
        pkcs12_adapter = Pkcs12Adapter(
            pkcs12_filename=str(CERT_PATH), 
            pkcs12_password=self.cert_password
        )
        # Mount the adapter to specific URLs - this tells requests to use our certificate
        # for authentication when connecting to these endpoints
        self.session.mount(API_BASE_URL, pkcs12_adapter)
        self.session.mount("https://", pkcs12_adapter)  # Mount for all HTTPS
        
    def login(self) -> bool:
        """Authenticate with McMaster-Carr API and obtain AuthToken."""
        try:
            login_data = {
                "UserName": self.api_username,
                "Password": self.api_password
            }
            
            response = self.session.post(
                f"{API_BASE_URL}{API_ENDPOINTS['login']}",
                json=login_data,
                timeout=30,
                verify=self.verify
            )
            
            if response.status_code == 200:
                response_data = response.json()
                self.auth_token = response_data.get('AuthToken')
                if self.auth_token:
                    self.is_authenticated = True
                    # Set authorization header for all subsequent requests
                    # Bearer token auth - server will validate this token for each API call
                    self.session.headers.update({
                        'Authorization': f'Bearer {self.auth_token}'
                    })
                    logger.info("Successfully authenticated with McMaster-Carr API")
                    return True
                else:
                    logger.error("No AuthToken received in login response")
                    return False
            else:
                logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return False
    
    def logout(self) -> bool:
        """Logout from McMaster-Carr API."""
        if not self.is_authenticated or not self.auth_token:
            logger.warning("Not authenticated, nothing to logout")
            return True
            
        try:
            response = self.session.post(
                f"{API_BASE_URL}/v1/logout",
                timeout=30,
                verify=self.verify
            )
            
            if response.status_code in (200, 204):  # 204 No Content is also valid for logout
                self.is_authenticated = False
                self.auth_token = None
                self.session.headers.pop('Authorization', None)
                logger.info("Successfully logged out from McMaster-Carr API")
                return True
            else:
                logger.error(f"Logout failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return False
    
    def add_product_subscription(self, product_id: str) -> bool:
        """Add a product to the subscription list."""
        if not self.is_authenticated or not self.auth_token:
            raise RuntimeError("Not authenticated. Please login first.")
            
        try:
            self.cache_stats['subscription_api_calls'] += 1
            
            # According to API docs, PUT request with product IDs in body
            # McMaster API expects product URLs rather than bare product IDs
            response = self.session.put(
                f"{API_BASE_URL}{API_ENDPOINTS['add_product']}",
                json={"URL": f"https://mcmaster.com/{product_id}"},  # Convert ID to full McMaster URL
                timeout=30,
                verify=self.verify
            )
            
            if response.status_code == 200 or response.status_code == 201:
                logger.info(f"Successfully subscribed to product: {response.status_code} - {product_id}")
                return True
            else:
                logger.error(f"Failed to subscribe to product {product_id}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error subscribing to product {product_id}: {str(e)}")
            return False
    
    def get_product_info(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve product information."""
        if not self.is_authenticated or not self.auth_token:
            raise RuntimeError("Not authenticated. Please login first.")
            
        # Check cache first - avoid API call if we already have the data
        cache_file = CACHE_DIR / f"product_{product_id}.json"
        if cache_file.exists():
            self.cache_stats['product_info_cache_hits'] += 1
            logger.info(f"Using cached product info for {product_id}")
            # Load and return cached JSON data directly
            with open(cache_file, 'r') as f:
                return json.load(f)
        
        try:
            self.cache_stats['product_info_api_calls'] += 1
            logger.info(f"Product info not in cache for {product_id}, calling API...")
            
            url = API_BASE_URL + API_ENDPOINTS['product_info'].format(product_id=product_id)
            response = self.session.get(url, timeout=30, verify=self.verify)
            
            if response.status_code == 200:
                product_data = response.json()
                
                # Cache the response
                with open(cache_file, 'w') as f:
                    json.dump(product_data, f, indent=2)
                
                logger.info(f"Retrieved and cached product info for: {product_id}")
                return product_data
            else:
                logger.error(f"Failed to get product info for {product_id}: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting product info for {product_id}: {str(e)}")
            return None
    
    def download_cad_file(self, product_id: str, output_path: Optional[Path] = None) -> Optional[Path]:
        """Download CAD file for a product, checking cache and placeholders first."""
        if not self.is_authenticated or not self.auth_token:
            raise RuntimeError("Not authenticated. Please login first.")
            
        try:
            # First check if we have a valid placeholder indicating no CAD available
            if check_for_placeholder(CACHE_DIR, 'cad', product_id):
                logger.info(f"Valid placeholder found - no CAD available for {product_id}")
                return None
            
            # Check cache for actual CAD files
            common_extensions = ['.step', '.pdf', '.igs', '.dxf', '.dwg', '.stp']
            for ext in common_extensions:
                cached_path = CACHE_DIR / f"cad_{product_id}{ext}"
                if cached_path.exists():
                    self.cache_stats['cad_cache_hits'] += 1
                    logger.info(f"Using cached CAD file for {product_id}: {cached_path}")
                    return cached_path if not output_path else cached_path
            
            # Not in cache or placeholder, need to download
            self.cache_stats['cad_api_downloads'] += 1
            logger.info(f"CAD file not in cache for {product_id}, downloading from API...")
            
            # First get product info to find CAD URLs
            product_info = self.get_product_info(product_id)
            if not product_info:
                logger.error(f"Could not get product info for {product_id}")
                return None
            
            # Find CAD URL in Links array - prefer 3D STEP format
            cad_url = None
            links = product_info.get('Links', [])
            
            # Priority order for CAD formats - prefer 3D over 2D, STEP over other formats
            # STEP is industry standard, most compatible with CAD software
            cad_preferences = ['3-D STEP', '3-D PDF', '2-D PDF', '3-D IGES', '2-D DXF']
            
            # Find the first available format in our preference order
            for preference in cad_preferences:
                for link in links:
                    if link.get('Key') == preference:
                        cad_url = link.get('Value')
                        break
                if cad_url:
                    break  # Found our preferred format, stop looking
            
            if not cad_url:
                logger.warning(f"No CAD URL found for product {product_id}, creating placeholder")
                create_placeholder(CACHE_DIR, 'cad', product_id)
                return None
            
            # Construct full URL
            full_url = API_BASE_URL + cad_url
            response = self.session.get(full_url, timeout=60, stream=True, verify=self.verify)
            
            if response.status_code == 200:
                # Determine file extension from URL
                extension = '.step'  # Default
                
                if '.pdf' in cad_url.lower():
                    extension = '.pdf'
                elif '.step' in cad_url.lower() or '.stp' in cad_url.lower():
                    extension = '.step'
                elif '.iges' in cad_url.lower() or '.igs' in cad_url.lower():
                    extension = '.igs'
                elif '.dxf' in cad_url.lower():
                    extension = '.dxf'
                elif '.dwg' in cad_url.lower():
                    extension = '.dwg'
                
                if not output_path:
                    output_path = CACHE_DIR / f"cad_{product_id}{extension}"
                
                # Stream download to handle large CAD files efficiently
                # 8KB chunks prevent memory issues with large files
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                logger.info(f"Downloaded and cached CAD file for {product_id} to {output_path}")
                return output_path
            else:
                logger.error(f"Failed to download CAD for {product_id}: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error downloading CAD for {product_id}: {str(e)}")
            return None
    
    def download_image_file(self, product_id: str, output_path: Optional[Path] = None) -> Optional[Path]:
        """Download image file for a product, checking cache and placeholders first."""
        if not self.is_authenticated or not self.auth_token:
            raise RuntimeError("Not authenticated. Please login first.")
            
        try:
            # First check if we have a valid placeholder indicating no image available
            if check_for_placeholder(CACHE_DIR, 'image', product_id):
                logger.info(f"Valid placeholder found - no image available for {product_id}")
                return None
            
            # Check cache for actual image files
            common_extensions = ['.png', '.jpg', '.jpeg', '.svg']
            for ext in common_extensions:
                cached_path = CACHE_DIR / f"image_{product_id}{ext}"
                if cached_path.exists():
                    self.cache_stats['image_cache_hits'] += 1
                    logger.info(f"Using cached image for {product_id}: {cached_path}")
                    return cached_path if not output_path else cached_path
            
            # Not in cache or placeholder, need to download
            self.cache_stats['image_api_downloads'] += 1
            logger.info(f"Image not in cache for {product_id}, downloading from API...")
            
            # First get product info to find the image URL
            product_info = self.get_product_info(product_id)
            if not product_info:
                logger.error(f"Could not get product info for {product_id}")
                return None
            
            # Find image URL in Links array
            image_url = None
            links = product_info.get('Links', [])
            for link in links:
                if link.get('Key') == 'Image':
                    image_url = link.get('Value')
                    break
            
            if not image_url:
                logger.warning(f"No image URL found for product {product_id}, creating placeholder")
                create_placeholder(CACHE_DIR, 'image', product_id)
                return None
            
            # Construct full URL
            full_url = API_BASE_URL + image_url
            response = self.session.get(full_url, timeout=60, stream=True, verify=self.verify)
            
            if response.status_code == 200:
                # Determine file extension from URL or headers
                content_type = response.headers.get('content-type', '')
                extension = '.jpg'  # Default
                
                # Determine image format - check URL first, then HTTP headers
                # URL-based detection is more reliable than content-type headers
                if '.png' in image_url.lower():
                    extension = '.png'
                elif '.svg' in image_url.lower():
                    extension = '.svg'   # Vector format, scalable
                elif '.jpg' in image_url.lower() or '.jpeg' in image_url.lower():
                    extension = '.jpg'
                # Fallback to content-type header if URL doesn't have extension
                elif 'png' in content_type:
                    extension = '.png'
                elif 'svg' in content_type:
                    extension = '.svg'
                
                if not output_path:
                    output_path = CACHE_DIR / f"image_{product_id}{extension}"
                
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                logger.info(f"Downloaded and cached image for {product_id} to {output_path}")
                return output_path
            else:
                logger.error(f"Failed to download image for {product_id}: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error downloading image for {product_id}: {str(e)}")
            return None
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache usage statistics."""
        return self.cache_stats.copy()
    
    def clean_cache_placeholders(self) -> int:
        """Clean expired placeholder files from cache."""
        return clean_expired_placeholders(CACHE_DIR)
    
    def print_cache_stats(self):
        """Print cache usage statistics."""
        stats = self.cache_stats
        total_product_requests = stats['product_info_cache_hits'] + stats['product_info_api_calls']
        total_image_requests = stats['image_cache_hits'] + stats['image_api_downloads']
        total_cad_requests = stats['cad_cache_hits'] + stats['cad_api_downloads']
        total_subscription_requests = stats['subscription_cache_skips'] + stats['subscription_api_calls']
        
        logger.info("=== Cache Usage Statistics ===")
        
        if total_subscription_requests > 0:
            subscription_cache_rate = (stats['subscription_cache_skips'] / total_subscription_requests) * 100
            logger.info(f"Subscriptions: {stats['subscription_cache_skips']} skipped (cached), {stats['subscription_api_calls']} API calls ({subscription_cache_rate:.1f}% cache skip rate)")
        
        if total_product_requests > 0:
            product_cache_rate = (stats['product_info_cache_hits'] / total_product_requests) * 100
            logger.info(f"Product Info: {stats['product_info_cache_hits']} cache hits, {stats['product_info_api_calls']} API calls ({product_cache_rate:.1f}% cache hit rate)")
        
        if total_image_requests > 0:
            image_cache_rate = (stats['image_cache_hits'] / total_image_requests) * 100
            logger.info(f"Images: {stats['image_cache_hits']} cache hits, {stats['image_api_downloads']} downloads ({image_cache_rate:.1f}% cache hit rate)")
        
        if total_cad_requests > 0:
            cad_cache_rate = (stats['cad_cache_hits'] / total_cad_requests) * 100
            logger.info(f"CAD Files: {stats['cad_cache_hits']} cache hits, {stats['cad_api_downloads']} downloads ({cad_cache_rate:.1f}% cache hit rate)")
        
        total_requests = total_product_requests + total_image_requests + total_cad_requests + total_subscription_requests
        total_cache_hits = stats['product_info_cache_hits'] + stats['image_cache_hits'] + stats['cad_cache_hits'] + stats['subscription_cache_skips']
        
        if total_requests > 0:
            overall_cache_rate = (total_cache_hits / total_requests) * 100
            logger.info(f"Overall: {total_cache_hits} cache hits/skips, {total_requests - total_cache_hits} API calls ({overall_cache_rate:.1f}% cache hit rate)")
        
        logger.info("===============================")
    
    def process_products(self, product_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Process multiple products and gather all their data."""
        results = {}
        
        for product_id in product_ids:
            logger.info(f"Processing product: {product_id}")
            
            # SMART RATE LIMITING: Track if any API calls are made for this product
            # Only apply rate limiting delays when we actually hit the API
            api_calls_made = False
            
            # Check if product info is already cached to avoid redundant subscription
            # Subscription API tells McMaster we want to access this product's data
            cache_file = CACHE_DIR / f"product_{product_id}.json"
            if cache_file.exists():
                self.cache_stats['subscription_cache_skips'] += 1
                logger.info(f"Product {product_id} already cached, skipping subscription call")
            else:
                # Add to subscription only if not cached - this IS an API call
                logger.info(f"Product {product_id} not cached, calling subscription API")
                self.add_product_subscription(product_id)
                api_calls_made = True  # Mark that we made an API call
            
            # Get product info (will use cache if available)
            product_info = self.get_product_info(product_id)
            if not product_info:
                logger.warning(f"Skipping {product_id} - could not retrieve product info")
                continue
            
            # Check if product info came from API (not cache)
            # We need to track if get_product_info() made an API call vs used cache
            if self.cache_stats['product_info_api_calls'] > 0:
                # Compare API call count before/after to detect new calls
                prev_api_calls = getattr(self, '_prev_product_api_calls', 0)
                current_api_calls = self.cache_stats['product_info_api_calls']
                if current_api_calls > prev_api_calls:
                    api_calls_made = True  # New API call was made
                self._prev_product_api_calls = current_api_calls
            
            # Download files (these methods track their own cache hits/API calls)
            # Capture download stats before attempting downloads
            prev_cad_calls = self.cache_stats['cad_api_downloads']
            prev_image_calls = self.cache_stats['image_api_downloads']
            
            cad_path = self.download_cad_file(product_id)
            image_path = self.download_image_file(product_id)
            
            # Check if downloads made API calls by comparing stats before/after
            # If either counter increased, we made network requests
            if (self.cache_stats['cad_api_downloads'] > prev_cad_calls or 
                self.cache_stats['image_api_downloads'] > prev_image_calls):
                api_calls_made = True  # File downloads required API calls
            
            results[product_id] = {
                "info": product_info,
                "cad_path": str(cad_path) if cad_path else None,
                "image_path": str(image_path) if image_path else None
            }
            
            # SMART RATE LIMITING - ONLY apply delays if API calls were made
            # This prevents unnecessary 12+ second delays when all data is cached
            if api_calls_made:
                logger.info(f"API calls made for {product_id}, applying rate limiting...")
                time.sleep(1)  # Be respectful to McMaster-Carr's servers
            else:
                logger.info(f"All data for {product_id} served from cache, skipping rate limiting")
                # No delay needed - we didn't hit their servers
        
        # Print cache statistics after processing all products
        self.print_cache_stats()
        
        return results