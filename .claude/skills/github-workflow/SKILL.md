---
name: github-workflow
description: Comprehensive terminal workflow for managing Pull Requests, Issues, Releases, and GitHub Actions via GitHub CLI (gh)
tools: Bash
user-invocable: true
disable-model-invocation: false
---

# GitHub CLI (`gh`) Terminal Workflow

Manage Pull Requests, Issues, Releases, and CI/CD pipelines directly from the terminal without leaving your workflow.

## 1. Pull Requests (PR)

### Create a Pull Request
Always run invariant verification before creating a PR:
```bash
# Using the native project helper (recommended):
python3 scripts/pr.py create --task T-xxx --title "Brief summary of change" --body "Details..."

# Or using raw gh CLI:
python3 scripts/verify.py
gh pr create --title "[T-xxx] Title" --body "Description" --draft
# Or auto-fill from commit message:
gh pr create --fill
```

### Inspect & Review PRs
```bash
# Check status of PR for current branch
python3 scripts/pr.py status
# or
gh pr status

# View PR diff in terminal
python3 scripts/pr.py diff
# or
gh pr diff

# Checkout a PR locally to test
gh pr checkout <PR_NUMBER>

# View PR details and comments
gh pr view <PR_NUMBER> --comments

# Review and approve a PR
gh pr review <PR_NUMBER> --approve -b "LGTM, verified against test suite"
```

### Check CI & Merge
```bash
# Check CI status
python3 scripts/pr.py checks
# or live watch
gh pr checks --watch

# Merge PR (Squash & delete branch)
python3 scripts/pr.py merge
# or
gh pr merge <PR_NUMBER> --squash --delete-branch
```

---

## 2. Issues

```bash
# List open issues
gh issue list

# View issue details
gh issue view <ISSUE_NUMBER>

# Create a new issue
gh issue create --title "Issue title" --body "Issue description"

# Close an issue
gh issue close <ISSUE_NUMBER>
```

---

## 3. GitHub Actions (CI/CD)

```bash
# List recent workflow runs
gh run list

# Watch a running workflow live in terminal
gh run watch

# View logs for failed jobs without opening browser
gh run view --log-failed

# Trigger a workflow manually
gh workflow run <WORKFLOW_NAME>
```

---

## 4. Releases

```bash
# List releases
gh release list

# Create a new release with auto-generated changelog notes
gh release create v1.0.0 --generate-notes --title "Release v1.0.0"
```
