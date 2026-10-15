# CLAUDE.md

This file provides guidance to AI agents working with code in this
repository.

## Project Overview

`myconfig` is a Python CLI (Click + PyYAML) that tracks apps and dotfiles
and restores them on Ubuntu machines. Sources live in `src/myconfig/`:

- `cli.py` - all commands
- `config.py` - config.yml I/O, path handling and validation
- `profiles.py` - profile inheritance
- `packages.py` - apt/snap/cargo/npm managers
- `files.py` - applying configs with backups
- `export.py` - encrypted export/import (OpenSSL)
- `git.py` - git sync
- `secrets.py` - secret detection warnings

See DESIGN.md for design decisions.

## Development Life Cycle

- **Implement TDD**: create tests for new functionality and bug fixes
- **Validate**: Run linting and unit tests before commit

## Build and Development Key Commands

```bash
make deps   # create .venv and install with dev dependencies
make lint   # ruff check src tests
make test   # pytest with coverage
```

## Testing

- Tests use the `home` fixture (tests/conftest.py) to point `$HOME` at a
  temporary directory. Never write tests that touch the real `$HOME`.
- Prefer end-to-end tests through the `run` fixture (Click CliRunner).
- Never call real package managers in tests: mock `_run`/`is_installed`.

## Git Workflow

### Branch Naming

- `fix/` - bug fixes (e.g., `fix/export-permissions`)
- `feature/` - new features (e.g., `feature/flatpak-support`)
- `chore/` - maintenance tasks (e.g., `chore/update-dependencies`)

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) format: `type(scope): description`

Follow the 50/72 rule:
- Subject line: 50 characters or less
- Body text: wrap at 72 characters

**Types:**
- `feat`: new feature
- `fix`: bug fix
- `docs`: documentation changes
- `test`: adding/updating tests
- `chore`: maintenance, dependencies
- `refactor`: code restructuring without behavior change

**Examples:**
```
fix(export): pass password to openssl on stdin
feat(cli): add --app and --config flags to apply
docs: update CLAUDE.md with git workflow
```

### Pull Requests

- All changes must be developed on feature branches (not directly on `main`)
- Submit changes via PR to `main`
- PR titles should follow conventional commit format

## Documentation Maintenance

When making changes to the codebase, ensure relevant documentation is kept up to date:

- **DESIGN.md**: Update when making architectural changes, adding new components, or modifying system design
- **README.md**: Update when adding new features, changing installation steps, or modifying usage instructions

Documentation updates should be included in the same PR as the code changes they describe.
