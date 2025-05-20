def normalize_symbol(symbol: str) -> str:
    if symbol.endswith(".P"):
        return symbol[:-2]  # просто обрезаем ".P"
    return symbol
