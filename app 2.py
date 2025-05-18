from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Optional
import uvicorn
import os
from chatbox import ArticleChatbot, list_available_articles

# Get port from environment variable (Cloud Run sets this)
PORT = int(os.getenv("PORT", 8080))

app = FastAPI(
    title="Article Chatbot API",
    description="API for chatting about articles",
    version="1.0.0"
)

class ChatRequest(BaseModel):
    article_id: str
    question: str

class ChatResponse(BaseModel):
    success: bool
    data: Optional[Dict] = None
    error: Optional[str] = None

class ArticleResponse(BaseModel):
    success: bool
    data: Dict
    error: Optional[str] = None

@app.get("/api/health", response_model=ChatResponse)
async def health_check():
    """Health check endpoint"""
    return ChatResponse(
        success=True,
        data={"status": "healthy"}
    )

@app.get("/api/chat", response_model=ChatResponse)
async def chat_get(article_id: str = Query(..., description="The ID of the article"), 
                  question: str = Query(..., description="The question to ask about the article")):
    """Chat about an article using GET method"""
    try:
        # Initialize chatbot with the article
        chatbot = ArticleChatbot(article_id=article_id)
        
        # Get response
        response = chatbot.chat_with_article(question)
        
        return ChatResponse(
            success=True,
            data={
                "response": response,
                "article_id": article_id,
                "question": question
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post("/api/chat", response_model=ChatResponse)
async def chat_post(request: ChatRequest):
    """Chat about an article using POST method"""
    try:
        # Initialize chatbot with the article
        chatbot = ArticleChatbot(article_id=request.article_id)
        
        # Get response
        response = chatbot.chat_with_article(request.question)
        
        return ChatResponse(
            success=True,
            data={
                "response": response,
                "article_id": request.article_id,
                "question": request.question
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.get("/api/articles", response_model=ArticleResponse)
async def list_articles():
    """Get list of all available articles"""
    try:
        articles = list_available_articles()
        
        if not articles:
            return ArticleResponse(
                success=True,
                data={"articles": [], "message": "No articles found"}
            )
        
        return ArticleResponse(
            success=True,
            data={"articles": articles}
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT) 