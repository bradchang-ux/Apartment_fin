#!/usr/bin/env bash
set -e

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Build frontend
cd ../frontend
npm install
npm run build

cd ..
