# myconfig Design Document

A portable configuration management tool for quickly restoring your environment on any machine.

## Design Choices

### Language: Python

**Decision**: Python 3.10+ with pipx distribution

**Rationale**:
- Rapid development and easy iteration
- User already familiar with Python
- Ubuntu (target OS) always has Python 3 installed
- Rich ecosystem for CLI tools, SSH, and YAML handling

**Trade-off**: Not a single binary like Go/Rust would provide. Mitigated by:
- Using pipx for clean isolated installation
- Target machines (Ubuntu) have Python pre-installed
- Remote deploy works via SSH where Python is also available

### Configuration Format: YAML

**Decision**: YAML for the declarative manifest (`config.yml`)

**Rationale**:
- Human-readable and easy to edit manually
- Supports comments (unlike JSON)
- Good for nested structures (profiles, app configs)
- Widely understood format

**Schema**:
```yaml
version: 1
package_managers:
  preference: [apt, snap, cargo]  # Global order
profiles:
  base:
    apps:
      helix: { prefer: cargo }
      git: {}
    configs:
      - .bashrc
      - .gitconfig
  work:
    extends: base
    apps:
      docker: {}
```

### Storage: Simple File Copies

**Decision**: Copy tracked files to `~/.config/myconfig/files/`

**Rationale**:
- Simple and transparent - users can inspect/edit stored files directly
- No learning curve (vs git-based solutions like chezmoi)
- Easy to understand what's being tracked
- Mirrors home directory structure for clarity

**Alternative considered**: Git-backed repository
- Rejected for initial version to keep things simple
- Can be added later as optional sync mechanism

**Sync workflow**: Files can flow in both directions:
- `apply` copies stored files → system (restore configuration)
- `sync` copies system files → storage (capture changes)

### Path Handling: Relative to $HOME

**Decision**: Store paths relative to home directory (e.g., `.bashrc` not `/home/user/.bashrc`)

**Rationale**:
- Portable across different usernames
- Works when deploying to remote machines with different users
- Intuitive for dotfiles which are typically in `$HOME`

### CLI Style: Git-style Subcommands

**Decision**: `myconfig add app helix` instead of `myconfig --add-app helix`

**Rationale**:
- More readable and discoverable
- Familiar pattern (git, docker, kubectl)
- Better help text organization
- Easier to extend with new commands

**Framework**: Click
- Mature, well-documented
- Excellent subcommand support
- Good error messages and help generation

### Profile System: Inheritance with Base

**Decision**: Profiles can extend other profiles

**Rationale**:
- Reduces duplication (common tools in `base`, specialized in `work`/`personal`)
- Single source of truth for shared configuration
- Flexible for different environments

**Resolution**: Child profile merges with parent, child wins on conflicts

### Package Manager: Preference Order + Per-App Override

**Decision**: Global preference list with per-app override capability

**Rationale**:
- Sensible defaults (apt → snap → cargo)
- Flexibility when needed (e.g., prefer cargo for helix)
- Handles different availability across systems

**Example**:
```yaml
package_managers:
  preference: [apt, snap, cargo]  # Try apt first
profiles:
  base:
    apps:
      helix: { prefer: cargo }    # Override: use cargo for helix
      git: {}                      # Use global preference
```

### Conflict Handling: Backup Then Overwrite

**Decision**: Create timestamped `.bak` files before overwriting

**Rationale**:
- Safe by default - never lose existing configuration
- Automatic - no user intervention needed
- Recoverable - backups are right next to originals

**Format**: `<filename>.bak.<YYYYMMDD_HHMMSS>`

### Secret Detection: Warn But Don't Block

**Decision**: Detect potential secrets and warn, but allow user to proceed

**Rationale**:
- User's responsibility to manage secrets
- Avoid false positives blocking legitimate use
- Education through warnings

**Patterns detected**:
- File names: `.env`, `*_token`, `*_secret`, `*.pem`, `*.key`, `id_rsa`, etc.
- Content: API keys, passwords, private keys, GitHub tokens

### Export Format: Encrypted tar.gz

**Decision**: tar.gz archive encrypted with OpenSSL (AES-256-CBC)

**Rationale**:
- `tar.gz` is universal and well-understood
- OpenSSL is available everywhere (no extra dependencies)
- Password-based encryption is simple for users
- SHA256 checksum for integrity verification

**Alternative considered**: age encryption
- Cleaner design but requires additional tool installation
- OpenSSL is more universally available

### Remote Deployment: Full Automation via SSH

**Decision**: Single command deploys everything to remote host

**Rationale**:
- Main use case: quickly set up a new VM/container
- Reduces friction to "feel at home" on any machine
- SSH is the standard for remote Linux administration

**Flow**:
1. Connect via SSH (key-based auth)
2. Optionally add public key to `authorized_keys`
3. Create encrypted archive, SCP to remote
4. Decrypt and extract on remote
5. Install packages (requires sudo)
6. Copy config files to correct locations

**Dependency**: paramiko (pure Python SSH library)

## Directory Structure

```
~/.config/myconfig/
├── config.yml              # Main manifest (tracked items, profiles)
└── files/                  # Stored config files
    ├── .bashrc
    ├── .gitconfig
    └── .config/
        └── helix/
            └── config.toml
```

## Future Considerations

Features intentionally deferred for simplicity:

1. **Git sync**: Optional git-backed storage for version control and cloud sync
2. **Flatpak support**: Additional package manager
3. **Template variables**: e.g., `{{hostname}}` in config files
4. **Hooks**: Pre/post apply scripts
5. **Diff viewer**: Interactive diff before applying changes
6. **Config validation**: Schema validation for tracked configs
