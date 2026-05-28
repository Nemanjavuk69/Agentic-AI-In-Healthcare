# Agentic AI In Healthcare

A semester project focused on analyzing privacy risks and security implications in agentic AI systems applied to healthcare. This project leverages large language models and autonomous agents to identify, evaluate, and mitigate privacy vulnerabilities in healthcare applications.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)

## Prerequisites

Before you begin, ensure you have the following prerequisites installed on your system:

### 1. Ollama

Ollama is required to run and manage large language models locally. Follow the official instructions below:

<!-- **Official Ollama Website:** https://ollama.ai -->

**Installation Instructions:**
- Visit [ollama.ai](https://ollama.ai) and download the installer for your operating system (Windows, macOS, or Linux)
- Follow the official installation guide provided on their website
- Verify your installation by running:
  ```bash
  ollama --version
  ```

### 2. Qwen2.5 Model

After installing Ollama, you'll need to pull the Qwen2.5 model. Choose based on your system resources:

**For systems with moderate resources (3B parameter model):**
```bash
ollama pull qwen2.5:3b
```

**For systems with more powerful hardware (7B parameter model):**
```bash
ollama pull qwen2.5:7b
```

**Start the Ollama service:**
```bash
ollama serve
```

The model will be available at `http://localhost:11434` by default.

### 3. Python Requirements

- **Python:** 3.8 or higher
- **Package Manager:** pip (comes with Python)

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Nemanjavuk69/Agentic-AI-In-Healthcare.git
   cd Agentic-AI-In-Healthcare
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   - **On Windows:**
     ```bash
     agentic\Scripts\venv
     ```
   - **On macOS/Linux:**
     ```bash
     source venv/bin/activate
     ```

4. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Once you have completed the installation steps, follow these steps to run the application:

1. **Ensure Ollama is running:**
   ```bash
   ollama serve
   ```
   Keep this terminal window open.

2. **Start the Booking API (in a new terminal):**
   
   Make sure you're in the project directory with the virtual environment activated, then run:
    ```bash
    python code/booking_api.py
    ```
   The Booking API should now be running and ready to accept requests. Keep this terminal window open.

3. **Run the main agent (in another new terminal):**

Make sure you're in the project directory with the virtual environment activated, then run:
    ```bash
    python code/agent1.py
    ```

## Configuration

### Model Selection

The Qwen2.5 model is configured in `code/utils.py`. Open this file and update the `MODEL_NAME` variable to choose between:

- `qwen2.5:3b` - Faster, suitable for development and testing
- `qwen2.5:7b` - Better performance and accuracy (recommended)

**Example configuration in utils.py:**
```python
"model": "qwen2.5:3b" OR "model": "qwen2.5:7b"
```
