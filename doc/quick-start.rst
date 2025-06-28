Getting Started with opinionated_mcp
=====================================

**opinionated_mcp** is a zero-config OAuth framework for MCP (Model Context Protocol) servers that makes authentication simple and secure. This guide will get you to a working MCP server with user-specific data storage in just a few steps.

What You'll Build
-----------------

By the end of this guide, you'll have a working MCP server with two tools:

- ``write_name(name)`` - Store the user's name
- ``read_name()`` - Retrieve the user's stored name

Each user's data is automatically isolated by their Google account - no need to handle user identification in your tool code.

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

Step 3: Create Your Server
---------------------------

Create a new file called ``server.py``:

.. code-block:: python

    from opinionated_mcp import OpinionatedMCP, generate_session_key

    # In-memory storage for user data (use a database in production)
    user_data = {}

    # Create the MCP server
    server = OpinionatedMCP(
        name="User Name Manager",
        google_client_id="YOUR_GOOGLE_CLIENT_ID_HERE",  # Replace with your Client ID
        session_key=generate_session_key(),
        base_url="http://localhost:8000"
    )

    @server.tool(name="write_name", description="Store your name")
    @server.require_auth
    async def write_name(request, user_id, name: str):
        """Store the user's name. The user_id is automatically provided by authentication."""
        user_data[user_id] = name
        return f"Stored name '{name}' for user {user_id}"

    @server.tool(name="read_name", description="Get your stored name")
    @server.require_auth
    async def read_name(request, user_id):
        """Retrieve the user's stored name. The user_id is automatically provided by authentication."""
        name = user_data.get(user_id, "No name stored")
        return f"Your stored name is: {name}"

    if __name__ == "__main__":
        server.run(debug=True)

**Important**: Replace ``YOUR_GOOGLE_CLIENT_ID_HERE`` with your actual Google Client ID from step 2.

Step 4: Run Your Server
------------------------

Start your server::

    python server.py

You should see output like::

    🚀 Starting User Name Manager
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

If you have an MCP client, connect it to ``http://localhost:8000/mcp``. You'll see two available tools:

- ``write_name`` - Takes a name parameter
- ``read_name`` - Returns your stored name

Each user who authenticates will have their own isolated data storage.

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

**Tool Definition**::

    @server.tool(name="write_name", description="Store your name")
    @server.require_auth
    async def write_name(request, user_id, name: str):
        # user_id is automatically the authenticated user's email
        user_data[user_id] = name
        return f"Stored name '{name}' for user {user_id}"

Key points:

- ``@server.tool()`` registers the function as an MCP tool
- ``@server.require_auth`` ensures only authenticated users can call it
- ``user_id`` parameter is automatically injected with the authenticated user's email
- The tool signature (``name: str``) becomes the MCP tool's parameter schema

**Authentication Flow**:

1. User calls an MCP tool
2. Server checks if user is authenticated
3. If not authenticated, returns authentication error
4. If authenticated, calls your tool function with ``user_id`` automatically set
5. Your tool code works with per-user data without worrying about authentication

What Makes This "Opinionated"
------------------------------

This framework makes several decisions for you:

- **Google OAuth only** - No configuration for multiple providers
- **PKCE without client secrets** - More secure, easier deployment  
- **Automatic user ID injection** - Your tools automatically get the authenticated user
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

The key insight is that ``user_id`` is automatically provided to all your ``@server.require_auth`` decorated tools, so you can focus on your business logic rather than authentication plumbing.

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