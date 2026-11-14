# UI guidelines

This page sets which control each kind of action takes in the web app, and how its icons
are drawn. A new screen follows it, so that one action looks the same on every screen.

Without written rules, each screen decides again. The same action then ends up as a
filled button on one page and a link on the next, and a phone shows rows of worded
buttons that wrap onto three lines.

The sizes, colours and spacing come from the tokens at the top of `app.css`.
`tests/web/test_stylesheet_tokens.py` fails on a literal value outside them.

## Controls

| Control        | Markup                          | When it fits                                      | Examples                                      |
| -------------- | ------------------------------- | ------------------------------------------------- | --------------------------------------------- |
| Tool           | `.btn.tool` in a `.toolbar`     | Several actions on one object                     | Supprimer, Scinder, Lier…                     |
| Button         | `.btn`, icon left of the label  | One action, next to what it acts on               | Modifier on Historique, Synchroniser          |
| Primary button | `.btn.primary`                  | The submit of a form, or the answer to a question | Confirmer, Importer, Scinder under its fields |
| Danger         | `.danger` on a tool or a button | An action that deletes or drops something         | Supprimer, Oublier, Délier                    |
| Action link    | `.action-link`                  | An action written as words in a sentence          | "Lier à « Loyer »"                            |
| Back link      | `back(url, label)`              | The top of a page opened from another             | Retour                                        |
| Filter button  | `filter_toggle(count)`          | A list page with more filters than a search       | Opérations, Budgets                           |

A tool has no fill, so a toolbar reads as one row. A filled button is kept for the
moment the user commits, after a form or a question.

## Forms and detail pages

A form puts each label above its field, such as the edit page of a budget. A field then
takes the whole width of a phone, which a date or an amount needs.

A detail page puts each label beside its value, in a `.detail-grid`, such as the page of
an operation. Its values are short and mostly read, so one line each keeps the page to a
glance. A value that is also a control, such as the category select, stays on its line.

## Toolbars

A toolbar holds the actions on one object, as the last thing on its card. For example,
the edit page of a budget ends on Supprimer, Terminer, Scinder, Historique and
Enregistrer.

- **Put the destructive action first and the expected one last.** Supprimer sits at the
  left, furthest from Enregistrer, which the thumb reaches first.
- **Keep it to one line down to 360 px.** The tools share the width equally, so five is
  the limit, and each label is one word.
- **End a label with "…" when the action opens a choice.** "Lier…" opens a picker, while
  "Lier" links at once.
- **Mark the toolbar `data-confirm-strip`.** A question asked by one tool then hides the
  others until it is answered or cancelled.
- **Put a section that opens in place, such as the split, in a `<details>`.** Opened, it
  hides the other tools and takes the whole width.

## Icons

Every icon is drawn once, in `templates/macros/icons.html`. A template imports the macro
and calls it by name:

```jinja
{% from "macros/icons.html" import icon with context %}
<a class="btn tool" href="...">{{ icon("link") }}<span>{{ _("Link…") }}</span></a>
```

An icon is a line drawing on a 24-unit grid, with a stroke of 2, in the text colour. It
therefore takes the colour of its button: red on a danger tool, blue elsewhere.

**An icon always has a visible label.** It sits above the label in a tool, and to its
left everywhere else. An icon alone is a guess on a phone, where no tooltip appears on
hover. The one exception is an action repeated on every row of a table, such as
downloading a backup: the icon stands alone and carries an `aria-label`.

**One action has one icon, everywhere.**

| Icon       | Action       |
| ---------- | ------------ |
| `add`      | Ajouter      |
| `back`     | Retour       |
| `delete`   | Supprimer    |
| `download` | Télécharger  |
| `edit`     | Modifier     |
| `end`      | Terminer     |
| `filter`   | Filtrer      |
| `forget`   | Oublier      |
| `history`  | Historique   |
| `import`   | Importer     |
| `link`     | Lier         |
| `plan`     | Prévoir      |
| `postpone` | Reporter     |
| `save`     | Enregistrer  |
| `split`    | Scinder      |
| `sync`     | Synchroniser |
| `unlink`   | Délier       |

A new action that needs an icon gets a new entry in the macro and a row in this table.
`tests/web/test_icons.py` fails when a template calls a name the macro does not draw, or
draws an icon of its own.

## Questions

A question that confirms an action uses words, not icons. It names the consequence, such
as "L'oublier ? 180,00 EUR reviennent dans votre marge.", then offers **Annuler** and a
**Confirmer** in the colour of the action. The question takes the place of the toolbar
or strip that asked it, through `confirm.js`.

## Filters

A list page keeps its search in sight and folds the other filters behind **Filtrer**.
The number on the button counts the filters changed from their default, so a short list
does not pass for the whole ledger. While that number is above zero, the page opens with
the filters unfolded. `filters.js` keeps the number current as the filters change. A
checkbox ticked by default, such as "Actifs seulement", carries `data-filter-default`,
so it counts once it is unticked. A plain GET form with no submit button carries
`data-autosubmit`, and applies a picked option or a tick at once; its search applies on
Enter.
