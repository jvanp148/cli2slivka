# ===========================================================================
# Utility helpers
# ===========================================================================
import re

# Just to make the titles and other text more how it should be in YAML
def slugify(text: str) -> str:
    """'Gap open penalty' -> 'gap-open-penalty'"""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text


def strip_macro_placeholders(text: str) -> str:
    """Remove Galaxy macro tokens like @VERSION@ or @TOOL_VERSION@."""
    return re.sub(r"@[\w_]+@", "", text).strip("+. ")