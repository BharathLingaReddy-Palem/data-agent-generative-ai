-- ========================================================
-- 🗄️ Supabase PostgreSQL Database Schema
-- Autonomous Data Science Agent
-- ========================================================

-- 1. Projects Table
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    owner_id TEXT,
    csv_url TEXT NOT NULL,
    task_type TEXT,
    target_column TEXT,
    status TEXT DEFAULT 'completed',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Existing deployments: ownership is supplied by the server's local account database.
ALTER TABLE projects ADD COLUMN IF NOT EXISTS owner_id TEXT;
CREATE INDEX IF NOT EXISTS projects_owner ON projects(owner_id);

-- 2. Trained Models / Leaderboard Table
CREATE TABLE IF NOT EXISTS model_leaderboard (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    model_url TEXT,
    accuracy DOUBLE PRECISION,
    f1_score DOUBLE PRECISION,
    rmse DOUBLE PRECISION,
    r2_score DOUBLE PRECISION,
    is_best BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Reports Table
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    pdf_url TEXT NOT NULL,
    summary TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 4. Chat History Table
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Server-only mirror. Use a service-role key on the backend, never in either UI.
-- RLS with no public policies prevents anon/authenticated clients from bypassing the API.
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_leaderboard ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON projects, model_leaderboard, reports, chat_messages FROM anon, authenticated;
