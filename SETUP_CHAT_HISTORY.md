# Quick Setup Guide - ChatGPT-like Chat History

## For New Installations

1. **Create the database tables:**
   ```bash
   psql -h your-supabase-host -U postgres -d postgres -f create_chat_tables.sql
   ```

2. **Restart your application:**
   ```bash
   python main.py
   ```

3. **Done!** The chat history system is now active.

## For Existing Installations (Migration)

1. **Backup your database first:**
   ```bash
   pg_dump -h your-host -U your-user -d your-db > backup.sql
   ```

2. **Run the migration script:**
   ```bash
   psql -h your-supabase-host -U postgres -d postgres -f MIGRATE_CHAT_HISTORY.sql
   ```

3. **Restart your application:**
   ```bash
   python main.py
   ```

4. **Verify the migration:**
   - Open the app in your browser
   - Check that existing chats appear in the sidebar
   - Create a new chat and verify it saves properly

## Testing the System

### Test 1: Create New Conversation
1. Click "New chat" button
2. Send a message: "How does this work?"
3. Verify:
   - ✅ Conversation appears in sidebar
   - ✅ Title is "How does this work?"
   - ✅ URL changes to `/chat/{uuid}`
   - ✅ Message count shows "2 messages"

### Test 2: Switch Between Conversations
1. Create another new chat
2. Send a different message
3. Click the first conversation in sidebar
4. Verify:
   - ✅ First conversation loads
   - ✅ URL updates to first conversation's ID
   - ✅ Messages display correctly
   - ✅ Active conversation is highlighted

### Test 3: Browser Navigation
1. Open a conversation
2. Click browser back button
3. Click browser forward button
4. Verify:
   - ✅ Conversations load correctly
   - ✅ URL updates properly
   - ✅ No page reload occurs

### Test 4: Direct URL Access
1. Copy a conversation URL: `/chat/{uuid}`
2. Open in new tab
3. Verify:
   - ✅ Conversation loads automatically
   - ✅ All messages display
   - ✅ Can continue chatting

### Test 5: Rename Conversation
1. Click the menu icon (⋮) on a conversation
2. Click "Edit"
3. Type new title and press Enter
4. Verify:
   - ✅ Title updates in sidebar
   - ✅ Title persists after refresh

### Test 6: Delete Conversation
1. Click the menu icon (⋮) on a conversation
2. Click "Delete"
3. Confirm deletion
4. Verify:
   - ✅ Conversation removed from sidebar
   - ✅ If active, returns to home screen
   - ✅ Messages are deleted from database

## Troubleshooting

### Issue: Sidebar shows "No chat history yet"
**Solution:**
- Check Supabase connection in logs
- Verify tables exist: `SELECT * FROM "ChatSessions" LIMIT 1;`
- Check browser console for errors

### Issue: Messages not saving
**Solution:**
- Verify trigger exists: `\df update_session_on_message`
- Check session_id is valid UUID
- Look for errors in server logs

### Issue: Title stays "New Chat"
**Solution:**
- Verify you sent a user message (not just assistant)
- Check message_count in database
- Review ChatManager.add_message logic

### Issue: URL routing not working
**Solution:**
- Clear browser cache
- Check FastAPI route: `/chat/{conversation_id}`
- Verify conversation_id is valid UUID format

## Configuration

### Change Default User ID
In `src/chat_manager.py`, update the default:
```python
user_id: str = "your_user_id"
```

### Adjust Session Limit
In frontend, change the limit:
```javascript
const resp = await fetch("/chat/sessions?limit=100");
```

### Customize Title Generation
In `src/chat_manager.py`, modify:
```python
def _generate_title_from_message(self, message: str) -> str:
    words = message.strip().split()
    if len(words) <= 10:  # Changed from 6 to 10
        return message
    return ' '.join(words[:10]) + '...'
```

## Database Maintenance

### View All Sessions
```sql
SELECT id, title, message_count, last_message_at 
FROM "ChatSessions" 
ORDER BY updated_at DESC 
LIMIT 20;
```

### View Messages for a Session
```sql
SELECT role, content, created_at 
FROM "ChatMessages" 
WHERE session_id = 'your-session-uuid'
ORDER BY created_at ASC;
```

### Clean Up Old Sessions
```sql
-- Delete sessions older than 90 days with no messages
DELETE FROM "ChatSessions"
WHERE message_count = 0 
  AND created_at < NOW() - INTERVAL '90 days';
```

### Reset Message Counts
```sql
UPDATE "ChatSessions" s
SET message_count = (
    SELECT COUNT(*) 
    FROM "ChatMessages" m 
    WHERE m.session_id = s.id
);
```

## Next Steps

1. Read the full guide: `CHAT_HISTORY_GUIDE.md`
2. Customize the UI in `static/chat-history.css`
3. Add user authentication for multi-user support
4. Implement conversation search
5. Add export functionality

## Support

If you encounter issues:
1. Check server logs: `logs/service-error.log`
2. Check browser console (F12)
3. Verify database connection
4. Review the troubleshooting section above
