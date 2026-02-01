# myconfig

A portable configuration management tool for quickly restoring your environment on any machine.

Track your favorite apps and dotfiles, export them to a USB drive, and restore on any Ubuntu machine in seconds.

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

# Track some apps (apt is the default package manager)
myconfig add app git
myconfig add app helix -m cargo   # use cargo for helix
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
# Add an app (defaults to apt)
myconfig add app curl

# Add an app with specific package manager
myconfig add app helix --manager cargo    # or -m cargo
myconfig add app spotify-client -m snap

# Add an app with extra package manager parameters
myconfig add app node -m snap -p "--classic"
myconfig add app code -m snap -p "--classic --channel=stable"

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
    apt: git, ripgrep, curl
    cargo: helix
  Configs:
    [+] .bashrc
    [+] .gitconfig

[work]
  extends: base
  Apps:
    apt: docker, kubectl
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

# Only install apps (skip config files)
myconfig apply --app

# Only apply config files (skip app installation)
myconfig apply --config

# Preview changes without applying
myconfig apply --dry-run
```

This will:
1. Install tracked apps using preferred package managers
2. Backup existing config files (creates `.bak.<timestamp>` files)
3. Copy tracked configs to their correct locations

Use `--app` or `--config` to apply only one category. When neither flag is given, both are applied.

### Export and Import

```bash
# Export to encrypted archive (will prompt for password)
myconfig export /media/usb/

# Export to specific file
myconfig export ~/backup/myconfig_backup.tar.gz.enc

# Import from archive (will prompt for password)
myconfig import /media/usb/myconfig_20250125_143022.tar.gz.enc
```

### Git Sync

Sync your configuration between machines using a git remote:

```bash
# Initialize with a git remote (fresh machine — clones the repo)
myconfig init --git git@github.com:user/dotfiles.git

# Or add git to an existing myconfig setup
myconfig init --git git@github.com:user/dotfiles.git

# After making changes (add apps, sync configs, etc.), push to remote
myconfig git push

# On another machine, pull the latest
myconfig git pull
```

`myconfig git push` stages all changes, creates a date-stamped commit, and pushes. `myconfig git pull` pulls the latest from remote. You can also use regular git commands directly in `~/.config/myconfig/` for more control.

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
profiles:
  base:
    apps:
      apt: [git, curl]
      cargo: [helix]
    configs:
      - .bashrc
      - .gitconfig

  work:
    extends: base          # Inherits all apps and configs from base
    apps:
      apt: [docker, kubectl]
    configs:
      - .kube/config

  personal:
    extends: base
    apps:
      snap: [spotify-client]
    configs:
      - .config/personal-projects.conf
```

When you apply the `work` profile, you get:
- All apps from `base` (apt: git, curl; cargo: helix) + work apps (apt: docker, kubectl)
- All configs from `base` (.bashrc, .gitconfig) + work configs (.kube/config)

## Package Managers

myconfig supports four package managers:
- **apt** - Debian/Ubuntu packages (default)
- **snap** - Snap packages
- **cargo** - Rust packages
- **npm** - Node.js packages

Apps are grouped by package manager, enabling batch installation for efficiency.

### Specifying Package Manager

When adding an app, specify the manager with `--manager` (or `-m`). If not specified, `apt` is used:

```bash
# Uses apt (default)
myconfig add app git
myconfig add app curl

# Specify different managers
myconfig add app helix -m cargo      # Rust packages via cargo
myconfig add app spotify-client -m snap
myconfig add app typescript -m npm
```

### Config Structure

Apps are stored grouped by manager for batch installation:

```yaml
profiles:
  base:
    apps:
      apt: [git, curl, htop]
      cargo: [helix, ripgrep]
      snap:
        - spotify-client
        - node: "--classic"           # with extra parameters
        - code: "--classic --channel=stable"
```

Apps with parameters are stored as `{name: "params"}` and installed individually to preserve their specific arguments.

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
| `myconfig init [--git <url>]` | Initialize myconfig (optionally with git remote) |
| `myconfig add app <name>` | Track an application |
| `myconfig add config <path>` | Track a config file |
| `myconfig remove app <name>` | Stop tracking an app |
| `myconfig remove config <path>` | Stop tracking a config |
| `myconfig list` | List tracked items |
| `myconfig status` | Check for changed files |
| `myconfig sync` | Sync modified files to storage |
| `myconfig apply [--app] [--config]` | Apply configuration locally |
| `myconfig export <dest>` | Export to encrypted archive |
| `myconfig import <archive>` | Import from archive |
| `myconfig git push` | Commit and push config to remote |
| `myconfig git pull` | Pull latest config from remote |

### Common Options

| Option | Description |
|--------|-------------|
| `--profile, -P` | Specify profile (default: base) |
| `--manager, -m` | Package manager (apt/snap/cargo/npm, default: apt) |
| `--params, -p` | Extra parameters for package manager (e.g., `--classic`) |
| `--dry-run` | Preview changes without applying |
| `--app` | Only install apps (apply command) |
| `--config` | Only apply config files (apply command) |
| `--keep-file` | Keep stored copy when removing config |
| `--help` | Show help for any command |

## Requirements

- Python 3.10+
- OpenSSL (for encrypted export/import)
- Git (for git sync feature)

## License

MIT
