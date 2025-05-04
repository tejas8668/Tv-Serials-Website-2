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

    def _ensure_connection(self):
        """Ensure MongoDB connection exists and is alive"""
        if self.client is None:
            self._init_connection()
        else:
            try:
                # Ping to check connection
                self.client.admin.command('ping')
            except Exception:
                logger.warning("MongoDB connection lost, reconnecting...")
                self._init_connection()
    
    def _init_connection(self):
        """Initialize MongoDB connection with retries"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Connection pool settings
                self.client = MongoClient(
                    os.getenv("MONGO_URI"),
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
                logger.info("Successfully connected to MongoDB")
                
                self.db = self.client["telegram_bot_db"]
                self.collection = self.db["files"]
                
                # Ensure index exists
                self.collection.create_index([("file_number", DESCENDING)])
                break
                
            except ConnectionFailure as e:
                if attempt == max_retries - 1:
                    logger.error(f"Could not connect to MongoDB after {max_retries} attempts: {str(e)}")
                    raise
                logger.warning(f"Connection attempt {attempt + 1} failed, retrying...")
                time.sleep(1)

    def fetch_files(self, page, posts_per_page):
        """Fetch files with pagination"""
        self._ensure_connection()
        
        max_retries = 3
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
                
            except AutoReconnect as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to fetch files after {max_retries} attempts: {str(e)}")
                    raise
                logger.warning(f"Query attempt {attempt + 1} failed, retrying...")
                time.sleep(1)
            except Exception as e:
                logger.error(f"Unexpected error fetching files: {str(e)}")
                raise

    def _get_total_count(self):
        """Get total count with caching"""
        self._ensure_connection()
        
        current_time = datetime.now()
        if self._cache_time and current_time - self._cache_time < self._cache_duration:
            return self._latest_number
            
        # Update cache using fast count with hint
        count = self.collection.count_documents({}, hint="file_number_-1")
        self._latest_number = count
        self._cache_time = current_time
        return count
