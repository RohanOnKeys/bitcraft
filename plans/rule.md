
# BitCraft Rules

**BitCraft**

AI Powered Monitoring & Analysis of Bitcoin Transaction Traffic Software

Move fast during development. Stay strict with documentation, Git hygiene, and code quality.

---

# Documentation Rules

- RULE-DOC-001: Write docstrings for all API endpoints, routes, and most functions.
- RULE-DOC-002: If a docstring does not fit, explain the function with comments.
- RULE-DOC-003: Document complex logic so the reason behind it is clear.

---

# Code Rules

- RULE-CODE-001: Regularly remove redundant routes and folders.
- RULE-CODE-002: Always gitignore `.env` files.
- RULE-CODE-003: Always gitignore `.temp` files and other local artifacts.
- RULE-CODE-004: Check `.gitignore` before every push.
- RULE-CODE-005: Every empty folder must contain a `.gitkeep` file before pushing.

---

# Repository Rules

- RULE-REPO-001: Keep every folder purposeful.
- RULE-REPO-002: Store documentation in `docs`.
- RULE-REPO-003: Store planning documents in `plans`.
- RULE-REPO-004: All folder names should be in plural e.g `plans` 
- RULE-REPO-005: All files must be named singular e.g `plan.md`

---

# Git Rules

## Branch Rules

- RULE-GIT-001: Never push directly to `main`.
- RULE-GIT-002: Create a separate branch for every feature, fix, or documentation change.
- RULE-GIT-003: Keep branches short lived and merge them quickly.
- RULE-GIT-004: Keep `main` stable and deployable.

## Commit Rules

- RULE-GIT-005: One logical change per commit.
- RULE-GIT-006: Keep commit messages short and in present tense.
- RULE-GIT-007: Use `git commit -s`  is required.
- RULE-GIT-008: Always use a standard commit type.

Standard commit types:

- `feat:` New feature
- `fix:` Bug fix
- `chore:` Maintenance
- `docs:` Documentation
- `refactor:` Code restructuring
- `perf:` Performance improvement
- `test:` Test changes
- `style:` Formatting only
- `ci:` CI/CD changes
- `build:` Build or dependency changes
- `revert:` Revert a previous commit

---

# PR Rules

- RULE-PR-001: Every change reaches `main` through a PR.
- RULE-PR-002: Keep each PR focused on one change.
- RULE-PR-003: Self review before merging.
- RULE-PR-004: Squash merge by default.

---

# Merge Rules

Merge only when:

- Documentation is complete.
- Formatting is clean.
- Links and paths work.
- The change has been self reviewed.
- `main` remains stable.

---

# Philosophy

- Document first.
- Keep Git history meaningful.
- Remove duplication.
- Prefer clarity over cleverness.
- Keep `main` production ready.