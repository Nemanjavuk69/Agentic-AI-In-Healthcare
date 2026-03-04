@echo off
echo ╔═══════════════════════════════════════════════╗
echo ║   TAXONOMY ENGINE - QUICK START SCRIPT        ║
echo ╚═══════════════════════════════════════════════╝
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed. Please install Python 3.8+ first.
    pause
    exit /b 1
)

echo ✓ Python found
python --version

:: Check if Node.js is installed
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js is not installed. Please install Node.js 16+ first.
    pause
    exit /b 1
)

echo ✓ Node.js found
node --version
echo.

:: Install Python dependencies
echo 📦 Installing Python dependencies...
pip install sentence-transformers scikit-learn requests --break-system-packages --quiet

if %errorlevel% equ 0 (
    echo ✓ Python dependencies installed
) else (
    echo ⚠️  Some Python dependencies may have failed. Please check errors above.
)

echo.

:: Install Node.js dependencies
echo 📦 Installing Node.js dependencies...
call npm install

if %errorlevel% equ 0 (
    echo ✓ Node.js dependencies installed
) else (
    echo ❌ Failed to install Node.js dependencies
    pause
    exit /b 1
)

echo.
echo ═══════════════════════════════════════════════
echo ✨ Setup complete! Starting server...
echo ═══════════════════════════════════════════════
echo.

:: Start the server
call npm start
