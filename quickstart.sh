#!/bin/bash

echo "╔═══════════════════════════════════════════════╗"
echo "║   TAXONOMY ENGINE - QUICK START SCRIPT        ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8+ first."
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 16+ first."
    exit 1
fi

echo "✓ Node.js found: $(node --version)"
echo ""

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install sentence-transformers scikit-learn requests --break-system-packages --quiet

if [ $? -eq 0 ]; then
    echo "✓ Python dependencies installed"
else
    echo "⚠️  Some Python dependencies may have failed. Please check errors above."
fi

echo ""

# Install Node.js dependencies
echo "📦 Installing Node.js dependencies..."
npm install --silent

if [ $? -eq 0 ]; then
    echo "✓ Node.js dependencies installed"
else
    echo "❌ Failed to install Node.js dependencies"
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "✨ Setup complete! Starting server..."
echo "═══════════════════════════════════════════════"
echo ""

# Start the server
npm start
