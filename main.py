"""
GodView 应用入口
"""

from app.api.app import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    from app.config import settings

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
