from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure
import os
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        # Connection pool settings
        self.client = MongoClient(
            os.getenv("MONGO_URI"),
            maxPoolSize=50,  # Maximum number of connections in the pool
            minPoolSize=10,  # Minimum number of connections in the pool
            maxIdleTimeMS=45000,  # Maximum time a connection can be idle (45 seconds)
            connectTimeoutMS=2000,  # Connection timeout (2 seconds)
            serverSelectionTimeoutMS=3000,  # Server selection timeout (3 seconds)
            retryWrites=True  # Enable automatic retry of writes
        )
        
        try:
            # Verify connection
            self.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
        except ConnectionFailure as e:
            logger.error(f"Could not connect to MongoDB: {str(e)}")
            
        self.db = self.client["telegram_bot_db"]
        self.collection = self.db["files"]
        
        # List all collections
        collections = self.db.list_collection_names()
        logger.info(f"Available collections: {collections}")
        
        # Ensure index exists for file_number
        self.collection.create_index([("file_number", DESCENDING)])
        
        # Cache variables
        self._latest_number = None
        self._cache_time = None
        self._cache_duration = timedelta(minutes=5)

    def _get_total_count(self):
        """Get total count with caching"""
        current_time = datetime.now()
        
        if self._cache_time and current_time - self._cache_time < self._cache_duration:
            return self._latest_number
            
        # Update cache using fast count with hint
        count = self.collection.count_documents({}, hint="file_number_-1")
        self._latest_number = count
        self._cache_time = current_time
        return count

    def fetch_files(self, page, posts_per_page):
        try:
            # Use MongoDB's cursor-based pagination with hint for better performance
            data = list(
                self.collection.find(
                    {},
                    {
                        "_id": 0,
                        "file_number": 1,
                        "file_name": 1,
                        "share_link": 1,
                        "image_url": 1,
                        "file_size": 1
                    }
                )
                .sort("file_number", -1)
                .skip((page - 1) * posts_per_page)
                .limit(posts_per_page)
                .hint([("file_number", -1)])  # Force index usage
            )
            
            # Get total count from cached value or update cache
            total_items = self._get_total_count()
            
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
            logger.error(f"Error fetching files: {str(e)}")
            raise