# Простой кеш для FAJ Rating
rating_cache = {}

def update_rating(team: str, rating: float):
    rating_cache[team] = rating

def get_rating(team: str, default: float = 100) -> float:
    return rating_cache.get(team, default)
