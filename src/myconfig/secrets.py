"""Secret detection for myconfig."""

import re
from pathlib import Path

# Patterns that likely indicate sensitive files
SECRET_PATTERNS = [
    (r"\.env$", "Environment file may contain secrets"),
    (r"\.env\.", "Environment file may contain secrets"),
    (r"_token$", "File name suggests it contains tokens"),
    (r"_secret$", "File name suggests it contains secrets"),
    (r"_key$", "File name suggests it contains keys"),
    (r"credentials", "File name suggests it contains credentials"),
    (r"\.pem$", "PEM files often contain private keys"),
    (r"\.key$", "Key files often contain private keys"),
    (r"id_rsa$", "SSH private key"),
    (r"id_ed25519$", "SSH private key"),
    (r"id_ecdsa$", "SSH private key"),
    (r"\.pgpass$", "PostgreSQL password file"),
    (r"\.netrc$", "Contains login credentials"),
    (r"\.npmrc$", "May contain npm tokens"),
    (r"\.pypirc$", "May contain PyPI tokens"),
]

# Content patterns that suggest secrets
CONTENT_PATTERNS = [
    (r"(?i)api[_-]?key\s*[=:]\s*['\"]?[a-zA-Z0-9_-]{20,}",
     "Possible API key found"),
    (r"(?i)secret[_-]?key\s*[=:]\s*['\"]?[a-zA-Z0-9_-]{20,}",
     "Possible secret key found"),
    (r"(?i)password\s*[=:]\s*['\"]?[^\s'\"]{8,}",
     "Possible password found"),
    (r"(?i)token\s*[=:]\s*['\"]?[a-zA-Z0-9_-]{20,}",
     "Possible token found"),
    (r"-----BEGIN (RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----",
     "Private key found"),
    (r"ghp_[a-zA-Z0-9]{36}",
     "GitHub personal access token found"),
    (r"gho_[a-zA-Z0-9]{36}",
     "GitHub OAuth token found"),
    (r"github_pat_[a-zA-Z0-9_]{22,}",
     "GitHub fine-grained token found"),
    (r"glpat-[a-zA-Z0-9_-]{20,}",
     "GitLab personal access token found"),
    (r"AKIA[0-9A-Z]{16}",
     "AWS access key ID found"),
    (r"sk-(ant-|proj-)?[a-zA-Z0-9_-]{40,}",
     "Possible AI provider API key found"),
]


def check_secrets(file_path: Path, relative_path: str) -> list[str]:
    """Check a file for potential secrets.

    Returns a list of warning messages, empty if no concerns found.
    """
    warnings = []

    # Check filename patterns
    filename = file_path.name
    for pattern, message in SECRET_PATTERNS:
        if re.search(pattern, filename, re.IGNORECASE):
            warnings.append(f"{message}: {relative_path}")

    # Check content patterns (only for text files)
    try:
        content = file_path.read_text(errors="ignore")
        for pattern, message in CONTENT_PATTERNS:
            if re.search(pattern, content):
                warnings.append(f"{message} in {relative_path}")
                break  # One content warning is enough
    except (OSError, UnicodeDecodeError):
        # Binary file or can't read, skip content check
        pass

    return warnings
