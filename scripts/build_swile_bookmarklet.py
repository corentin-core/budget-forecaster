#!/usr/bin/env python3
"""
Build script for the Swile export bookmarklet.

Reads swile_export.js, minifies it, and generates swile_bookmarklet.html
with the bookmarklet embedded for easy drag-and-drop installation.

Usage:
    python scripts/build_swile_bookmarklet.py
"""

import html
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
JS_SOURCE = SCRIPT_DIR / "swile_export.js"
HTML_OUTPUT = SCRIPT_DIR / "swile_bookmarklet.html"


def minify_js(source: str) -> str:
    """Basic JavaScript minification."""
    # Remove single-line comments (but not URLs with //)
    result = re.sub(r"(?<!:)//.*?$", "", source, flags=re.MULTILINE)
    # Remove multi-line comments
    result = re.sub(r"/\*[\s\S]*?\*/", "", result)
    # Remove leading/trailing whitespace per line
    result = "\n".join(line.strip() for line in result.splitlines())
    # Remove empty lines
    result = "\n".join(line for line in result.splitlines() if line)
    # Collapse whitespace around operators and punctuation
    result = re.sub(r"\s*([{}\[\]();,:<>?=+\-*/%&|^!~])\s*", r"\1", result)
    # Restore necessary spaces (after keywords)
    for keyword in (
        "const",
        "let",
        "var",
        "return",
        "throw",
        "new",
        "typeof",
        "async",
        "await",
        "function",
        "if",
        "else",
        "for",
        "while",
        "catch",
    ):
        result = re.sub(rf"\b{keyword}\b([^\s])", rf"{keyword} \1", result)
    # Remove newlines
    result = result.replace("\n", "")
    return result


def generate_html(bookmarklet_code: str) -> str:
    """Generate the HTML installation page."""
    # Escape for HTML attribute
    escaped_code = html.escape(bookmarklet_code, quote=True)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Swile Export - Installation du bookmarklet</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 600px;
            margin: 50px auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
        }}
        h1 {{ color: #1a1a2e; }}
        .bookmarklet {{
            display: inline-block;
            padding: 12px 24px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            font-size: 16px;
            margin: 20px 0;
            cursor: grab;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }}
        .bookmarklet:hover {{
            box-shadow: 0 6px 16px rgba(102, 126, 234, 0.6);
        }}
        .step {{
            background: #f5f5f5;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
        }}
        .step-number {{
            display: inline-block;
            width: 28px;
            height: 28px;
            background: #667eea;
            color: white;
            border-radius: 50%;
            text-align: center;
            line-height: 28px;
            margin-right: 10px;
            font-weight: bold;
        }}
        code {{
            background: #e8e8e8;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 14px;
        }}
        .warning {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 12px;
            margin: 15px 0;
        }}
    </style>
</head>
<body>
    <h1>Swile Export</h1>
    <p>Exporte tes operations Swile en un clic.</p>

    <h2>Installation</h2>
    <p>Glisse ce bouton dans ta barre de favoris :</p>

    <a class="bookmarklet" href="{escaped_code}">Swile Export</a>

    <p><small>(Si tu ne vois pas ta barre de favoris : <code>Ctrl+Shift+B</code>)</small></p>

    <h2>Utilisation</h2>

    <div class="step">
        <span class="step-number">1</span>
        Connecte-toi sur <a href="https://team.swile.co" target="_blank">team.swile.co</a>
    </div>

    <div class="step">
        <span class="step-number">2</span>
        Clique sur le bookmarklet "Swile Export" dans ta barre de favoris
    </div>

    <div class="step">
        <span class="step-number">3</span>
        Attends la fin de l'export (notification en haut a droite)
    </div>

    <div class="step">
        <span class="step-number">4</span>
        Deux fichiers sont telecharges : <code>operations.json</code> et <code>wallets.json</code>
    </div>

    <h2>Import dans budget-forecaster</h2>
    <p>Deplace les fichiers dans le dossier <code>swile/</code> puis :</p>
    <pre><code>python -m budget_forecaster.main -c config.yaml load swile/</code></pre>

    <div class="warning">
        <strong>Astuce :</strong> Configure Firefox pour telecharger directement dans <code>swile/</code>
        (Parametres &gt; Fichiers et applications &gt; Enregistrer les fichiers dans...)
    </div>
</body>
</html>
"""


def main() -> None:
    """Main entry point."""
    if not JS_SOURCE.exists():
        print(f"Error: {JS_SOURCE} not found")
        return

    print(f"Reading {JS_SOURCE}...")
    js_code = JS_SOURCE.read_text(encoding="utf-8")

    print("Minifying JavaScript...")
    minified = minify_js(js_code)
    bookmarklet = f"javascript:{minified}"

    print(f"Bookmarklet size: {len(bookmarklet)} characters")

    print(f"Generating {HTML_OUTPUT}...")
    html_content = generate_html(bookmarklet)
    HTML_OUTPUT.write_text(html_content, encoding="utf-8")

    print("Done!")


if __name__ == "__main__":
    main()
