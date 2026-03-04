const express = require('express');
const { spawn } = require('child_process');
const path = require('path');
const cors = require('cors');

const app = express();
const PORT = 3000;

app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.static('public'));

// API endpoint to generate taxonomy
app.post('/api/generate-taxonomy', async (req, res) => {
  try {
    const { csvData, k } = req.body;

    if (!csvData || !k) {
      return res.status(400).json({ error: 'Missing csvData or k parameter' });
    }

    console.log(`Generating taxonomy with k=${k} for ${csvData.length} papers...`);

    // Call Python backend (use 'python' on Windows, 'python3' on Mac/Linux)
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    const python = spawn(pythonCmd, [
      path.join(__dirname, 'taxonomy_backend.py'),
      JSON.stringify(csvData),
      k.toString()
    ]);

    let stdout = '';
    let stderr = '';

    python.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    python.stderr.on('data', (data) => {
      stderr += data.toString();
      console.error('Python stderr:', data.toString());
    });

    python.on('close', (code) => {
      if (code !== 0) {
        console.error('Python error:', stderr);
        return res.status(500).json({ 
          error: 'Taxonomy generation failed',
          details: stderr
        });
      }

      try {
        const result = JSON.parse(stdout);
        console.log('Taxonomy generated successfully');
        res.json(result);
      } catch (err) {
        console.error('Failed to parse Python output:', err);
        res.status(500).json({ 
          error: 'Failed to parse taxonomy data',
          details: stdout
        });
      }
    });

    python.on('error', (err) => {
      console.error('Failed to start Python process:', err);
      res.status(500).json({ 
        error: 'Failed to start taxonomy generation',
        details: err.message
      });
    });

  } catch (error) {
    console.error('Server error:', error);
    res.status(500).json({ 
      error: 'Internal server error',
      details: error.message
    });
  }
});

app.listen(PORT, () => {
  console.log(`
╔═══════════════════════════════════════════════╗
║   TAXONOMY ENGINE SERVER                      ║
║   Running on http://localhost:${PORT}        ║
╚═══════════════════════════════════════════════╝

Open your browser and navigate to:
→ http://localhost:${PORT}

Make sure you have installed Python dependencies:
→ pip install sentence-transformers scikit-learn requests --break-system-packages
  `);
});