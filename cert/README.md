# Certificate Directory

This directory should contain the McMaster-Carr API client certificate required for authentication.

## Required File

Place your client certificate file here with the name specified in your configuration:
- `RamSripracha.pfx` (or your specific certificate filename)

## Important Security Notes

- **NEVER** commit your actual certificate file to version control
- The certificate file (*.pfx, *.p12, *.pem) is excluded via .gitignore
- Store your certificate password securely (use environment variables or secure credential storage)

## Setup Instructions

1. Obtain your client certificate from McMaster-Carr
2. Place the certificate file in this directory
3. Ensure the filename matches what's configured in your code
4. Set up your certificate password:
   - Via environment variable: `MCMASTER_CERT_PASSWORD`
   - Or use the secure credential prompt when running the application

## Troubleshooting

If you get certificate-related errors:
1. Verify the certificate file exists in this directory
2. Check that the filename matches your configuration
3. Ensure the certificate password is correct
4. Verify file permissions allow reading the certificate

For more information, see the main project documentation.