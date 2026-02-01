# AGENT.md

This file provides guidance to AI AGENT when working with code in this repository.

## Project Overview

## Development Life Cycle
- **Implement TDD**: create tests for new functionality and bug fixes
- **Validate**: Run linting and unit tests before commit 

## Build and Development Key Commands

- **Test:** 'make test'
- **Lint:** 'make link'
- **Test:** 'make test'

## Testing

## Git Workflow

### Branch Naming

- `fix/` - bug fixes (e.g., `fix/jira-search-issues`)
- `feature/` - new features (e.g., `feature/add-priority-sync`)
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
fix(jira): use enhanced search API for issues
feat(sync): add component mapping support
docs: update AGENT.md with git workflow
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
