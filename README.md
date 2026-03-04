# 🚀 Taxonomy Engine - AI-Powered Research Classification

An interactive web application that uses machine learning to automatically cluster and visualize scientific papers into a hierarchical taxonomy. Built with Python (ML backend) and React + D3.js (interactive frontend).

![Taxonomy Visualization](https://img.shields.io/badge/Visualization-Sunburst-FFD700)
![AI Powered](https://img.shields.io/badge/AI-Claude%20%2B%20ML-FF6B9D)
![Status](https://img.shields.io/badge/Status-Production%20Ready-00FF00)

## ✨ Features

- **📊 AI-Powered Clustering**: Uses sentence transformers and k-means to group papers semantically
- **🎯 Adjustable K Value**: Choose between 2-15 clusters to match your research needs
- **🤖 Intelligent Naming**: Claude AI automatically generates meaningful cluster names
- **📈 Interactive Sunburst Visualization**: Beautiful D3.js radial layout with hover effects
- **📄 Rich Paper Metadata**: Fetches titles, abstracts, authors, and keywords
- **💾 CSV Export**: Export individual clusters for further analysis
- **📋 Clipboard Copy**: Quick copy of paper details for documentation
- **🎨 Stunning UI**: Cyberpunk-inspired design with smooth animations

## 🛠️ Technology Stack

### Backend
- **Python 3.8+**
- **sentence-transformers**: Semantic embeddings
- **scikit-learn**: K-means clustering
- **Claude API**: Intelligent cluster naming
- **requests**: API communication

### Frontend
- **React 18**: Component-based UI
- **D3.js v7**: Data visualization
- **Node.js**: Express server
- **Vanilla CSS**: Custom styling

## 📋 Prerequisites

1. **Python 3.8+** installed
2. **Node.js 16+** and npm installed
3. **4GB+ RAM** recommended for embedding generation

## 🚀 Installation

### Step 1: Clone/Download the Project

Download all files to a directory of your choice.

### Step 2: Install Python Dependencies

```bash
pip install sentence-transformers scikit-learn requests --break-system-packages
```

Or if you prefer using a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install sentence-transformers scikit-learn requests
```

### Step 3: Install Node.js Dependencies

```bash
npm install
```

### Step 4: Start the Server

```bash
npm start
```

The server will start on `http://localhost:3000`

## 📖 Usage

### 1. Prepare Your CSV File

Your CSV file should contain DOI numbers. Two formats are supported:

#### Format A: Simple DOI List
```csv
DOI
10.1109/ACCESS.2026.3665348
10.1109/ACCESS.2025.3532853
10.1109/ACCESS.2026.3662282
```

#### Format B: Full IEEE Export (Recommended)
If you have a full IEEE Xplore export with columns like:
- `Document Title`
- `Abstract`
- `Author Keywords`
- `IEEE Terms`
- `DOI`

The system will use this rich metadata directly for better clustering!

### 2. Upload and Cluster

1. **Open** `http://localhost:3000` in your browser
2. **Click** "Choose CSV File" and select your CSV
3. **Adjust** the K value (number of clusters) using the slider
4. **Click** "Generate Taxonomy" and wait for processing
5. **Explore** the interactive sunburst visualization!

### 3. Interact with Clusters

- **Hover** over any segment to preview cluster details
- **Click** a cluster to see the full list of papers
- **Export** individual clusters as CSV files
- **Copy** paper details to clipboard for documentation

## 🎯 How It Works

### 1. **Data Ingestion**
The system reads your CSV and either:
- Uses existing metadata (if provided)
- Fetches metadata from Crossref API (for DOI-only CSVs)

### 2. **Embedding Generation**
Combines paper titles, abstracts, and keywords into semantic embeddings using the `all-MiniLM-L6-v2` sentence transformer model.

### 3. **Clustering**
Applies k-means clustering to group semantically similar papers.

### 4. **Intelligent Naming**
Claude AI analyzes paper titles and keywords in each cluster to generate descriptive category names.

### 5. **Visualization**
Creates an interactive sunburst chart where:
- Center = Root taxonomy
- Inner ring = Main clusters
- Size = Number of papers

## 📊 Example Use Cases

### Use Case 1: Literature Review Organization
- Upload 120 papers on "Machine Learning"
- Set k=7 to get broad categories
- Export each cluster for focused reading

### Use Case 2: Research Gap Analysis
- Upload papers from your field
- Set k=10 for granular clustering
- Identify under-researched areas

### Use Case 3: Conference Paper Classification
- Upload accepted papers
- Set k=5 to create session tracks
- Export for conference program

## 🎨 Customization

### Adjust Clustering Algorithm

Edit `taxonomy_backend.py` line 120:

```python
# Switch to hierarchical clustering
from sklearn.cluster import AgglomerativeClustering
clusterer = AgglomerativeClustering(n_clusters=k)
labels = clusterer.fit_predict(embeddings)
```

### Change Embedding Model

Edit `taxonomy_backend.py` line 30:

```python
# Use a more powerful model
self.model = SentenceTransformer('all-mpnet-base-v2')
```

### Customize Visualization Colors

Edit `public/taxonomy_visualizer.jsx` line 160:

```javascript
const colorScale = d3.scaleOrdinal()
  .range([
    '#YOUR_COLOR_1',
    '#YOUR_COLOR_2',
    // ... add more colors
  ]);
```

## ⚠️ Limitations & Notes

- **API Rate Limits**: Crossref has rate limits (50 requests/second)
- **Processing Time**: ~5-30 seconds for 100 papers depending on hardware
- **Max Papers**: Recommended maximum of 200 papers per analysis
- **Internet Required**: For fetching paper metadata and Claude API calls

## 🔧 Troubleshooting

### "Module not found" Error
```bash
# Reinstall Python dependencies
pip install sentence-transformers scikit-learn requests --break-system-packages --force-reinstall
```

### Server Won't Start
```bash
# Check if port 3000 is already in use
lsof -ti:3000 | xargs kill -9  # macOS/Linux
netstat -ano | findstr :3000   # Windows
```

### Clustering Takes Too Long
- Reduce the number of papers
- Use a smaller embedding model
- Increase RAM allocation

### Papers Not Loading
- Check DOI format (must be valid)
- Verify internet connection
- Check Crossref API status

## 📚 File Structure

```
taxonomy-engine/
├── taxonomy_backend.py      # Python ML backend
├── server.js                # Express server
├── package.json             # Node dependencies
├── public/
│   ├── index.html          # Main HTML page
│   └── taxonomy_visualizer.jsx  # React component
└── README.md               # This file
```

## 🤝 Contributing

Feel free to fork, modify, and improve! Some ideas:

- Add support for arXiv, PubMed, or other paper sources
- Implement hierarchical clustering visualization
- Add paper similarity network view
- Export to different formats (PDF, PNG, etc.)
- Add more ML algorithms (DBSCAN, hierarchical, etc.)

## 📄 License

MIT License - Feel free to use for research and commercial purposes!

## 🎓 Citation

If you use this tool in your research, please cite:

```bibtex
@software{taxonomy_engine_2026,
  author = {Your Name},
  title = {Taxonomy Engine: AI-Powered Research Classification},
  year = {2026},
  url = {https://github.com/yourusername/taxonomy-engine}
}
```

## 🌟 Acknowledgments

- **Sentence Transformers** for semantic embeddings
- **D3.js** for beautiful visualizations
- **Claude AI** by Anthropic for intelligent naming
- **Crossref API** for paper metadata

---

**Built with ❤️ for researchers, by researchers**

For questions or support, open an issue or contact [vanRossum@umass.org]
