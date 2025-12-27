# Contributing

This repo is used as a demo + reference implementation, but we still want a clean history and safe releases.

## Workflow (required)

- **Do not push directly to `master`.**
- Create a **feature branch** from `master` and open a **Pull Request**.
- Prefer **small, focused PRs** (easy review + rollback).

### Typical flow

```bash
git checkout master
git pull --ff-only

git checkout -b feat/<short-topic>
# make changes

git status
git commit -m "<type>(<scope>): <message>"

git push -u origin HEAD
```

Open a PR from your branch into `master`.

## Commit messages

Use a conventional, descriptive format:

- `feat(scope): ...`
- `fix(scope): ...`
- `docs: ...`
- `chore: ...`

Examples:

- `feat(bootstrap): add guarded first-superuser setup via SPA`
- `feat(c2b): support per-shortcode STK push and tenancy attribution`

## Tests

Before opening a PR, run the relevant tests:

```bash
source .venv/bin/activate
python manage.py test
```

## Releases / branch protection (recommended)

To enforce this workflow, enable branch protection for `master` in GitHub:

1. Repo → **Settings** → **Branches**
2. **Add branch protection rule** for `master`
3. Enable:
   - **Require a pull request before merging**
   - **Require status checks to pass before merging** (select your CI checks)
   - (Optional) **Require approvals** (e.g. 1)
   - (Optional) **Restrict who can push to matching branches**

This prevents accidental direct pushes to `master`.
