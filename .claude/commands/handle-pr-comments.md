# Handle PR Comments

Address review comments on a GitHub pull request interactively.

## Arguments

- `$ARGUMENTS`: PR number or URL (e.g., `200` or
  `https://github.com/user/repo/pull/200`)

## Workflow

### Phase 1: Collect and Analyze

1. **Extract PR number** from arguments (strip URL if needed)

2. **Fetch unresolved review comments**:

```bash
# Get review comments (inline comments on code)
gh api repos/{owner}/{repo}/pulls/<number>/comments \
  --jq '.[] | {id, user: .user.login, path, line, body}'

# Get issue comments (general discussion)
gh api repos/{owner}/{repo}/issues/<number>/comments \
  --jq '.[] | {id, user: .user.login, body}'
```

3. **Present a summary** of all comments to the user:
   - Comment number, author, file/line, and summary
   - Group by topic if related
   - Distinguish inline (code) comments from general comments

### Phase 2: Process Each Comment

For each comment, **one at a time**:

1. **Read the relevant code** to understand the context
2. **Propose a solution**:
   - If code change needed: describe the change
   - If just a response needed: draft the response
   - If disagreement: explain the tradeoff and let the user decide
3. **Wait for user validation** before proceeding
4. **Apply the change** if approved (code modification)
5. Move to the next comment

### Phase 3: Commit and Push

After all comments are addressed:

1. **Run tests** to ensure nothing is broken
2. **Commit** with a descriptive message summarizing all changes
3. **Push** to the remote branch

### Phase 4: Reply to Comments

For each comment that was addressed:

1. **Draft a response** explaining what was done
2. **Wait for user validation** before sending
3. **Post the reply** using:

```bash
# Reply to an inline review comment
gh api repos/{owner}/{repo}/pulls/<number>/comments/<comment_id>/replies \
  -X POST \
  -f body="🤖 Claude: <response>"

# Reply to a general issue comment
gh api repos/{owner}/{repo}/issues/<number>/comments \
  -X POST \
  -f body="🤖 Claude: <response>"
```

## Response Guidelines

- **Be concise**: explain what was done, not why it was requested
- **Reference the change**: mention new function/test names if relevant
- **Prefix with**: `🤖 Claude:`
- **Reference commits**: include commit hash when relevant

## Example Responses

### Code change applied

> 🤖 Claude: Fixed in abc1234. Renamed `match_heuristic` to `__match_heuristic` and
> updated tests to use the public `match()` API.

### Refactoring declined (with explanation)

> 🤖 Claude: Keeping the current approach. A `NamedTuple` would add more code for only 3
> call sites, while the explicit calls are more readable.

### Simple fix

> 🤖 Claude: Fixed in abc1234. Renamed to `test_migration_is_idempotent`.

### Phase 5: Introspection

After all comments are replied to, **reflect on the review**:

1. **Identify patterns** in the feedback:

   - What mistakes were repeated?
   - What conventions were violated?
   - What could have been caught earlier?

2. **Propose rule updates** if relevant:

   - `.claude/rules/` for coding patterns
   - `.claude/commands/` for workflow improvements
   - `CLAUDE.md` for project-specific knowledge

3. **Ask user** before applying any config changes

Example patterns to look for:

- Redundant comments → update `python-quality.md`
- Missing test cases → update `testing.md`
- Naming conventions → update relevant rule file
- Over-engineering → update `CLAUDE.md`

## Key Principles

1. **One comment at a time** - Don't batch process, let user validate each step
2. **Propose before acting** - Always get approval before code changes
3. **Test before commit** - Run tests after all changes are applied
4. **Validate before posting** - Let user approve each GitHub reply
5. **Learn from feedback** - Update rules to prevent future similar comments

$ARGUMENTS
