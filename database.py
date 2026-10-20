import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

Email_ServiceDATABASE_URL = os.getenv("EMAILSERVICEDATABASEURL")
JOB_BOARDDATABASE_URL = os.getenv("JOBBOARDDATBASEURL")

async def get_db_pool():
    """Creates and returns an async connection pool to Email/Subscriber DB."""
    if not Email_ServiceDATABASE_URL:
        raise ValueError("EMAILSERVICEDATABASEURL is not set in the environment variables.")
    return await asyncpg.create_pool(Email_ServiceDATABASE_URL)

async def get_jobboard_db_pool():
    """Creates and returns an async connection pool to Job Board DB."""
    if not JOB_BOARDDATABASE_URL:
        raise ValueError("JOBBOARDDATBASEURL is not set in the environment variables.")
    return await asyncpg.create_pool(JOB_BOARDDATABASE_URL)