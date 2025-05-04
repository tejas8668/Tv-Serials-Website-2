from flask import Flask, render_template, jsonify, request, current_app
from database import Database
import os
from dotenv import load_dotenv
from functools import wraps
from time import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
# Suppress MongoDB OCSP debug logs
logging.getLogger('pymongo.ocsp_support').setLevel(logging.WARNING)
logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure for production
if os.environ.get('RENDER'):
    app.config['PREFERRED_URL_SCHEME'] = 'https'

db = Database()

POSTS_PER_PAGE = 40

def timing_decorator(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        start = time()
        result = f(*args, **kwargs)
        end = time()
        current_app.logger.info(f'{f.__name__} took {end - start:.2f} seconds')
        return result
    return wrapper

@app.route('/')
def index():
    # Try a test query
    try:
        sample = db.collection.find_one()
        logger.info(f"Test query result: {sample}")
        if not sample:
            logger.error("No documents found in collection")
    except Exception as e:
        logger.error(f"Error during test query: {str(e)}")
    return render_template('index.html')

@app.route('/files')
@timing_decorator
def get_files():
    try:
        page = int(request.args.get('page', 1))
        logger.debug(f'Requesting page {page}')
        
        if page < 1:
            return jsonify({"error": "Page number must be positive"}), 400
            
        result = db.fetch_files(page, POSTS_PER_PAGE)
        logger.debug(f'Database returned: {result}')
        
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
    # Test database connection on startup
    try:
        test_result = db.collection.find_one()
        logger.info(f'Database test document: {test_result}')
        if test_result:
            logger.info(f'Available fields: {list(test_result.keys())}')
    except Exception as e:
        logger.error(f'Database connection failed: {str(e)}', exc_info=True)
    
    app.run(debug=True)