"""
Secure credential storage using system keychains.
Works cross-platform with macOS Keychain, Windows Credential Manager, and Linux Secret Service.
"""

import os
import logging
from typing import Optional

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logging.info("keyring module not installed - credentials will not persist between sessions")


# Service name for keyring storage
SERVICE_NAME = "mcmaster-carr-label-generator"


def is_keyring_available() -> bool:
    """Check if keyring is available and working."""
    if not KEYRING_AVAILABLE:
        return False
    
    try:
        # Test keyring by trying to get a non-existent key
        backend = keyring.get_keyring()
        
        # Check if we have a working backend (not the null/fail backend)
        if hasattr(backend, 'priority') and backend.priority <= 0:
            logging.debug(f"Keyring backend '{backend}' has low priority, may not work")
            return False
            
        # Try to actually use it
        keyring.get_password(SERVICE_NAME, "test_key")
        return True
    except Exception as e:
        # Keyring might be available but not configured properly
        logging.debug(f"Keyring not working: {e}")
        return False


def get_credential_from_keychain(key: str) -> Optional[str]:
    """Get a credential from the system keychain.
    
    Args:
        key: The credential key (e.g., 'MCMASTER_API_USERNAME')
    
    Returns:
        The credential value or None if not found
    """
    if not is_keyring_available():
        return None
    
    try:
        return keyring.get_password(SERVICE_NAME, key)
    except Exception as e:
        logging.debug(f"Failed to get credential from keychain: {e}")
        return None


def save_credential_to_keychain(key: str, value: str) -> bool:
    """Save a credential to the system keychain.
    
    Args:
        key: The credential key (e.g., 'MCMASTER_API_USERNAME')
        value: The credential value
    
    Returns:
        True if saved successfully, False otherwise
    """
    if not is_keyring_available():
        return False
    
    try:
        keyring.set_password(SERVICE_NAME, key, value)
        return True
    except Exception as e:
        logging.debug(f"Failed to save credential to keychain: {e}")
        return False


def delete_credential_from_keychain(key: str) -> bool:
    """Delete a credential from the system keychain.
    
    Args:
        key: The credential key to delete
    
    Returns:
        True if deleted successfully, False otherwise
    """
    if not is_keyring_available():
        return False
    
    try:
        keyring.delete_password(SERVICE_NAME, key)
        return True
    except Exception:
        # Might fail if key doesn't exist, which is OK
        return False


def get_credential(key: str) -> Optional[str]:
    """Get a credential from environment variable or system keychain.
    
    Checks in order:
    1. Environment variable
    2. System keychain (if available)
    
    Args:
        key: The credential key
    
    Returns:
        The credential value or None if not found
    """
    # First check environment variable
    value = os.environ.get(key)
    if value:
        return value
    
    # Then check keychain
    return get_credential_from_keychain(key)


def cache_credential(key: str, value: str) -> None:
    """Cache a credential in environment and optionally keychain.
    
    Always sets the environment variable for the current process.
    If keyring is available, also saves to system keychain for persistence.
    
    Args:
        key: The credential key
        value: The credential value
    """
    # Always set in current environment
    os.environ[key] = value
    
    # Try to save to keychain for persistence
    if save_credential_to_keychain(key, value):
        logging.debug(f"Saved {key} to system keychain")
    else:
        logging.debug(f"Could not save {key} to keychain, only available for this process")


def clear_all_credentials() -> None:
    """Clear all stored credentials from the keychain."""
    credential_keys = [
        'MCMASTER_API_USERNAME',
        'MCMASTER_API_PASSWORD', 
        'MCMASTER_CERT_PASSWORD'
    ]
    
    for key in credential_keys:
        delete_credential_from_keychain(key)
        if key in os.environ:
            del os.environ[key]
    
    print("All cached credentials have been cleared from the system keychain.")