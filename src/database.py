from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure, AutoReconnect
import os
from datetime import datetime, timedelta
import logging
import time
import threading
from functools import wraps

logger = logging.getLogger(__name__)

def with_retry(max_retries=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))
                        continue
                    raise last_error
        return wrapper
    return decorator

class Database:
    _instance = None
    _lock = threading.Lock()
    _pid = None
    
    def __new__(cls):
        if cls._instance is None or cls._pid != os.getpid():
            with cls._lock:
                if cls._instance is None or cls._pid != os.getpid():
                    cls._instance = super(Database, cls).__new__(cls)
                    cls._instance._initialized = False
                    cls._pid = os.getpid()
        return cls._instance

    def __init__(self):
        if self._initialized and self._pid == os.getpid():
            return
            
        self._initialized = True
        self.client = None
        self.db = None
        self.collection = None
        self._latest_number = None
        self._cache_time = None
        self._cache_duration = timedelta(minutes=5)
        
        # Don't initialize connection in __init__
        # Let it be created on first use

    @with_retry(max_retries=3, delay=1)
    def _ensure_connection(self):
        """Ensure MongoDB connection exists and is alive"""
        # Check if we need to create a new connection after fork
        if self.client is None or self._pid != os.getpid():
            self._init_connection()
            return

        try:
            # Quick connection check
            self.client.admin.command('ping')
        except Exception as e:
            logger.warning(f"MongoDB connection check failed: {str(e)}, reconnecting...")
            self._init_connection()

    def _init_connection(self):
        """Initialize MongoDB connection"""
        if self.client:
            try:
                self.client.close()
            except:
                pass

        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise ValueError("MONGO_URI environment variable is not set")

        # Optimized connection settings for Render's free tier
        self.client = MongoClient(
            mongo_uri,
            maxPoolSize=5,  # Reduced for free tier
            minPoolSize=0,  # Allow pool to shrink when idle
            maxIdleTimeMS=30000,  # 30 seconds
            connectTimeoutMS=5000,
            serverSelectionTimeoutMS=5000,
            retryWrites=True,
            retryReads=True,
            w='majority',
            socketTimeoutMS=10000,
            connect=True  # Make immediate connection
        )

        # Initialize database and collection
        self.db = self.client.get_database("telegram_bot_db")
        self.collection = self.db.get_collection("files")
        
        # Update process ID
        self._pid = os.getpid()
        
        # Ensure index exists
        self.collection.create_index([("file_number", DESCENDING)])
        logger.info("Successfully connected to MongoDB and initialized collection")

    @with_retry(max_retries=3, delay=1)
    def fetch_files(self, page, posts_per_page):
        """Fetch files with pagination"""
        self._ensure_connection()
        
        total_items = self._get_total_count()
        logger.info(f"Fetching page {page}, total items: {total_items}")
        
        start_number = total_items - (page - 1) * posts_per_page
        end_number = max(1, start_number - posts_per_page + 1)
        
        data = list(
            self.collection.find(
                {"file_number": {"$gte": end_number, "$lte": start_number}},
                {
                    "_id": 0,
                    "file_number": 1,
                    "file_name": 1,
                    "share_link": 1,
                    "image_url": 1,
                    "file_size": 1
                }
            ).sort("file_number", -1)
        )
        
        logger.info(f"Found {len(data)} documents for page {page}")
        if data:
            logger.info(f"First document in results: {data[0]}")

        total_pages = (total_items + posts_per_page - 1) // posts_per_page

        return {
            "data": data,
            "total_items": total_items,
            "total_pages": total_pages,
            "current_page": page
        }

    @with_retry(max_retries=3, delay=1)
    def _get_total_count(self):
        """Get total count with caching"""
        self._ensure_connection()
        
        current_time = datetime.now()
        if self._cache_time and current_time - self._cache_time < self._cache_duration:
            return self._latest_number
        
        count = self.collection.count_documents({})
        self._latest_number = count
        self._cache_time = current_time
        return count
