# Prompts package

# ---------------------------------------------------------------------------
# Memex Response Style Policy
# ---------------------------------------------------------------------------
# Emojis, emoticons, and decorative Unicode are opt-in — they belong to the
# user's domain (MCPs, skills, apps being built), not to Memex's own voice.
# Every agent system prompt should include this rule.  Use apply_style_policy()
# to prepend it rather than copy-pasting, so the wording stays consistent.
# ---------------------------------------------------------------------------

MEMEX_STYLE_POLICY = (
    "RESPONSE STYLE: Do not use emojis, emoticons, or decorative Unicode symbols "
    "(e.g. ✅ ❌ 🚀 ⚡ →→ ★) in your responses. Convey status, structure, and "
    "emphasis through plain prose and standard Markdown only — headers, bold, "
    "bullet lists, code blocks, blockquotes. This rule applies to your own output; "
    "it does not restrict content you generate *for* the user (e.g. code, HTML, "
    "copy for an app) when emojis are explicitly requested or appropriate there."
)


def apply_style_policy(instructions: str) -> str:
    """Prepend the Memex style policy to an agent's instruction string."""
    return f"{MEMEX_STYLE_POLICY}\n\n{instructions}"
