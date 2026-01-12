# Commit Changes

Create a well-formatted git commit.

## Instructions

1. Check the current status and diff:

```bash
git status
git diff --staged
```

2. If nothing is staged, ask what should be committed

3. Write a commit message following conventional commits:

   - `feat:` new feature
   - `fix:` bug fix
   - `refactor:` code refactoring
   - `test:` adding tests
   - `docs:` documentation

4. Create the commit:

```bash
git commit -m "type: description

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

5. Show the result with `git log -1`

$ARGUMENTS
