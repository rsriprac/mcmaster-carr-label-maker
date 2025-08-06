import os
import getpass
import sys
from typing import Dict, Optional

from .keychain import get_credential, cache_credential, is_keyring_available


def get_credentials() -> Dict[str, str]:
    """Get McMaster-Carr API credentials from environment variables, keychain, or prompt user.
    
    Returns a dictionary with API_USERNAME, API_PASSWORD, and CERT_PASSWORD.
    Checks in order:
    1. Environment variables
    2. System keychain (if available)
    3. Prompts user if not found
    
    Credentials are cached in the system keychain for secure persistence.
    """
    credentials = {}
    
    # Define required credentials with their environment variable names and prompts
    required_creds = [
        {
            'env_var': 'MCMASTER_API_USERNAME',
            'key': 'API_USERNAME',
            'prompt': 'McMaster-Carr API Username (email): ',
            'is_password': False
        },
        {
            'env_var': 'MCMASTER_API_PASSWORD',
            'key': 'API_PASSWORD',
            'prompt': 'McMaster-Carr API Password: ',
            'is_password': True
        },
        {
            'env_var': 'MCMASTER_CERT_PASSWORD',
            'key': 'CERT_PASSWORD',
            'prompt': 'Certificate Password: ',
            'is_password': True
        }
    ]
    
    # Show keyring status once
    keyring_available = is_keyring_available()
    if keyring_available:
        print("Using system keychain for secure credential storage.")
    else:
        print("Note: Keychain unavailable, credentials only cached for this process.")
    
    # Check each credential
    for cred in required_creds:
        # Try to get from environment or keychain
        value = get_credential(cred['env_var'])
        
        if not value:
            # Credential is missing, prompt user
            print(f"\nMissing {cred['env_var']}.")
            
            if cred['is_password']:
                # Use getpass for password fields (hides input)
                value = getpass.getpass(cred['prompt'])
            else:
                # Normal input for non-password fields
                value = input(cred['prompt'])
            
            if not value:
                print(f"Error: {cred['env_var']} cannot be empty.", file=sys.stderr)
                sys.exit(1)
            
            # Cache the credential
            cache_credential(cred['env_var'], value)
            
            if keyring_available:
                print(f"✓ {cred['env_var']} saved to system keychain")
            else:
                print(f"✓ {cred['env_var']} set for this process only")
        
        credentials[cred['key']] = value
    
    return credentials


def check_non_sensitive_env_vars() -> Dict[str, Optional[str]]:
    """Check for non-sensitive environment variables that can remain in .env file.
    
    Returns a dictionary with the current values.
    """
    return {
        'MCMASTER_SSL_VERIFY': os.getenv('MCMASTER_SSL_VERIFY', 'false')
    }