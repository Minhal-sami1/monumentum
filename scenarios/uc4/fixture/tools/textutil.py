"""Text utilities used by the fixture project. Loop-managed (capability)."""


def slugify(title):
    """Lowercase, spaces to hyphens, strip other punctuation."""
    out = []
    for ch in title.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_"):
            out.append("-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")
