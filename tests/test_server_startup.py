"""
Simple startup script to test the API server initialization.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

import pytest


@pytest.mark.asyncio
async def test_server_startup():
    """Test that the API server components can be imported and initialized."""
    try:
        print("🧪 Testing API Server Components...")
        
        # Test imports
        print("1. Testing imports...")
        from api_server import app, get_agent
        from evolving_agent.core.agent import SelfImprovingAgent
        print("✅ All imports successful")
        
        # Test agent initialization
        print("2. Testing agent initialization...")
        agent = SelfImprovingAgent()
        await agent.initialize()
        print("✅ Agent initialized successfully")
        
        # Test FastAPI app
        print("3. Testing FastAPI app...")
        print(f"✅ FastAPI app created: {app.title}")
        print(f"   Version: {app.version}")
        print(f"   Routes: {len(app.routes)}")
        
        # List available routes
        print("\n📋 Available API Routes:")
        for route in app.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                methods = ', '.join(route.methods)
                print(f"   {methods:20} {route.path}")
        
        print("\n🎉 API server components are ready!")
        print("\nTo start the server manually:")
        print("   python -m uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload")
        
        print("\nTo access documentation:")
        print("   Swagger UI: http://localhost:8000/docs")
        print("   ReDoc: http://localhost:8000/redoc")
        
        # Cleanup
        await agent.cleanup()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_server_startup())
    sys.exit(0 if success else 1)
