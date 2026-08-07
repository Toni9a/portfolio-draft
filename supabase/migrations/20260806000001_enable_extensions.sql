-- Migration 001: Enable extensions
-- Run this first in the Supabase SQL editor or via CLI

-- Vector similarity search (for opinion embeddings / backfeed brain)
create extension if not exists vector;

-- Better UUID generation
create extension if not exists "pgcrypto";
