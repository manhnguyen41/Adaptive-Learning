"""
Main API application
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.diagnostic_api import router as diagnostic_router
from api.diagnostic_session_api import router as diagnostic_session_router

app = FastAPI(
    title="Adaptive Learning Diagnostic Test API",
    description="API để sinh ra bộ câu hỏi đánh giá năng lực ban đầu",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(diagnostic_router)
app.include_router(diagnostic_session_router)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Adaptive Learning Diagnostic Test API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

