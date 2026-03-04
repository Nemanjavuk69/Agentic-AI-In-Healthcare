# 🚀 QUICK START GUIDE

## Three Ways to Get Started

### Option 1: 🎭 Demo Mode (Instant - No Setup Required!)

**Perfect for:** Quick preview of the UI and functionality

1. Open `demo_standalone.html` in your web browser
2. Upload the included `sample_papers.csv` file
3. Click "Generate Taxonomy"
4. Explore the interactive visualization!

**Note:** This uses mock data and doesn't perform real AI clustering.

---

### Option 2: ⚡ Full Setup (Recommended)

**Perfect for:** Production use with real AI clustering

#### Prerequisites
- Python 3.8+ installed
- Node.js 16+ installed
- 4GB+ RAM

#### Installation

**On macOS/Linux:**
```bash
./quickstart.sh
```

**On Windows:**
```batch
quickstart.bat
```

**Or manually:**

1. **Install Python dependencies:**
```bash
pip install sentence-transformers scikit-learn requests --break-system-packages
```

2. **Install Node.js dependencies:**
```bash
npm install
```

3. **Start the server:**
```bash
npm start
```

4. **Open your browser:**
Navigate to `http://localhost:3000`

---

### Option 3: 🔧 Manual Testing (Advanced)

**Perfect for:** Testing the Python backend directly

```bash
# Test with sample data
python3 taxonomy_backend.py '[{"DOI": "10.1109/ACCESS.2026.3665348"}]' 5
```

---

## 📊 Using the Application

### Step 1: Prepare Your CSV

Your CSV needs a `DOI` column with paper DOIs:

```csv
DOI
10.1109/ACCESS.2026.3665348
10.1109/ACCESS.2025.3532853
10.1109/ACCESS.2026.3662282
```

**Bonus:** If you have full IEEE exports with `Document Title`, `Abstract`, `Author Keywords`, the system will use that rich metadata directly!

### Step 2: Generate Taxonomy

1. **Upload CSV** - Click "Choose CSV File" and select your file
2. **Set K Value** - Use the slider to choose 2-15 clusters
3. **Generate** - Click "Generate Taxonomy" and wait 10-30 seconds
4. **Explore** - Interact with the beautiful sunburst visualization!

### Step 3: Export Results

- **Hover** over clusters to preview papers
- **Click** clusters to see full details
- **Export CSV** - Download cluster papers as CSV
- **Copy** - Copy paper details to clipboard

---

## 🎨 What You'll See

### The Visualization
- **Center Circle**: Root taxonomy node
- **Inner Ring**: Main research categories (auto-generated names!)
- **Colors**: Each cluster has a distinct, vibrant color
- **Size**: Larger segments = more papers in that cluster

### Interactions
- **Hover**: Highlights segment + shows preview
- **Click**: Opens detailed panel with all papers
- **Smooth Animations**: Watch clusters fade in beautifully

---

## 📁 Project Structure

```
taxonomy-engine/
├── demo_standalone.html      ← Demo version (no backend needed)
├── quickstart.sh              ← macOS/Linux setup script
├── quickstart.bat             ← Windows setup script
├── sample_papers.csv          ← Sample data for testing
├── taxonomy_backend.py        ← Python ML backend
├── server.js                  ← Express server
├── package.json               ← Node.js dependencies
├── public/
│   ├── index.html            ← Main HTML page
│   └── taxonomy_visualizer.jsx ← React component
└── README.md                  ← Full documentation
```

---

## 🔍 How It Works

### 1. Paper Ingestion
- Reads DOIs from CSV
- Fetches metadata (title, abstract, keywords)
- Supports both Crossref API and IEEE exports

### 2. Semantic Embeddings
- Uses `sentence-transformers` model
- Combines title + abstract + keywords
- Creates high-dimensional vector representations

### 3. K-Means Clustering
- Groups similar papers together
- You control the number of groups (k)
- Optimizes for semantic similarity

### 4. Intelligent Naming
- **Claude AI** analyzes each cluster
- Extracts key themes from paper titles
- Generates descriptive category names

### 5. Interactive Visualization
- **D3.js** creates sunburst layout
- Smooth animations and transitions
- Hover effects and click interactions

---

## 🎯 Common Use Cases

### 1. Literature Review Organization
```
Papers: 120 research articles on "Deep Learning"
k: 7 clusters
Result: Broad categories like "NLP", "Computer Vision", "Reinforcement Learning"
```

### 2. Research Gap Analysis
```
Papers: Your field's recent publications
k: 10 clusters
Action: Identify under-researched areas
```

### 3. Conference Track Planning
```
Papers: Accepted conference submissions
k: 5 clusters
Result: Session tracks with balanced paper distribution
```

---

## ⚠️ Troubleshooting

### "Module not found" Error
```bash
pip install sentence-transformers scikit-learn requests --break-system-packages --force-reinstall
```

### Server Won't Start
Port 3000 might be in use:
```bash
# Kill process on port 3000 (macOS/Linux)
lsof -ti:3000 | xargs kill -9

# Or change the port in server.js
const PORT = 3001;  // Change to different port
```

### Slow Processing
- Reduce number of papers
- Use a smaller embedding model
- Ensure adequate RAM (4GB+)

### Papers Not Loading
- Verify DOI format
- Check internet connection
- Crossref API might be rate-limited

---

## 🎓 Tips for Best Results

1. **Use Rich Metadata**: IEEE exports with abstracts give better clustering than DOI-only files

2. **Choose K Wisely**: 
   - k=3-5 for broad categories
   - k=7-10 for balanced granularity
   - k=12-15 for fine-grained classification

3. **Batch Processing**: Process 80-120 papers at a time for optimal performance

4. **Domain Specificity**: Works best with papers from a specific research area

---

## 📞 Need Help?

1. Check `README.md` for detailed documentation
2. Review error messages in terminal/console
3. Try the demo version first to verify setup
4. Check browser console (F12) for frontend errors

---

## 🌟 What Makes This Special?

✅ **AI-Powered Naming** - Claude generates human-readable category names  
✅ **Beautiful Visualization** - Cyberpunk-inspired sunburst design  
✅ **Interactive Exploration** - Hover, click, export, copy  
✅ **Semantic Clustering** - Groups papers by meaning, not just keywords  
✅ **Production Ready** - Real ML models, not mock data  
✅ **Flexible Input** - Works with DOIs or full metadata  

---

## 🚀 Ready to Start?

1. **Quick Test:** Open `demo_standalone.html`
2. **Full Setup:** Run `./quickstart.sh` (or `.bat` on Windows)
3. **Upload Papers:** Use `sample_papers.csv` or your own data
4. **Generate & Explore!**

**Have fun exploring your research taxonomy! 🎉**
