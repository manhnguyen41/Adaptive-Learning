"""
Main API application
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.diagnostic_api import router as diagnostic_router
from api.diagnostic_session_api import router as diagnostic_session_router
from api.passing_probability_api import router as passing_probability_router
from api.next_action_api import router as next_action_router
from api.shared import (
    load_questions_and_difficulties,
    load_progress_data,
    get_question_topic_map,
    get_topic_meta_map,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup và shutdown events"""
    print("Starting server - Loading data into cache...")
    
    try:
        print("Loading questions and difficulties...")
        questions, difficulties = load_questions_and_difficulties()
        print(f"Loaded {len(questions)} questions, {len(difficulties)} difficulties")
        
        print("Loading progress data...")
        progress_data = load_progress_data()
        print(f"Loaded progress data ({len(progress_data)} records)")
        
        print("Loading question topic map...")
        question_topic_map = get_question_topic_map()
        print(f"Loaded {len(question_topic_map)} question-topic mappings")
        
        print("Loading topic meta map...")
        topic_meta_map = get_topic_meta_map()
        print(f"Loaded {len(topic_meta_map)} topic metadata")
        
        print("All data loaded successfully! Server is ready.")
    except Exception as e:
        print(f"Error loading data: {str(e)}")
        raise
    
    yield
    
    # Shutdown
    print("Shutting down server...")


app = FastAPI(
    title="Adaptive Learning Diagnostic Test API",
    description="API để sinh ra bộ câu hỏi đánh giá năng lực ban đầu",
    version="1.0.0",
    lifespan=lifespan
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
app.include_router(passing_probability_router)
app.include_router(next_action_router)


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
