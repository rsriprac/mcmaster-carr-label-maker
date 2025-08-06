# Configuration Guide

This guide explains how to configure the McMaster-Carr Label Generator for different environments.

## Configuration Sources

The application uses a hierarchical configuration system with the following precedence (highest to lowest):

1. **Environment Variables** - Override all other settings
2. **config.py defaults** - Built-in defaults for non-sensitive settings

When running with `--verbose`, the application shows where each configuration value comes from.

## SSL Certificate Configuration

### CA Certificate Verification

The application supports multiple methods for verifying server SSL certificates, making it portable across different environments:

1. **Custom CA Bundle** (highest priority)
   - Place your CA bundle at `ca/ca.pem` in the project directory
   - Useful for corporate environments with internal CAs

2. **System Environment Variables** (recommended for portability)
   - `REQUESTS_CA_BUNDLE` - Standard requests library variable
   - `SSL_CERT_FILE` - Standard OpenSSL variable
   - `CURL_CA_BUNDLE` - Alternative CA bundle path
   
   Example:
   ```bash
   export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
   python -m src.main 91290A115
   ```

3. **Certifi Package** (default)
   - Uses the `certifi` Python package's CA bundle
   - Automatically updated and cross-platform compatible
   - Works out of the box on most systems

4. **Disable Verification** (not recommended)
   ```bash
   export MCMASTER_SSL_VERIFY=false
   python -m src.main 91290A115
   ```

### Client Certificate

The McMaster-Carr API requires client certificate authentication. Place your `.pfx` certificate file at:
```
cert/cert.pfx
```

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MCMASTER_API_USERNAME` | API username (email) | None (prompted once, then cached) |
| `MCMASTER_API_PASSWORD` | API password | None (prompted once, then cached) |
| `MCMASTER_CERT_PASSWORD` | Certificate password | None (prompted once, then cached) |
| `MCMASTER_SSL_VERIFY` | Enable SSL verification | `true` |
| `MCMASTER_LABEL_WIDTH` | Default label width | Cached from last use or `1.5` |
| `MCMASTER_LABEL_HEIGHT` | Default label height | Cached from last use or `0.5` |
| `MCMASTER_IMAGE_RATIO` | Image width ratio on label | `0.25` |
| `MCMASTER_OUTPUT_DIR` | Output directory | `output` |
| `MCMASTER_CACHE_DIR` | Cache directory | `cache` |
| `MCMASTER_API_RATE_LIMIT` | API rate limit (seconds) | `0.5` |
| `MCMASTER_CERT_FILENAME` | Certificate filename | `cert.pfx` |
| `MCMASTER_CA_FILENAME` | CA bundle filename | `ca.pem` |

### config.py Settings

The `src/config.py` file contains default values for non-sensitive settings. These can be overridden by environment variables.

## Secure Credential Storage

The application uses your system's secure keychain/credential manager to store sensitive credentials:

- **macOS**: Keychain Access
- **Windows**: Windows Credential Manager  
- **Linux**: Secret Service API (GNOME Keyring, KWallet)

When you run the application for the first time, it will prompt for any missing credentials:

```
Using system keychain for secure credential storage.

Missing MCMASTER_API_USERNAME.
McMaster-Carr API Username (email): your-email@example.com
✓ MCMASTER_API_USERNAME saved to system keychain

Missing MCMASTER_API_PASSWORD.
McMaster-Carr API Password: ********
✓ MCMASTER_API_PASSWORD saved to system keychain

Missing MCMASTER_CERT_PASSWORD.
Certificate Password: ********
✓ MCMASTER_CERT_PASSWORD saved to system keychain
```

These credentials are securely stored in your system's keychain and will be automatically loaded on future runs.

**Security Features:**
- Credentials are encrypted by the operating system
- Access is restricted to your user account
- No plain text storage on disk
- Survives system restarts

**Managing Credentials:**
```bash
# Clear all stored credentials
python -m src.main --clear-cache
```

**Note**: Label dimensions (width/height) are cached securely across sessions for convenience.

## Examples

### Corporate Environment with Custom CA
```bash
# Use company CA bundle
export SSL_CERT_FILE=/usr/local/share/ca-certificates/company-ca.crt
export MCMASTER_SSL_VERIFY=true

python -m src.main 91290A115
```

### Development Environment
```bash
# Disable SSL verification for testing
export MCMASTER_SSL_VERIFY=false

# Set custom dimensions
export MCMASTER_LABEL_WIDTH=2.0
export MCMASTER_LABEL_HEIGHT=1.0

python -m src.main --verbose 91290A115
```

### Docker/Container Environment
```bash
# Use container's CA certificates
export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
export MCMASTER_SSL_VERIFY=true

# Mount certificate
docker run -v /path/to/cert.pfx:/app/cert/cert.pfx ...
```

## Viewing Configuration

To see which configuration values are being used and their sources:

```bash
python -m src.main --verbose --help
```

This will show:
- Current configuration values
- Where each value comes from (environment variable or config.py)
- Redacted credentials (shown as asterisks)