# Security Setup Guide

## ⚠️ Important Security Notice

The following files contain sensitive information and should **NEVER** be committed to version control:

### 🔐 Files to Keep Private

1. **Environment Variables**
   - `.env` - Contains API credentials
   - Any `.env.*` files (except `.env.example`)

2. **Certificates**
   - `cert/*.pfx` - Client certificates with private keys
   - `cert/*.p12` - PKCS12 certificates
   - `cert/*.key` - Private key files
   - `ca/*.pem` - CA certificates (if private)

3. **Cache Data**
   - `cache/` - May contain proprietary product information
   - Downloaded product data, images, and CAD files

4. **Output Files**  
   - `output/*.pdf` - Generated labels may contain proprietary info

## 🛡️ How to Remove Sensitive Files from Git

If any sensitive files were accidentally committed, remove them:

```bash
# Remove certificate from git tracking (but keep local file)
git rm --cached cert/rsriprac-cert.pfx

# Remove entire directories from tracking
git rm -r --cached cache/
git rm -r --cached output/

# Commit the removal
git commit -m "Remove sensitive files from tracking"

# Force push if needed (CAREFUL - this rewrites history)
# git push --force origin main
```

## 📝 Setting Up Your Environment

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your credentials:**
   ```
   MCMASTER_API_USERNAME=your_username
   MCMASTER_API_PASSWORD=your_password
   MCMASTER_CERT_PASSWORD=your_cert_password
   ```

3. **Place your certificate:**
   - Put your `.pfx` file in the `cert/` directory
   - Update `src/config.py` if the filename differs from `rsriprac-cert.pfx`

4. **Create necessary directories:**
   ```bash
   mkdir -p cache output
   ```

## ✅ What SHOULD Be Committed

- Source code (`src/`)
- Tests (`tests/`)
- Documentation (`*.md` files)
- Configuration templates (`.env.example`)
- Build files (`Makefile`, `requirements.txt`, `pytest.ini`)
- Example product lists (`product_id.*.txt`)

## 🔒 Best Practices

1. **Always use `.env` for credentials** - Never hardcode them
2. **Check `.gitignore` is working** - Run `git status` before committing
3. **Review commits** - Ensure no sensitive data is included
4. **Use separate certificates** - Dev vs production environments
5. **Rotate credentials regularly** - Especially if exposed

## 🚨 If Credentials Are Exposed

If you accidentally commit credentials:

1. **Immediately rotate/change them** at McMaster-Carr
2. **Remove from git history** using BFG Repo-Cleaner or git filter-branch
3. **Force push cleaned history** to all remotes
4. **Notify team members** to re-clone the repository

## 📋 Pre-Commit Checklist

Before every commit:
- [ ] Run `git status` - check no sensitive files are staged
- [ ] Review `.env` is NOT in the list
- [ ] Verify `cert/` directory is NOT included  
- [ ] Check `cache/` and `output/` are NOT included
- [ ] Ensure only source code and documentation are staged

Remember: It's easier to prevent sensitive data from being committed than to remove it later!