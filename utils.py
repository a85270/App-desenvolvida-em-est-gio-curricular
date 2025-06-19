from flask import current_app
import requests
from app.extensions import cache
from functools import wraps
from datetime import datetime, timedelta
from flask import has_app_context

API_KEY = '8fd6bb9dceb2add7beb67f7d666eb9a5'

def get_weather(city):
    base_url = "http://api.openweathermap.org/data/2.5/weather"
    complete_url = f"{base_url}?q={city}&appid={API_KEY}&units=metric"
    response = requests.get(complete_url)

    if response.status_code == 200:
        data = response.json()
        weather_info = {
            "temperatura": data["main"]["temp"],
            "descricao": data["weather"][0]["description"],
            "humidade": data["main"]["humidity"],
            "vento": data["wind"]["speed"]
        }
        return weather_info
    else:
        return {"erro": "Cidade Não encontrada ou problema com a API."}

def cached_time_margin(func):
    def times_overlap(intervalA: tuple[datetime, datetime],
                      intervalB: tuple[datetime, datetime]) -> bool:
        return (intervalA[0] <= intervalB[0] < intervalA[1] or
                intervalA[0] < intervalB[1] <= intervalA[1])
    
    def contains_times(interval: tuple[datetime, datetime],
                       inner_interval: tuple[datetime, datetime]) -> bool:
        return (interval[0] <= inner_interval[0] and
                inner_interval[1] <= interval[1] and
                interval[0].date() == inner_interval[0].date())
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Simplify positional arguments and extract times
        origin = args[0]["coordenadas"]
        destination = args[1]["coordenadas"]
        time_margin = args[2:4]     # departure, arrival
        timeless_args = (origin, destination) + args[4:]
        
        if origin == destination:
            # Skip invalid search
            return []

        times_cache_key = f"{func.__name__}:{timeless_args}:{kwargs}"
        make_timed_key = lambda time_margin: (times_cache_key +
            f"-{':'.join(t.strftime('%Y.%m.%d.%H:%M:%S') for t in time_margin)}"
        )
        
        # Only use cache if inside Flask app context
        if has_app_context():
            cache_key = make_timed_key(time_margin)
            cached_data = cache.get(cache_key)
        else:
            cached_data = None

        if cached_data is not None:
            current_app.logger.info("Cache used for key: %s", cache_key)
            return cached_data
        else:
            found = False
        
        if has_app_context():
            cached_times = cache.get(times_cache_key) or []
        else:
            cached_times = []
        updated_times = cached_times + [time_margin]
        results = []

        for time_input in cached_times:
            if times_overlap(time_input, time_margin):
                overlapping_cache = make_timed_key(time_input)
                if has_app_context():
                    cached_data = cache.get(overlapping_cache)
                else:
                    cached_data = None

                if cached_data is not None:
                    results.extend(cached_data)
                    
                    if contains_times(time_input, time_margin):
                        found = True
                        break

                    elif contains_times(time_margin, time_input):
                        if has_app_context():
                            cache.delete(overlapping_cache)
                        updated_times.remove(time_input)

                else:
                    # Cache in this time margin expired
                    updated_times.remove(time_input)

        if not found:
            new_results = func(*args, **kwargs)

            # Add results to cache for an hour
            if has_app_context():
                cache.set(cache_key, new_results, timeout=3600)
                # Update the times cache without expiration
                cache.set(times_cache_key, updated_times, timeout=0)

            results.extend(new_results)
            
        # Filter unique results within the time margin
        full_results = []
        for result in results:
            if contains_times(
                time_margin,
                (datetime.strptime(result["partida"], '%Y-%m-%d %H:%M:%S'),
                datetime.strptime(result["chegada"], '%Y-%m-%d %H:%M:%S'))
            ) and not any(result == other for other in full_results):
                full_results.append(result)

        return full_results

    return wrapper
