Getting Started with opinionated_mcp
=====================================

**opinionated_mcp** is a zero-config OAuth framework for MCP (Model Context Protocol) servers that makes authentication simple and secure. This guide will get you to a working MCP server with user-specific data storage in just a few steps.

What You'll Build
-----------------

By the end of this guide, you'll have a working MCP server with:

- Two authenticated MCP tools: ``write_name(name)`` and ``read_name()``
- Authenticated web endpoints: ``GET /my-name`` and ``POST /my-name``
- User-specific data storage with automatic Google OAuth authentication

Each user's data is automatically isolated by their Google account through both the authenticated MCP tools and web endpoints.

Prerequisites
-------------

Before starting, you'll need:

1. Python 3.8+ installed
2. A Google account
3. 5 minutes to set up Google OAuth

Step 1: Installation
--------------------

Install opinionated_mcp::

    pip install opinionated_mcp

Step 2: Google OAuth Setup
---------------------------

You need a Google OAuth Client ID (no client secret required):

1. Go to the `Google Cloud Console <https://console.cloud.google.com/>`_
2. Create a new project or select an existing one
3. Enable the Google+ API (or Google Identity API)
4. Navigate to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
5. Set application type to "Web application"
6. Add authorized redirect URI: ``http://localhost:8000/callback``
7. Copy the Client ID (looks like: ``123456789-abc.apps.googleusercontent.com``)

Step 3: Create Your Server (or Use the Example)
------------------------------------------------

**Option A: Quick Test with Built-in Example**

If you want to immediately test opinionated_mcp without creating any files, you can run the included example directly::

    python -c "from opinionated_mcp.example import run_example_server; run_example_server('YOUR_GOOGLE_CLIENT_ID_HERE')"

Replace ``YOUR_GOOGLE_CLIENT_ID_HERE`` with your actual Google Client ID from step 2. This will start an "Example MCP Server" with two authenticated tools: ``write_name`` and ``read_name``. Skip to Step 5 to test your server.

**Option B: Create Your Own Server File**

Create a new file called ``server.py``:

.. code-block:: python

    from opinionated_mcp import OpinionatedMCP, generate_session_key
    from fastapi import Request, HTTPException

    # In-memory storage for user data (use a database in production)
    user_data = {}

    # Create the MCP server
    server = OpinionatedMCP(
        name="User Name Manager",
        google_client_id="YOUR_GOOGLE_CLIENT_ID_HERE",  # Replace with your Client ID
        session_key=generate_session_key(),
        base_url="http://localhost:8000"
    )

    @server.authenticated_tool(name="write_name", description="Store your name")
    def write_name(user_id: str, name: str) -> str:
        """Store the user's name. User ID is automatically provided."""
        user_data[user_id] = name
        return f"Stored name '{name}' for user {user_id}"

    @server.authenticated_tool(name="read_name", description="Get your stored name")
    def read_name(user_id: str) -> str:
        """Retrieve the user's stored name. User ID is automatically provided."""
        name = user_data.get(user_id, "No name stored")
        return f"Your stored name is: {name}"

    # For user-specific functionality, use authenticated endpoints
    @server.app.get("/my-name")
    async def get_my_name(request: Request):
        """Get the authenticated user's name"""
        user_id = server.oauth_handler.get_user_from_request(request)
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        name = user_data.get(user_id, "No name stored")
        return {"user_id": user_id, "name": name}

    @server.app.post("/my-name")
    async def set_my_name(request: Request, name: str):
        """Set the authenticated user's name"""
        user_id = server.oauth_handler.get_user_from_request(request)
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        user_data[user_id] = name
        return {"user_id": user_id, "name": name, "message": f"Stored name '{name}'"}

    if __name__ == "__main__":
        server.run(debug=True)

**Important**: Replace ``YOUR_GOOGLE_CLIENT_ID_HERE`` with your actual Google Client ID from step 2.

Step 4: Run Your Server  
------------------------

**If you created a server.py file (Option B)**

Start your server::

    python server.py

**If you used the one-liner example (Option A)**

Your server should already be running! If not, run it again::

    python -c "from opinionated_mcp.example import run_example_server; run_example_server('YOUR_GOOGLE_CLIENT_ID_HERE')"

Replace ``YOUR_GOOGLE_CLIENT_ID_HERE`` with your actual Google Client ID from step 2.

You should see output like::

    🚀 Starting Example MCP Server       # (or "User Name Manager" if you created server.py)
    📡 Server: http://localhost:8000
    🔗 Base URL: http://localhost:8000
    🔐 Login: http://localhost:8000/login
    🤖 MCP: http://localhost:8000/mcp

Step 5: Test Your Server
-------------------------

1. **Visit the server**: Open http://localhost:8000 in your browser
2. **Log in**: Click the login link or visit http://localhost:8000/login
3. **Authenticate**: Complete the Google OAuth flow
4. **Test the MCP endpoint**: Your MCP tools are available at http://localhost:8000/mcp

Testing with MCP Client
~~~~~~~~~~~~~~~~~~~~~~~

If you have an MCP client, connect it to ``http://localhost:8000/mcp``. You'll see two available authenticated tools:

- ``write_name`` - Takes a name parameter and stores it for the authenticated user
- ``read_name`` - Returns the authenticated user's stored name

You can also use these authenticated web endpoints:

- ``GET /my-name`` - Get your stored name (requires authentication)
- ``POST /my-name`` - Set your name (requires authentication)

Each user who authenticates will have their own isolated data storage accessible through both MCP tools and web endpoints.

Understanding the Code
----------------------

Let's break down what's happening:

**Server Setup**::

    server = OpinionatedMCP(
        name="User Name Manager",                    # Display name
        google_client_id="YOUR_CLIENT_ID",          # Google OAuth Client ID  
        session_key=generate_session_key(),         # Encryption key for sessions
        base_url="http://localhost:8000"            # Where your server runs
    )

**Authenticated MCP Tool Definition**::

    @server.authenticated_tool(name="write_name", description="Store your name")
    def write_name(user_id: str, name: str) -> str:
        # User ID is automatically injected by the authenticated_tool decorator
        user_data[user_id] = name
        return f"Stored name '{name}' for user {user_id}"

**Authenticated Endpoint Definition**::

    @server.app.get("/my-name")
    async def get_my_name(request: Request):
        user_id = server.oauth_handler.get_user_from_request(request)
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        name = user_data.get(user_id, "No name stored")
        return {"user_id": user_id, "name": name}

Key points:

- ``@server.authenticated_tool()`` registers an MCP tool that automatically receives the authenticated user's ID as the first parameter
- ``@server.app.get()`` and ``@server.app.post()`` create authenticated web endpoints
- For web endpoints, ``user_id`` is obtained by calling ``server.oauth_handler.get_user_from_request(request)``
- You manually check authentication and handle the user_id in your web endpoint logic
- MCP tools using ``@server.authenticated_tool()`` automatically get user context without manual authentication checks

**Authentication Flow**:

1. User calls an authenticated MCP tool or visits an authenticated endpoint (e.g., ``/my-name``)
2. Server checks session for authentication status
3. If not authenticated, returns 401 error or redirects to login
4. If authenticated:
   - For MCP tools: user_id is automatically injected as the first parameter
   - For web endpoints: your endpoint code gets the user_id and handles per-user data
5. Both MCP tools and web endpoints support user-specific functionality

What Makes This "Opinionated"
------------------------------

This framework makes several decisions for you:

- **Google OAuth only** - No configuration for multiple providers
- **PKCE without client secrets** - More secure, easier deployment  
- **Automatic user ID injection** - Your MCP tools automatically get the authenticated user ID
- **Session-based authentication** - Uses encrypted cookies
- **FastAPI integration** - Modern, async Python web framework

Production Considerations
-------------------------

For production use, consider these improvements:

**Persistent Storage**::

    # Replace in-memory dict with a database
    import sqlite3

    def get_user_name(user_id):
        conn = sqlite3.connect('users.db')
        cursor = conn.execute('SELECT name FROM users WHERE email = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    def set_user_name(user_id, name):
        conn = sqlite3.connect('users.db')
        conn.execute('INSERT OR REPLACE INTO users (email, name) VALUES (?, ?)', (user_id, name))
        conn.commit()
        conn.close()

**Environment Variables**::

    import os
    
    server = OpinionatedMCP(
        name=os.getenv("SERVER_NAME", "User Name Manager"),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID"),
        session_key=os.getenv("SESSION_KEY", generate_session_key()),
        base_url=os.getenv("BASE_URL", "http://localhost:8000")
    )

**HTTPS and Domain**::

    # Update Google OAuth redirect URI to:
    # https://yourdomain.com/callback
    
    server = OpinionatedMCP(
        name="User Name Manager",
        google_client_id="YOUR_CLIENT_ID",
        session_key=os.getenv("SESSION_KEY"),
        base_url="https://yourdomain.com",
        host="0.0.0.0",  # Listen on all interfaces
        port=int(os.getenv("PORT", "8000"))
    )

Next Steps
----------

Now that you have a working authenticated MCP server, you can:

- Add more tools with different functionality
- Integrate with databases or external APIs
- Deploy to production with proper HTTPS
- Add web endpoints alongside your MCP tools
- Scale to handle multiple users

The key insight is that you can easily build user-specific functionality using either authenticated MCP tools with ``@server.authenticated_tool()`` or authenticated web endpoints. Both approaches provide automatic user isolation, allowing you to build comprehensive user-specific applications that work seamlessly with MCP clients and web browsers.

Troubleshooting
---------------

**"OAuth error" messages**: 
  Check that your Google Client ID is correct and the redirect URI (``http://localhost:8000/callback``) is configured in Google Cloud Console.

**"No name stored" always returned**:
  Make sure you're testing with the same Google account that you used to store the name.

**MCP client can't connect**:
  Ensure your server is running and accessible at ``http://localhost:8000/mcp``.

**Server won't start**:
  Check that port 8000 isn't already in use, or change the port in your server configuration.