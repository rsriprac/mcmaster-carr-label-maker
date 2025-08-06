# Setup Guide

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- McMaster-Carr API access and certificate

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/mcmaster-label-generator.git
   cd mcmaster-label-generator
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

   For image format support, you may also need:
   - **macOS**: `brew install poppler` (for PDF to image conversion)
   - **Ubuntu/Debian**: `sudo apt-get install poppler-utils`
   - **Windows**: Download poppler from [here](https://blog.alivate.com.au/poppler-windows/)

3. **Set up your certificate**
   - Place your McMaster-Carr API certificate (`.pfx` file) in the `cert/` directory
   - The certificate filename should match what's configured in the code

4. **Configure environment (optional)**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` if you need to change SSL verification settings.

## Authentication

The application supports two methods for providing credentials:

### Method 1: Environment Variables (Recommended for automation)
```bash
export MCMASTER_API_USERNAME=your-email@example.com
export MCMASTER_API_PASSWORD=your-password
export MCMASTER_CERT_PASSWORD=certificate-password
```

### Method 2: Interactive Prompts
If credentials aren't found in environment variables, the application will prompt you to enter them. The credentials are cached for the current session only.

## SSL/TLS Configuration

The McMaster-Carr API uses mutual TLS authentication:

- **Client Certificate**: Your `.pfx` certificate is required to authenticate with the API
- **Server Certificate Verification**: Controlled via `MCMASTER_SSL_VERIFY` environment variable
  - Set to `false` (default) to disable server certificate verification
  - Set to `true` to enable verification (requires proper CA certificates)

Note: The API may use internal certificate authorities, so server verification is disabled by default.

## Troubleshooting

### Certificate Issues
- Ensure your `.pfx` file is in the `cert/` directory
- Verify the certificate password is correct
- Check that the certificate hasn't expired

### Connection Issues
- Try setting `MCMASTER_SSL_VERIFY=false` in your environment
- Check your network allows HTTPS connections to `api.mcmaster.com`
- Verify your API credentials are correct

### Image Format Issues
- For PDF to image conversion, ensure poppler is installed
- Check that Pillow (PIL) is properly installed: `pip install --upgrade Pillow`
- Some formats may require additional system libraries