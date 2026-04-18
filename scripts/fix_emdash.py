"""Fix mojibake em-dashes in training-report.tsx"""
import os

path = os.path.join(os.path.dirname(__file__), "..", "ui", "src", "components", "training", "training-report.tsx")

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace mojibake em-dash patterns with proper em-dash
original = content
content = content.replace("\u00e2\u0080\u201c", "\u2014")  # â€" -> —
content = content.replace("\u00e2\u0080\u201d", "\u2014")  # â€" variant -> —
content = content.replace("\u00e2\u0080\u0094", "\u2014")  # â€" -> —

# Also try the exact string from grep
content = content.replace("â\u0080\u201c", "\u2014")
content = content.replace("â\u0080\u201d", "\u2014")

# The pattern seen in grep: â€" (3 chars that are double-encoded em-dash)
content = content.replace("\u00e2\u20ac\u201c", "\u2014")
content = content.replace("\u00e2\u20ac\u201d", "\u2014")

# Most likely: the raw text "â€"" as 3 Unicode codepoints 
content = content.replace("\u00e2\u20ac\u0094", "\u2014")

changes = len(original) - len(content)
print(f"Characters changed: {changes}")

# Check if any â remain that look like mojibake
remaining = content.count("\u00e2")
print(f"Remaining â chars: {remaining}")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Done")
