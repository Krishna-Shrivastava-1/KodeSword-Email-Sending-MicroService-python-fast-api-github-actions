from fastapi import FastAPI
from database import get_db_pool, get_jobboard_db_pool
from routers import job_email,welcome_email

app = FastAPI()

@app.on_event("startup")
async def startup():
    # Store DB pools globally in FastAPI app state
    app.state.db_pool = await get_db_pool()
    app.state.jobboard_db_pool = await get_jobboard_db_pool()
    print("Database connection pools initialized successfully!")

@app.on_event("shutdown")
async def shutdown():
    if hasattr(app.state, "db_pool"):
        await app.state.db_pool.close()
    if hasattr(app.state, "jobboard_db_pool"):
        await app.state.jobboard_db_pool.close()
    print("Database connection pools closed.")

# Include the external route file cleanly!
app.include_router(job_email.router)
app.include_router(welcome_email.router)
@app.get("/health")
async def health_check():
    return {"status": "ok"}