from flask import Flask, render_template, jsonify, request, current_app, send_from_directory
from .database import Database
import os
from dotenv import load_dotenv
from functools import wraps
from time import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('pymongo.ocsp_support').setLevel(logging.WARNING)
logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure for production
if os.environ.get('RENDER'):
    app.config['PREFERRED_URL_SCHEME'] = 'https'

# Configure static files cache
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 year in seconds

# Database will be initialized lazily by each worker
db = None

POSTS_PER_PAGE = 40

def get_db():
    global db
    if db is None:
        db = Database()
    return db

@app.before_request
def check_database():
    try:
        get_db()
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        return jsonify({"error": "Database connection not available"}), 503

@app.after_request
def add_cache_headers(response):
    # Cache static files
    if request.path.startswith('/static/'):
        response.cache_control.public = True
        response.cache_control.max_age = 31536000  # 1 year
        response.headers['Vary'] = 'Accept-Encoding'
    return response

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.png',
        mimetype='image/png'
    )

def timing_decorator(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        start = time()
        result = f(*args, **kwargs)
        end = time()
        logger.info(f'{f.__name__} took {end - start:.2f} seconds')
        return result
    return wrapper

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/files')
@timing_decorator
def get_files():
    try:
        page = int(request.args.get('page', 1))
        logger.debug(f'Requesting page {page}')
        
        if page < 1:
            return jsonify({"error": "Page number must be positive"}), 400
            
        result = get_db().fetch_files(page, POSTS_PER_PAGE)
        
        if not result['data']:
            logger.warning('No data found in database')
            return jsonify({"error": "No files found"}), 404
            
        return jsonify(result)
        
    except ValueError as e:
        logger.error(f'Invalid page number: {str(e)}')
        return jsonify({"error": "Invalid page number"}), 400
    except Exception as e:
        logger.error(f'Error fetching files: {str(e)}', exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(debug=True)
