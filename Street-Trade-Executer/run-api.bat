@echo off
set PORT=8080
set "DATABASE_URL=postgresql://neondb_owner:npg_fh3GJr2iTRCW@ep-bitter-mode-aoi5d1e5-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
set NODE_ENV=development
node --enable-source-maps artifacts/api-server/dist/index.mjs
