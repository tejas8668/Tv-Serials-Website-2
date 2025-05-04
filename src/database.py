from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure, AutoReconnect
import os
from datetime import datetime, timedelta
import logging
import time
import threading

logger = logging.getLogger(__name__)

class Database:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(Database, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.client = None
        self.db = None
        self.collection = None
        self._latest_number = None
        self._cache_time = None
        self._cache_duration = timedelta(minutes=5)
        
        # Initialize connection immediately
        self._init_connection()

    def _ensure_connection(self):
        """Ensure MongoDB connection exists and is alive"""
        try:
            if self.client is None or self.collection is None:
                self._init_connection()
                return
            
            # Test connection
            self.client.admin.command('ping')
        except Exception as e:
            logger.warning(f"MongoDB connection check failed: {str(e)}, reconnecting...")
            self._init_connection()

    def _init_connection(self):
        """Initialize MongoDB connection with retries"""
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                if self.client:
                    try:
                        self.client.close()
                    except:
                        pass
                
                mongo_uri = os.getenv("MONGO_URI")
                if not mongo_uri:
                    raise ValueError("MONGO_URI environment variable is not set")
                
                # Connection pool settings
                self.client = MongoClient(
                    mongo_uri,
                    maxPoolSize=10,
                    minPoolSize=1,
                    maxIdleTimeMS=45000,
                    connectTimeoutMS=5000,
                    serverSelectionTimeoutMS=5000,
                    retryWrites=True,
                    retryReads=True,
                    w='majority',
                    socketTimeoutMS=10000,
                    connect=False  # Defer actual connection
                )
                
                # Test connection
                self.client.admin.command('ping')
                
                # Initialize database and collection
                self.db = self.client.get_database("telegram_bot_db")
                self.collection = self.db.get_collection("files")
                
                # Verify collection exists and is accessible
                self.collection.find_one()
                
                # Ensure index exists
                self.collection.create_index([("file_number", DESCENDING)])
                
                logger.info("Successfully connected to MongoDB and initialized collection")
                return
                
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    logger.warning(f"Connection attempt {attempt + 1} failed: {last_error}, retrying...")
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
        
        # If we get here, all retries failed
        logger.error(f"Could not connect to MongoDB after {max_retries} attempts. Last error: {last_error}")
        raise ConnectionFailure(f"Failed to establish MongoDB connection: {last_error}")

    def fetch_files(self, page, posts_per_page):
        """Fetch files with pagination"""
        self._ensure_connection()
        
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
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
                
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    logger.warning(f"Query attempt {attempt + 1} failed: {last_error}, retrying...")
                    self._ensure_connection()  # Ensure connection is alive before retry
                    time.sleep(1)
                    continue
                
                logger.error(f"Failed to fetch files after {max_retries} attempts: {last_error}")
                raise

    def _get_total_count(self):
        """Get total count with caching"""
        self._ensure_connection()
        
        current_time = datetime.now()
        if self._cache_time and current_time - self._cache_time < self._cache_duration:
            return self._latest_number
        
        try:
            # Update cache using fast count with hint
            count = self.collection.count_documents({})
            self._latest_number = count
            self._cache_time = current_time
            return count
        except Exception as e:
            logger.error(f"Error getting total count: {str(e)}")
            # Return cached value if available, otherwise raise
            if self._latest_number is not None:
                return self._latest_number
            raise
