@echo off
set PORT=24210
set BASE_PATH=/
pnpm --filter @workspace/trading-dashboard run dev
