import asyncio
from database import get_db_pool

async def create_tables():
    print("Connecting to Neon PostgreSQL...")
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        print("Creating 'subscribers' table if it doesn't exist...")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";") # or pgcrypto
        # SQL query to create the table
        # Job board update subs
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS jobboardsubscribers (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(255) UNIQUE NOT NULL,
                name VARCHAR(255)  ,
                mappedIdFromMainDb UUID UNIQUE,
                status VARCHAR(50) DEFAULT 'subscribed',
                type VARCHAR(255) DEFAULT 'jobsupdate',
                roleexperience VARCHAR(255) DEFAULT 'all',
                jobtype VARCHAR(255) DEFAULT 'all',
                country VARCHAR(255) DEFAULT 'all',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        print("Table 'job update subscribers' created successfully!")
        
    await pool.close()
    print("Database connection closed.")

if __name__ == "__main__":
    # Run the async function using asyncio
    asyncio.run(create_tables())