-- Run this in your Supabase SQL Editor to check your database structure
-- This will show what tables and functions exist

-- Check for Documents table
SELECT 'Documents table' as check_type, 
       CASE WHEN EXISTS (
         SELECT FROM information_schema.tables 
         WHERE table_schema = 'public' 
         AND table_name = 'Documents'
       ) THEN '✓ EXISTS' ELSE '✗ MISSING' END as status;

-- Check for DocumentChunks table
SELECT 'DocumentChunks table' as check_type,
       CASE WHEN EXISTS (
         SELECT FROM information_schema.tables 
         WHERE table_schema = 'public' 
         AND table_name = 'DocumentChunks'
       ) THEN '✓ EXISTS' ELSE '✗ MISSING' END as status;

-- Check for fts_search function
SELECT 'fts_search function' as check_type,
       CASE WHEN EXISTS (
         SELECT FROM information_schema.routines 
         WHERE routine_schema = 'public' 
         AND routine_name = 'fts_search'
       ) THEN '✓ EXISTS' ELSE '✗ MISSING' END as status;

-- Check for match_documents function (vector search)
SELECT 'match_documents function' as check_type,
       CASE WHEN EXISTS (
         SELECT FROM information_schema.routines 
         WHERE routine_schema = 'public' 
         AND routine_name = 'match_documents'
       ) THEN '✓ EXISTS' ELSE '✗ MISSING' END as status;

-- Check for RetrievalProfiles table
SELECT 'RetrievalProfiles table' as check_type,
       CASE WHEN EXISTS (
         SELECT FROM information_schema.tables 
         WHERE table_schema = 'public' 
         AND table_name = 'RetrievalProfiles'
       ) THEN '✓ EXISTS' ELSE '✗ MISSING' END as status;

-- Check for ChatSessions table
SELECT 'ChatSessions table' as check_type,
       CASE WHEN EXISTS (
         SELECT FROM information_schema.tables 
         WHERE table_schema = 'public' 
         AND table_name = 'ChatSessions'
       ) THEN '✓ EXISTS' ELSE '✗ MISSING' END as status;

-- Check for ChatMessages table
SELECT 'ChatMessages table' as check_type,
       CASE WHEN EXISTS (
         SELECT FROM information_schema.tables 
         WHERE table_schema = 'public' 
         AND table_name = 'ChatMessages'
       ) THEN '✓ EXISTS' ELSE '✗ MISSING' END as status;

-- List all functions in public schema
SELECT 'All functions in public schema:' as info;
SELECT routine_name, routine_type
FROM information_schema.routines
WHERE routine_schema = 'public'
ORDER BY routine_name;

-- List all tables in public schema
SELECT 'All tables in public schema:' as info;
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_type = 'BASE TABLE'
ORDER BY table_name;
