import os
import requests
import redis
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Set up the limiter configuration for rate limiting
app.config['FLASK_LIMITER_KEY_FUNC'] = get_remote_address

# Initialize Limiter with Flask app
limiter = Limiter(app)

# Get API Key from .env
API_KEY = os.getenv("WEATHER_API_KEY")
BASE_URL = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"

# Connect to Redis
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

@app.route('/weather', methods=['GET'])
@limiter.limit("5 per minute")  # Limit to 5 requests per minute
def get_weather():
    """Fetch real-time weather data with caching and rate limiting."""
    city = request.args.get('city', 'San Francisco').strip().lower()

    if not API_KEY:
        return jsonify({"error": "API key not found"}), 500

    # Check if weather data is cached
    cached_weather = redis_client.get(city)
    if cached_weather:
        return jsonify({"source": "cache", **eval(cached_weather)})

    # If not cached, fetch from API
    url = f"{BASE_URL}/{city}?unitGroup=metric&key={API_KEY}&contentType=json"

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for 4xx/5xx status codes

        data = response.json()

        if "days" not in data:
            return jsonify({"error": "Invalid city name or API error"}), 400

        # Extract relevant data
        weather_info = {
            "city": city.title(),
            "temperature": f"{data['days'][0]['temp']}°C",
            "description": data['days'][0]['conditions']
        }

        # Store in Redis with 12-hour expiration
        redis_client.setex(city, 12 * 60 * 60, str(weather_info))

        return jsonify({"source": "API", **weather_info})

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Weather API request failed", "message": str(e)}), 500
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
