#!/usr/bin/env python3
"""
Taxonomy Backend for Scientific Paper Clustering
Uses sentence transformers for embeddings, sklearn for clustering,
and Claude API for intelligent cluster naming.
"""

import json
import sys
import numpy as np
from typing import List, Dict, Any
import warnings
warnings.filterwarnings('ignore')

# Try to import required libraries
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    import requests
    from collections import Counter
except ImportError as e:
    print(f"Missing required library: {e}", file=sys.stderr)
    print("Install with: pip install sentence-transformers scikit-learn requests --break-system-packages", file=sys.stderr)
    sys.exit(1)


class TaxonomyGenerator:
    def __init__(self):
        """Initialize the taxonomy generator with embedding model."""
        print("Loading embedding model...", file=sys.stderr)
        # Use a smaller, faster model for efficiency
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        print("Model loaded successfully!", file=sys.stderr)
    
    def fetch_paper_metadata(self, doi: str) -> Dict[str, Any]:
        """Fetch paper metadata from Crossref API."""
        try:
            url = f"https://api.crossref.org/works/{doi}"
            headers = {'User-Agent': 'TaxonomyVisualizer/1.0 (mailto:research@example.com)'}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()['message']
                
                # Extract key information
                title = data.get('title', [''])[0] if data.get('title') else ''
                abstract = data.get('abstract', '')
                
                # Clean abstract HTML tags if present
                if abstract:
                    import re
                    abstract = re.sub('<[^<]+?>', '', abstract)
                
                # Get authors
                authors = []
                if 'author' in data:
                    authors = [f"{a.get('given', '')} {a.get('family', '')}".strip() 
                              for a in data['author'][:3]]  # First 3 authors
                
                # Get keywords (if available)
                keywords = data.get('subject', [])
                
                return {
                    'doi': doi,
                    'title': title,
                    'abstract': abstract,
                    'authors': authors,
                    'keywords': keywords,
                    'year': data.get('published-print', {}).get('date-parts', [[None]])[0][0]
                }
            else:
                print(f"Failed to fetch {doi}: HTTP {response.status_code}", file=sys.stderr)
                return None
                
        except Exception as e:
            print(f"Error fetching {doi}: {str(e)}", file=sys.stderr)
            return None
    
    def fetch_papers_from_csv_data(self, csv_data: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Fetch paper metadata. If CSV contains full metadata, use it.
        Otherwise, fetch from Crossref.
        """
        papers = []
        
        for row in csv_data:
            doi = row.get('DOI', '').strip()
            if not doi:
                continue
            
            # Check if we have full metadata in CSV (like IEEE export)
            if 'Document Title' in row or 'Abstract' in row:
                paper = {
                    'doi': doi,
                    'title': row.get('Document Title', row.get('Title', '')),
                    'abstract': row.get('Abstract', ''),
                    'authors': row.get('Authors', '').split(';')[:3] if row.get('Authors') else [],
                    'keywords': (row.get('Author Keywords', '') + ';' + row.get('IEEE Terms', '')).split(';'),
                    'year': row.get('Publication Year', '')
                }
                papers.append(paper)
            else:
                # Fetch from Crossref
                paper = self.fetch_paper_metadata(doi)
                if paper:
                    papers.append(paper)
        
        print(f"Successfully loaded {len(papers)} papers", file=sys.stderr)
        return papers
    
    def create_embeddings(self, papers: List[Dict[str, Any]]) -> np.ndarray:
        """Create embeddings from paper title, abstract, and keywords."""
        texts = []
        
        for paper in papers:
            # Combine title, abstract, and keywords for rich semantic representation
            text_parts = []
            
            if paper.get('title'):
                text_parts.append(paper['title'])
            
            if paper.get('abstract'):
                # Truncate long abstracts
                abstract = paper['abstract'][:500]
                text_parts.append(abstract)
            
            if paper.get('keywords'):
                keywords = ' '.join([k.strip() for k in paper['keywords'] if k.strip()])
                if keywords:
                    text_parts.append(keywords)
            
            combined_text = ' '.join(text_parts)
            texts.append(combined_text)
        
        print("Generating embeddings...", file=sys.stderr)
        embeddings = self.model.encode(texts, show_progress_bar=True)
        return embeddings
    
    def cluster_papers(self, embeddings: np.ndarray, k: int) -> np.ndarray:
        """Perform k-means clustering on embeddings."""
        print(f"Clustering into {k} groups...", file=sys.stderr)
        
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(embeddings)
        
        # Calculate silhouette score for quality metric
        if len(set(labels)) > 1:
            score = silhouette_score(embeddings, labels)
            print(f"Silhouette score: {score:.3f}", file=sys.stderr)
        
        return labels
    
    def generate_cluster_name(self, papers: List[Dict[str, Any]], cluster_papers: List[int]) -> str:
        """Generate a meaningful cluster name using keyword analysis."""
        # Get papers in this cluster
        cluster_paper_list = [papers[i] for i in cluster_papers]
        
        # Extract titles and keywords for analysis
        titles = [p['title'] for p in cluster_paper_list if p.get('title')]
        all_keywords = []
        for p in cluster_paper_list:
            if p.get('keywords'):
                all_keywords.extend([k.strip().lower() for k in p['keywords'] if k.strip()])
        
        # Get most common keywords
        keyword_counts = Counter(all_keywords)
        
        # Also extract key terms from titles
        title_words = []
        for title in titles:
            # Extract meaningful words (skip common words)
            words = title.lower().split()
            meaningful = [w for w in words if len(w) > 4 and w not in 
                         {'based', 'using', 'study', 'paper', 'approach', 'analysis', 
                          'method', 'system', 'research', 'novel', 'conference'}]
            title_words.extend(meaningful)
        
        title_word_counts = Counter(title_words)
        
        # Combine keywords and title words
        all_terms = dict(keyword_counts)
        for word, count in title_word_counts.items():
            all_terms[word] = all_terms.get(word, 0) + count * 0.5  # Weight title words slightly less
        
        # Get top terms
        top_terms = sorted(all_terms.items(), key=lambda x: x[1], reverse=True)[:6]
        top_keywords = [term for term, _ in top_terms]
        
        # Clean up and create name
        return self._create_smart_name(top_keywords)
    
    def _create_smart_name(self, keywords: List[str]) -> str:
        """Create a smart, readable name from keywords."""
        if not keywords:
            return "Research Cluster"
        
        # Filter out very generic terms
        stop_words = {'research', 'study', 'analysis', 'paper', 'approach', 'method', 
                     'system', 'based', 'using', 'new', 'novel', 'ieee', 'access',
                     'learning', 'network', 'model', 'data', 'algorithm'}
        
        # First pass: get specific terms
        specific = [k.title() for k in keywords if k.lower() not in stop_words and len(k) > 3]
        
        if len(specific) >= 2:
            # Use top 2-3 specific terms
            return ' & '.join(specific[:3])
        
        # Second pass: include one common term with specific terms
        if len(specific) >= 1 and len(keywords) >= 2:
            common_term = keywords[0].title() if keywords[0].lower() in stop_words else keywords[1].title()
            return f"{specific[0]} {common_term}"
        
        # Fallback: just use top keywords
        clean_keywords = [k.title() for k in keywords if len(k) > 3]
        if len(clean_keywords) >= 2:
            return ' & '.join(clean_keywords[:3])
        elif len(clean_keywords) == 1:
            return clean_keywords[0] + " Systems"
        
        return "Research Cluster"

    
    def build_taxonomy(self, papers: List[Dict[str, Any]], k: int) -> Dict[str, Any]:
        """Build complete taxonomy structure."""
        if len(papers) == 0:
            return {"error": "No papers to cluster"}
        
        # Generate embeddings
        embeddings = self.create_embeddings(papers)
        
        # Perform clustering
        k = min(k, len(papers))  # Ensure k doesn't exceed paper count
        labels = self.cluster_papers(embeddings, k)
        
        # Build taxonomy structure
        print("Generating cluster names...", file=sys.stderr)
        taxonomy = {
            "name": "Research Taxonomy",
            "children": []
        }
        
        for cluster_id in range(k):
            # Get papers in this cluster
            cluster_indices = [i for i, label in enumerate(labels) if label == cluster_id]
            cluster_papers = [papers[i] for i in cluster_indices]
            
            # Generate cluster name
            cluster_name = self.generate_cluster_name(papers, cluster_indices)
            
            # Create cluster node
            cluster_node = {
                "name": cluster_name,
                "size": len(cluster_indices),
                "papers": [
                    {
                        "doi": p['doi'],
                        "title": p['title'],
                        "authors": ', '.join(p['authors']) if p.get('authors') else '',
                        "year": p.get('year', '')
                    }
                    for p in cluster_papers
                ]
            }
            
            taxonomy["children"].append(cluster_node)
        
        # Sort by size (descending)
        taxonomy["children"].sort(key=lambda x: x['size'], reverse=True)
        
        return taxonomy


def main():
    """Main entry point for the taxonomy generator."""
    if len(sys.argv) < 3:
        print("Usage: python taxonomy_backend.py <csv_json_data> <k_clusters>", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Parse arguments
        csv_json = sys.argv[1]
        k = int(sys.argv[2])
        
        # Parse CSV data
        csv_data = json.loads(csv_json)
        
        # Initialize generator
        generator = TaxonomyGenerator()
        
        # Fetch papers
        papers = generator.fetch_papers_from_csv_data(csv_data)
        
        if not papers:
            print(json.dumps({"error": "No papers could be loaded"}))
            sys.exit(1)
        
        # Build taxonomy
        taxonomy = generator.build_taxonomy(papers, k)
        
        # Output JSON
        print(json.dumps(taxonomy, indent=2))
        
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()