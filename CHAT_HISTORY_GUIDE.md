# Chat History System - ChatGPT-like Implementation

## Overview

The chat history system now works like ChatGPT with persistent conversation sessions. Each conversation is stored in the database and can be reopened, continued, and managed through the sidebar.

## Key Features

✅ **Persistent Sessions** - Conversations are saved to the database and survive page refreshes  
✅ **URL Routing** - Each conversation has a unique URL: `/chat/{conversation_id}`  
✅ **Automatic Titles** - First user message generates a conversation title  
✅ **Session Management** - Create, rename, delete conversations from the sidebar  
✅ **Message History** - All messages are linked to their conversation and retrieved in order  
✅ **Browser Navigation** - Back/forward buttons work to navigate between conversations  
✅ **Real-time Updates** - Session timestamps and message counts update automatically  

## Database Schema

### ChatSessions Table
```sql
- id (UUID, primary key)
- user_id (TEXT, default: 'default_user')
- title (TEXT, default: 'New Chat')
- collection (TEXT, optional)
- created_at (TIMESTAMPTZ)
- updated_at (TIMESTAMPTZ)
- last_message_at (TIMESTAMPTZ)
- message_count (INTEGER)
```

### ChatMessages Table
```sql
- id (UUID, primary key)
- session_id (UUID, foreign key → ChatSessions.id)
- user_id (TEXT, default: 'default_user')
- role (TEXT, 'user' or 'assistant')
- content (TEXT)
- sources (JSONB, optional)
- retrieval_profile (TEXT, optional)
- created_at (TIMESTAMPTZ)
```

## How It Works

### Creating a New Chat

1. User clicks "New chat" button
2. System clears current session (doesn't create DB record yet)
3. When user sends first message:
   - Creates new conversation record
   - Generates title from first user message
   - Saves user message
   - Retrieves response and saves assistant message
   - Updates session timestamp and message count

### Continuing a Chat

1. User clicks a conversation in sidebar
2. System loads conversation by `conversation_id`
3. Retrieves all messages in chronological order
4. Displays full conversation thread
5. New messages append to same conversation
6. Session `updated_at` timestamp updates automatically

### URL Structure

- **Home page**: `/` - Shows welcome screen, no active conversation
- **Specific conversation**: `/chat/{conversation_id}` - Loads that conversation
- **Browser navigation**: Back/forward buttons navigate between conversations
- **Shareable**: URLs can be bookmarked or shared

### Automatic Title Generation

When the first user message is sent:
```javascript
// Takes first 6 words of the message
"How do I implement a chat system?" → "How do I implement a..."
"Hello" → "Hello"
```

If no title is generated, defaults to "New Chat"

## API Endpoints

### Create Session
```http
POST /chat/sessions
Content-Type: application/json

{
  "title": "Optional title",
  "collection": "optional_collection_name"
}

Response: { "status": "success", "session": {...} }
```

### List Sessions
```http
GET /chat/sessions?limit=50&collection=optional

Response: { "status": "success", "sessions": [...] }
```

### Get Session
```http
GET /chat/sessions/{session_id}

Response: { "status": "success", "session": {...} }
```

### Update Session
```http
PUT /chat/sessions/{session_id}
Content-Type: application/json

{
  "title": "New title"
}

Response: { "status": "success", "session": {...} }
```

### Delete Session
```http
DELETE /chat/sessions/{session_id}

Response: { "status": "success" }
```

### Get Messages
```http
GET /chat/sessions/{session_id}/messages

Response: { "status": "success", "messages": [...] }
```

### Add Message
```http
POST /chat/sessions/{session_id}/messages
Content-Type: application/json

{
  "role": "user",
  "content": "Message text",
  "sources": [...],  // optional
  "retrieval_profile": "balanced"  // optional
}

Response: { "status": "success", "message": {...} }
```

## Database Triggers

A PostgreSQL trigger automatically updates session metadata when messages are added:

```sql
CREATE TRIGGER trigger_update_session_on_message
    AFTER INSERT ON public."ChatMessages"
    FOR EACH ROW
    EXECUTE FUNCTION update_session_on_message();
```

This trigger:
- Updates `updated_at` to current timestamp
- Sets `last_message_at` to message creation time
- Increments `message_count`

## Migration from Old System

If you have existing chat tables, run the migration:

```bash
psql -h your-host -U your-user -d your-db -f MIGRATE_CHAT_HISTORY.sql
```

Or for fresh installation:

```bash
psql -h your-host -U your-user -d your-db -f create_chat_tables.sql
```

## Frontend Implementation

### State Management
```javascript
state = {
  currentSessionId: null,  // Active conversation ID
  sessions: [],            // List of all sessions
  chatHistory: []          // In-memory message cache
}
```

### Key Functions

- `createNewSession(title)` - Creates new conversation
- `loadChatSessions()` - Loads all sessions for sidebar
- `switchToSession(sessionId)` - Loads specific conversation
- `saveMessageToSession(role, content, sources)` - Saves message to current session
- `renderChatSessions()` - Updates sidebar UI

### URL Handling

```javascript
// On page load
const pathMatch = window.location.pathname.match(/^\/chat\/([a-f0-9-]+)$/i);
if (pathMatch) {
  await switchToSession(pathMatch[1]);
}

// On navigation
window.addEventListener('popstate', async (event) => {
  // Handle back/forward buttons
});
```

## User Experience

### Sidebar Features

- **Search** - Filter conversations by title or collection
- **Rename** - Click edit icon to rename conversation
- **Delete** - Click delete icon (with confirmation)
- **Active indicator** - Current conversation is highlighted
- **Metadata** - Shows message count and last activity time

### Message Display

- User messages appear on the right
- Assistant messages appear on the left
- Sources/metadata shown below messages
- Full conversation history loads on session switch

## Best Practices

1. **Don't create sessions prematurely** - Wait for first message
2. **Always link messages to sessions** - Use `session_id` foreign key
3. **Update URLs on navigation** - Keep browser history in sync
4. **Handle errors gracefully** - Show user-friendly error messages
5. **Validate session existence** - Check session exists before adding messages

## Troubleshooting

### Sessions not appearing in sidebar
- Check database connection
- Verify `user_id` matches (default: 'default_user')
- Check browser console for errors

### Messages not saving
- Verify `session_id` is valid UUID
- Check `role` is either 'user' or 'assistant'
- Ensure database trigger is created

### URL routing not working
- Clear browser cache
- Check FastAPI route is registered
- Verify conversation_id format (UUID)

### Title not auto-generating
- Check first message is from 'user' role
- Verify `message_count` is 1 or less
- Check ChatManager.add_message logic

## Future Enhancements

- [ ] User authentication and multi-user support
- [ ] Conversation folders/categories
- [ ] Export conversation to PDF/Markdown
- [ ] Search within conversation
- [ ] Pin important conversations
- [ ] Archive old conversations
- [ ] Conversation templates
