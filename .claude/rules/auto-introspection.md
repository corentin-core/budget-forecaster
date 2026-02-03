# Auto-Introspection

## Trigger

This rule activates **automatically** when the user:

- Contradicts you ("non", "c'est faux", "tu as tort")
- Points out an error ("tu as fait une erreur", "c'est pas ça", "mauvaise analyse")
- Corrects your work ("ça sert à rien de...", "il fallait plutôt...")
- Expresses frustration with your output ("c'est nul", "recommence")

## Response Pattern

When triggered, **always** end your response with a proposal to update your config:

```markdown
---

**Proposition d'amélioration :**

J'ai fait l'erreur de [description concise]. Pour éviter ça à l'avenir :

- **Fichier à modifier** : `.claude/rules/X.md` | `.claude/skills/X/SKILL.md` |
  `CLAUDE.md`
- **Changement proposé** : [description du changement]

Veux-tu que j'applique cette modification ?
```

## Decision Tree

```
User points out error
  ↓
Is it a recurring pattern that could happen again?
  YES → Propose rule/skill update
  NO  → Just acknowledge and fix, no config change needed

What type of mistake?
  - Wrong process/workflow → Update skill (SKILL.md)
  - Missing knowledge about project → Update CLAUDE.md
  - Bad habit/pattern → Create/update rule (.claude/rules/)
```

## Examples

### Example 1: Workflow mistake

**User**: "ça sert à rien de relancer les tests en local, tu as la CI"

**Response should include**:

```markdown
---

**Proposition d'amélioration :**

J'ai fait l'erreur de lancer les tests localement alors que la CI fournit déjà ces
résultats. Pour éviter ça à l'avenir :

- **Fichier à modifier** : `.claude/skills/review/SKILL.md`
- **Changement proposé** : Ajouter une étape "Check CI status" et expliciter de NE PAS
  lancer les tests localement

Veux-tu que j'applique cette modification ?
```

### Example 2: Analysis mistake

**User**: "ton analyse est mauvaise, tu n'as pas regardé les lignes non couvertes"

**Response should include**:

```markdown
---

**Proposition d'amélioration :**

J'ai fait l'erreur de regarder les pourcentages globaux au lieu d'analyser les lignes
spécifiques non couvertes. Pour éviter ça à l'avenir :

- **Fichier à modifier** : `.claude/skills/review/SKILL.md`
- **Changement proposé** : Détailler l'analyse du coverage avec focus sur "Lines
  missing"

Veux-tu que j'applique cette modification ?
```

### Example 3: One-off mistake (no config change)

**User**: "tu as oublié un paramètre dans cet appel de fonction"

**Response**: Fix the mistake, but no config proposal needed (too specific, won't
recur).

## Important

- **Don't wait to be asked** - propose the improvement proactively
- **Be specific** - identify the exact file and change needed
- **Be concise** - the proposal should be 3-5 lines max
- **Ask permission** - never modify config without user approval
