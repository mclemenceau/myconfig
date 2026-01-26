# myconfig

A portable configuration management tool for quickly restoring your environment on any machine.

Track your favorite apps and dotfiles, export them to a USB drive, and deploy to any Ubuntu machine in seconds.

## Installation

```bash
# Using pipx (recommended)
pipx install .

# Or with pip in a virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

## Quick Start

```bash
# Initialize myconfig
myconfig init

# Track some apps
myconfig add app git
myconfig add app helix --prefer cargo
myconfig add app ripgrep

# Track config files
myconfig add config ~/.bashrc
myconfig add config ~/.gitconfig
myconfig add config ~/.config/helix/config.toml

# See what you're tracking
myconfig list
```

## Usage Examples

### Adding Apps and Configs

```bash
# Add an app (uses global package manager preference)
myconfig add app curl

# Add an app with specific package manager preference
myconfig add app helix --prefer cargo
myconfig add app spotify-client --prefer snap

# Add a config file
myconfig add config ~/.bashrc
myconfig add config ~/.ssh/config
myconfig add config ~/.config/starship.toml

# Add to a specific profile
myconfig add app docker --profile work
myconfig add config ~/.config/work-vpn.conf --profile work
```

### Removing Apps and Configs

```bash
# Remove an app
myconfig remove app helix

# Remove a config (also deletes stored copy)
myconfig remove config ~/.bashrc

# Remove config but keep the stored copy
myconfig remove config ~/.bashrc --keep-file

# Remove from specific profile
myconfig remove app docker --profile work
```

### Listing and Status

```bash
# List all tracked items
myconfig list

# List specific profile
myconfig list --profile work

# Check if tracked files have changed
myconfig status

# Sync modified system files back to storage
myconfig sync
```

Example output:
```
[base]
  Apps:
    - helix (prefer: cargo)
    - ripgrep
    - git
  Configs:
    [+] .bashrc
    [+] .gitconfig

[work]
  extends: base
  Apps:
    - docker
    - kubectl
  Configs:
    [+] .config/work-vpn.conf
```

### Syncing Changes

After modifying tracked config files on your system, sync the changes back to storage:

```bash
# Sync all modified files
myconfig sync

# Sync only a specific profile
myconfig sync --profile work

# Preview what would be synced
myconfig sync --dry-run
```

This updates the stored copies with the current versions from your system.

### Applying Configuration

```bash
# Apply base profile to local system
myconfig apply

# Apply specific profile
myconfig apply --profile work

# Preview changes without applying
myconfig apply --dry-run
```

This will:
1. Install tracked apps using preferred package managers
2. Backup existing config files (creates `.bak.<timestamp>` files)
3. Copy tracked configs to their correct locations

### Export and Import

```bash
# Export to encrypted archive (will prompt for password)
myconfig export /media/usb/

# Export to specific file
myconfig export ~/backup/myconfig_backup.tar.gz.enc

# Import from archive (will prompt for password)
myconfig import /media/usb/myconfig_20250125_143022.tar.gz.enc
```

### Remote Deployment

Deploy your configuration to a remote machine via SSH:

```bash
# Deploy to remote host
myconfig deploy ubuntu@192.168.1.50

# Deploy specific profile
myconfig deploy ubuntu@192.168.1.50 --profile work

# Use specific SSH key
myconfig deploy ubuntu@192.168.1.50 --key ~/.ssh/id_work
```

This will:
1. Connect via SSH
2. Add your public key to remote `authorized_keys` (if needed)
3. Transfer encrypted configuration archive
4. Install all tracked apps (requires sudo on remote)
5. Copy all config files to correct locations

## Working with Profiles

Profiles let you organize different configurations for different environments.

### Creating Profiles

Profiles are created automatically when you add items to them:

```bash
# Add items to a new "work" profile
myconfig add app docker --profile work
myconfig add app kubectl --profile work
myconfig add config ~/.kube/config --profile work
```

### Profile Inheritance

Edit `~/.config/myconfig/config.yml` to set up inheritance:

```yaml
version: 1
package_managers:
  preference: [apt, snap, cargo]

profiles:
  base:
    apps:
      git: {}
      curl: {}
      helix:
        prefer: cargo
    configs:
      - .bashrc
      - .gitconfig

  work:
    extends: base          # Inherits all apps and configs from base
    apps:
      docker: {}
      kubectl: {}
    configs:
      - .kube/config

  personal:
    extends: base
    apps:
      spotify-client:
        prefer: snap
    configs:
      - .config/personal-projects.conf
```

When you apply the `work` profile, you get:
- All apps from `base` (git, curl, helix) + work apps (docker, kubectl)
- All configs from `base` (.bashrc, .gitconfig) + work configs (.kube/config)

## Package Manager Preference

myconfig supports three package managers:
- **apt** - Debian/Ubuntu packages
- **snap** - Snap packages
- **cargo** - Rust packages

### Global Preference

Set the default order in `config.yml`:

```yaml
package_managers:
  preference: [apt, snap, cargo]  # Try apt first, then snap, then cargo
```

### Per-App Override

Some tools are better installed via specific managers:

```bash
# Helix editor - better to install via cargo for latest version
myconfig add app helix --prefer cargo

# Spotify - only available as snap
myconfig add app spotify-client --prefer snap
```

## Secret Detection

myconfig warns you when tracking files that might contain secrets:

```bash
$ myconfig add config ~/.env
Warning: Environment file may contain secrets: .env
Added config: .env (profile: base)
```

Detected patterns include:
- `.env` files
- Files with `token`, `secret`, `key` in the name
- SSH private keys (`id_rsa`, `id_ed25519`)
- Files containing API keys, passwords, or private key blocks

The warning is informational - you can still track these files, but be careful when exporting or sharing your configuration.

## File Locations

```
~/.config/myconfig/
├── config.yml      # Your configuration manifest
└── files/          # Stored copies of tracked config files
    ├── .bashrc
    ├── .gitconfig
    └── .config/
        └── helix/
            └── config.toml
```

## Command Reference

| Command | Description |
|---------|-------------|
| `myconfig init` | Initialize myconfig |
| `myconfig add app <name>` | Track an application |
| `myconfig add config <path>` | Track a config file |
| `myconfig remove app <name>` | Stop tracking an app |
| `myconfig remove config <path>` | Stop tracking a config |
| `myconfig list` | List tracked items |
| `myconfig status` | Check for changed files |
| `myconfig sync` | Sync modified files to storage |
| `myconfig apply` | Apply configuration locally |
| `myconfig export <dest>` | Export to encrypted archive |
| `myconfig import <archive>` | Import from archive |
| `myconfig deploy <user@host>` | Deploy to remote host |

### Common Options

| Option | Description |
|--------|-------------|
| `--profile, -p` | Specify profile (default: base) |
| `--prefer` | Package manager preference (apt/snap/cargo) |
| `--dry-run` | Preview changes without applying |
| `--keep-file` | Keep stored copy when removing config |
| `--key, -i` | SSH key for remote deployment |
| `--help` | Show help for any command |

## Requirements

- Python 3.10+
- OpenSSL (for encrypted export/import)
- SSH key pair (for remote deployment)

## License

MIT
