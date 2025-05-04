import os

class Config:
    MONGO_URI = os.getenv("MONGO_URI", "your_default_mongo_uri_here")
    POSTS_PER_PAGE = 40