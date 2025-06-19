import sys
import os
from flask_caching import Cache

# Add parent directory of this project to the Python module search path (sys.path);
# where the flask_gmaps_cache local extension could be found.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from flask_gmaps_cache import GMapsCachedWrapper

gmaps_wrapper = GMapsCachedWrapper()
cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})
