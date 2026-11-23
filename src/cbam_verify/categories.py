"""CN code -> aggregated goods category, following Table 1 of Implementing Regulation
(EU) 2025/2547 for iron and steel and aluminium. The longest matching prefix wins."""

CATEGORY_PREFIXES = [
    ("26011200", "sintered ore"),
    ("7201", "pig iron"),
    ("72021", "FeMn"),
    ("72024", "FeCr"),
    ("72026", "FeNi"),
    ("7203", "DRI"),
    ("7206", "crude steel"),
    ("7207", "crude steel"),
    ("7218", "crude steel"),
    ("7224", "crude steel"),
    ("72", "iron or steel products"),
    ("73", "iron or steel products"),
    ("7601", "unwrought aluminium"),
    ("76", "aluminium products"),
]


def goods_category(cn):
    """Return the goods category of a CN code (any length), or '' if none applies."""
    cn = str(cn).replace(" ", "")
    best = ""
    best_len = -1
    for prefix, cat in CATEGORY_PREFIXES:
        if cn.startswith(prefix) and len(prefix) > best_len:
            best, best_len = cat, len(prefix)
    return best


def sector(cn):
    cn = str(cn).replace(" ", "")
    if cn.startswith("76"):
        return "aluminium"
    if cn.startswith(("72", "73", "260112")):
        return "iron and steel"
    return ""
