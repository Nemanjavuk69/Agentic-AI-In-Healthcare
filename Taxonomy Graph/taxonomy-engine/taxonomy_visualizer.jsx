import React, { useState, useRef, useEffect } from 'react';
import * as d3 from 'd3';

const TaxonomyVisualizer = () => {
  const [csvData, setCsvData] = useState(null);
  const [kValue, setKValue] = useState(5);
  const [taxonomy, setTaxonomy] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedCluster, setSelectedCluster] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const svgRef = useRef(null);
  const fileInputRef = useRef(null);

  // Parse CSV file
  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target.result;
      const lines = text.trim().split('\n');
      
      if (lines.length < 2) {
        setError('CSV file appears to be empty');
        return;
      }

      // Parse CSV (handle quoted fields)
      const parseCSVLine = (line) => {
        const result = [];
        let current = '';
        let inQuotes = false;
        
        for (let i = 0; i < line.length; i++) {
          const char = line[i];
          if (char === '"') {
            inQuotes = !inQuotes;
          } else if (char === ',' && !inQuotes) {
            result.push(current.trim());
            current = '';
          } else {
            current += char;
          }
        }
        result.push(current.trim());
        return result;
      };

      const headers = parseCSVLine(lines[0]);
      const data = lines.slice(1).map(line => {
        const values = parseCSVLine(line);
        const row = {};
        headers.forEach((header, i) => {
          row[header] = values[i] || '';
        });
        return row;
      }).filter(row => row.DOI && row.DOI.trim());

      setCsvData(data);
      setError(null);
      setTaxonomy(null);
    };

    reader.onerror = () => {
      setError('Failed to read file');
    };

    reader.readAsText(file);
  };

  // Generate taxonomy by calling Python backend
  const generateTaxonomy = async () => {
    if (!csvData) {
      setError('Please upload a CSV file first');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Call Python backend
      const result = await fetch('/api/generate-taxonomy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          csvData,
          k: kValue
        })
      });

      if (!result.ok) {
        throw new Error('Backend processing failed');
      }

      const data = await result.json();
      
      if (data.error) {
        setError(data.error);
      } else {
        setTaxonomy(data);
      }
    } catch (err) {
      setError(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Render sunburst visualization
  useEffect(() => {
    if (!taxonomy || !svgRef.current) return;

    const width = 900;
    const height = 900;
    const radius = Math.min(width, height) / 2;

    // Clear previous
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', [-width / 2, -height / 2, width, height])
      .style('font-family', "'JetBrains Mono', 'Courier New', monospace")
      .style('font-size', '12px');

    // Create hierarchy
    const root = d3.hierarchy(taxonomy)
      .sum(d => d.size || 0)
      .sort((a, b) => b.value - a.value);

    // Create partition layout
    const partition = d3.partition()
      .size([2 * Math.PI, radius]);

    partition(root);

    // Color scale - vibrant, distinct colors
    const colorScale = d3.scaleOrdinal()
      .domain(root.children ? root.children.map(d => d.data.name) : [])
      .range([
        '#FF6B9D', '#C44569', '#FEA47F', '#25CCF7', '#EAB543',
        '#55E6C1', '#CAD3C8', '#F97F51', '#1B9CFC', '#58B19F',
        '#2C3A47', '#B33771', '#3B3B98', '#FD7272', '#9AECDB'
      ]);

    // Arc generator
    const arc = d3.arc()
      .startAngle(d => d.x0)
      .endAngle(d => d.x1)
      .padAngle(d => Math.min((d.x1 - d.x0) / 2, 0.005))
      .padRadius(radius / 2)
      .innerRadius(d => d.y0)
      .outerRadius(d => d.y1 - 2);

    // Create paths
    const paths = svg.append('g')
      .selectAll('path')
      .data(root.descendants().filter(d => d.depth > 0))
      .join('path')
      .attr('d', arc)
      .attr('fill', d => {
        while (d.depth > 1) d = d.parent;
        return colorScale(d.data.name);
      })
      .attr('fill-opacity', d => d.depth === 1 ? 0.9 : 0.6)
      .attr('stroke', '#1a1a1a')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .style('transition', 'all 0.3s ease')
      .on('mouseover', function(event, d) {
        d3.select(this)
          .attr('fill-opacity', 1)
          .attr('stroke-width', 3)
          .attr('stroke', '#FFD700');
        
        setHoveredNode(d);
      })
      .on('mouseout', function(event, d) {
        d3.select(this)
          .attr('fill-opacity', d.depth === 1 ? 0.9 : 0.6)
          .attr('stroke-width', 2)
          .attr('stroke', '#1a1a1a');
        
        setHoveredNode(null);
      })
      .on('click', (event, d) => {
        if (d.depth === 1) {
          setSelectedCluster(d.data);
        }
      });

    // Add labels for main clusters
    svg.append('g')
      .selectAll('text')
      .data(root.descendants().filter(d => d.depth === 1))
      .join('text')
      .attr('transform', d => {
        const x = (d.x0 + d.x1) / 2 * 180 / Math.PI;
        const y = (d.y0 + d.y1) / 2;
        return `rotate(${x - 90}) translate(${y},0) rotate(${x < 180 ? 0 : 180})`;
      })
      .attr('dy', '0.35em')
      .attr('text-anchor', 'middle')
      .attr('fill', '#ffffff')
      .attr('font-weight', 'bold')
      .attr('font-size', '14px')
      .attr('pointer-events', 'none')
      .text(d => {
        const name = d.data.name;
        return name.length > 25 ? name.substring(0, 22) + '...' : name;
      });

    // Add central circle with title
    svg.append('circle')
      .attr('r', radius / 4)
      .attr('fill', '#1a1a1a')
      .attr('stroke', '#FFD700')
      .attr('stroke-width', 4);

    svg.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '-0.5em')
      .attr('fill', '#FFD700')
      .attr('font-size', '24px')
      .attr('font-weight', 'bold')
      .text('Research');

    svg.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '1em')
      .attr('fill', '#ffffff')
      .attr('font-size', '18px')
      .text('Taxonomy');

    // Animation
    paths.attr('opacity', 0)
      .transition()
      .duration(800)
      .delay((d, i) => i * 20)
      .attr('opacity', 1);

  }, [taxonomy]);

  // Export cluster to CSV
  const exportCluster = (cluster) => {
    if (!cluster || !cluster.papers) return;

    const headers = ['DOI', 'Title', 'Authors', 'Year'];
    const rows = cluster.papers.map(p => [
      p.doi,
      `"${p.title.replace(/"/g, '""')}"`,
      `"${p.authors.replace(/"/g, '""')}"`,
      p.year
    ]);

    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${cluster.name.replace(/[^a-z0-9]/gi, '_')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Copy cluster papers to clipboard
  const copyToClipboard = (cluster) => {
    if (!cluster || !cluster.papers) return;

    const text = cluster.papers.map(p => 
      `${p.title}\nDOI: ${p.doi}\nAuthors: ${p.authors}\nYear: ${p.year}\n`
    ).join('\n---\n\n');

    navigator.clipboard.writeText(text).then(() => {
      alert('Papers copied to clipboard!');
    });
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%)',
      color: '#ffffff',
      fontFamily: "'Space Mono', 'Courier New', monospace",
      padding: '2rem'
    }}>
      {/* Header */}
      <div style={{
        textAlign: 'center',
        marginBottom: '3rem',
        animation: 'fadeInDown 0.8s ease'
      }}>
        <h1 style={{
          fontSize: '4rem',
          fontWeight: '900',
          background: 'linear-gradient(90deg, #FFD700, #FFA500, #FF6B9D)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          marginBottom: '0.5rem',
          letterSpacing: '-2px'
        }}>
          TAXONOMY ENGINE
        </h1>
        <p style={{
          fontSize: '1.2rem',
          color: '#888',
          letterSpacing: '4px',
          textTransform: 'uppercase'
        }}>
          AI-Powered Research Classification
        </p>
      </div>

      {/* Controls */}
      <div style={{
        maxWidth: '1200px',
        margin: '0 auto',
        background: 'rgba(255, 255, 255, 0.05)',
        backdropFilter: 'blur(10px)',
        border: '2px solid rgba(255, 215, 0, 0.3)',
        borderRadius: '20px',
        padding: '2rem',
        marginBottom: '2rem'
      }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr',
          gap: '2rem',
          alignItems: 'end'
        }}>
          {/* File Upload */}
          <div>
            <label style={{
              display: 'block',
              fontSize: '0.9rem',
              color: '#FFD700',
              marginBottom: '0.5rem',
              fontWeight: 'bold',
              letterSpacing: '1px'
            }}>
              📄 UPLOAD CSV
            </label>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleFileUpload}
              style={{ display: 'none' }}
            />
            <button
              onClick={() => fileInputRef.current.click()}
              style={{
                width: '100%',
                padding: '1rem',
                background: csvData ? 'rgba(0, 255, 0, 0.2)' : 'rgba(255, 215, 0, 0.2)',
                border: `2px solid ${csvData ? '#00ff00' : '#FFD700'}`,
                borderRadius: '10px',
                color: '#ffffff',
                fontSize: '1rem',
                cursor: 'pointer',
                transition: 'all 0.3s ease',
                fontFamily: 'inherit'
              }}
              onMouseOver={(e) => e.target.style.background = csvData ? 'rgba(0, 255, 0, 0.3)' : 'rgba(255, 215, 0, 0.3)'}
              onMouseOut={(e) => e.target.style.background = csvData ? 'rgba(0, 255, 0, 0.2)' : 'rgba(255, 215, 0, 0.2)'}
            >
              {csvData ? `✓ ${csvData.length} Papers Loaded` : 'Choose CSV File'}
            </button>
          </div>

          {/* K Value Slider */}
          <div>
            <label style={{
              display: 'block',
              fontSize: '0.9rem',
              color: '#FFD700',
              marginBottom: '0.5rem',
              fontWeight: 'bold',
              letterSpacing: '1px'
            }}>
              🎯 CLUSTERS: {kValue}
            </label>
            <input
              type="range"
              min="2"
              max="15"
              value={kValue}
              onChange={(e) => setKValue(parseInt(e.target.value))}
              style={{
                width: '100%',
                height: '8px',
                background: 'rgba(255, 215, 0, 0.3)',
                borderRadius: '5px',
                outline: 'none',
                cursor: 'pointer'
              }}
            />
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '0.8rem',
              color: '#666',
              marginTop: '0.5rem'
            }}>
              <span>2</span>
              <span>15</span>
            </div>
          </div>

          {/* Generate Button */}
          <div>
            <button
              onClick={generateTaxonomy}
              disabled={!csvData || loading}
              style={{
                width: '100%',
                padding: '1rem',
                background: loading 
                  ? 'rgba(128, 128, 128, 0.3)' 
                  : 'linear-gradient(90deg, #FFD700, #FFA500)',
                border: 'none',
                borderRadius: '10px',
                color: '#000000',
                fontSize: '1.1rem',
                fontWeight: 'bold',
                cursor: loading || !csvData ? 'not-allowed' : 'pointer',
                transition: 'all 0.3s ease',
                fontFamily: 'inherit',
                letterSpacing: '1px',
                textTransform: 'uppercase'
              }}
              onMouseOver={(e) => {
                if (!loading && csvData) {
                  e.target.style.transform = 'translateY(-2px)';
                  e.target.style.boxShadow = '0 8px 20px rgba(255, 215, 0, 0.4)';
                }
              }}
              onMouseOut={(e) => {
                e.target.style.transform = 'translateY(0)';
                e.target.style.boxShadow = 'none';
              }}
            >
              {loading ? '⚡ Processing...' : '🚀 Generate Taxonomy'}
            </button>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div style={{
            marginTop: '1rem',
            padding: '1rem',
            background: 'rgba(255, 0, 0, 0.1)',
            border: '2px solid rgba(255, 0, 0, 0.5)',
            borderRadius: '10px',
            color: '#ff6b6b'
          }}>
            ⚠️ {error}
          </div>
        )}
      </div>

      {/* Visualization */}
      {taxonomy && (
        <div style={{
          maxWidth: '1200px',
          margin: '0 auto',
          display: 'grid',
          gridTemplateColumns: '900px 1fr',
          gap: '2rem'
        }}>
          {/* Sunburst Chart */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.05)',
            backdropFilter: 'blur(10px)',
            border: '2px solid rgba(255, 215, 0, 0.3)',
            borderRadius: '20px',
            padding: '2rem',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center'
          }}>
            <svg ref={svgRef}></svg>
          </div>

          {/* Info Panel */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.05)',
            backdropFilter: 'blur(10px)',
            border: '2px solid rgba(255, 215, 0, 0.3)',
            borderRadius: '20px',
            padding: '2rem',
            maxHeight: '900px',
            overflowY: 'auto'
          }}>
            <h2 style={{
              fontSize: '1.5rem',
              color: '#FFD700',
              marginBottom: '1rem',
              letterSpacing: '1px'
            }}>
              {hoveredNode || selectedCluster ? '📊 CLUSTER DETAILS' : '💡 INSTRUCTIONS'}
            </h2>

            {!hoveredNode && !selectedCluster && (
              <div style={{ color: '#aaa', lineHeight: '1.8' }}>
                <p style={{ marginBottom: '1rem' }}>
                  <strong style={{ color: '#FFD700' }}>Hover</strong> over any cluster segment to preview details
                </p>
                <p style={{ marginBottom: '1rem' }}>
                  <strong style={{ color: '#FFD700' }}>Click</strong> a cluster to view full paper list
                </p>
                <p>
                  <strong style={{ color: '#FFD700' }}>Export</strong> clusters to CSV for further analysis
                </p>
              </div>
            )}

            {(hoveredNode || selectedCluster) && (() => {
              const cluster = selectedCluster || (hoveredNode?.depth === 1 ? hoveredNode.data : null);
              if (!cluster) return null;

              return (
                <div>
                  <h3 style={{
                    fontSize: '1.2rem',
                    color: '#ffffff',
                    marginBottom: '1rem',
                    wordWrap: 'break-word'
                  }}>
                    {cluster.name}
                  </h3>
                  
                  <div style={{
                    display: 'flex',
                    gap: '1rem',
                    marginBottom: '1.5rem'
                  }}>
                    <div style={{
                      padding: '0.5rem 1rem',
                      background: 'rgba(255, 215, 0, 0.2)',
                      border: '2px solid #FFD700',
                      borderRadius: '8px',
                      fontSize: '0.9rem'
                    }}>
                      📄 {cluster.size || cluster.papers?.length || 0} Papers
                    </div>
                    
                    {selectedCluster && (
                      <>
                        <button
                          onClick={() => exportCluster(cluster)}
                          style={{
                            padding: '0.5rem 1rem',
                            background: 'rgba(0, 255, 0, 0.2)',
                            border: '2px solid #00ff00',
                            borderRadius: '8px',
                            color: '#ffffff',
                            cursor: 'pointer',
                            fontSize: '0.9rem',
                            fontFamily: 'inherit'
                          }}
                          onMouseOver={(e) => e.target.style.background = 'rgba(0, 255, 0, 0.3)'}
                          onMouseOut={(e) => e.target.style.background = 'rgba(0, 255, 0, 0.2)'}
                        >
                          💾 CSV
                        </button>
                        
                        <button
                          onClick={() => copyToClipboard(cluster)}
                          style={{
                            padding: '0.5rem 1rem',
                            background: 'rgba(0, 200, 255, 0.2)',
                            border: '2px solid #00c8ff',
                            borderRadius: '8px',
                            color: '#ffffff',
                            cursor: 'pointer',
                            fontSize: '0.9rem',
                            fontFamily: 'inherit'
                          }}
                          onMouseOver={(e) => e.target.style.background = 'rgba(0, 200, 255, 0.3)'}
                          onMouseOut={(e) => e.target.style.background = 'rgba(0, 200, 255, 0.2)'}
                        >
                          📋 Copy
                        </button>
                      </>
                    )}
                  </div>

                  {cluster.papers && (
                    <div style={{
                      maxHeight: '600px',
                      overflowY: 'auto'
                    }}>
                      {cluster.papers.map((paper, idx) => (
                        <div
                          key={idx}
                          style={{
                            padding: '1rem',
                            background: 'rgba(255, 255, 255, 0.05)',
                            border: '1px solid rgba(255, 215, 0, 0.2)',
                            borderRadius: '10px',
                            marginBottom: '1rem',
                            transition: 'all 0.3s ease'
                          }}
                          onMouseOver={(e) => {
                            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)';
                            e.currentTarget.style.borderColor = '#FFD700';
                          }}
                          onMouseOut={(e) => {
                            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
                            e.currentTarget.style.borderColor = 'rgba(255, 215, 0, 0.2)';
                          }}
                        >
                          <div style={{
                            fontSize: '0.9rem',
                            color: '#ffffff',
                            fontWeight: 'bold',
                            marginBottom: '0.5rem',
                            lineHeight: '1.4'
                          }}>
                            {paper.title}
                          </div>
                          <div style={{
                            fontSize: '0.8rem',
                            color: '#888',
                            marginBottom: '0.3rem'
                          }}>
                            {paper.authors}
                          </div>
                          <div style={{
                            fontSize: '0.75rem',
                            color: '#666'
                          }}>
                            DOI: {paper.doi} | Year: {paper.year}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })()}
          </div>
        </div>
      )}

      {/* Footer */}
      <div style={{
        textAlign: 'center',
        marginTop: '3rem',
        padding: '2rem',
        borderTop: '2px solid rgba(255, 215, 0, 0.2)',
        color: '#666',
        fontSize: '0.9rem'
      }}>
        <p>Powered by Sentence Transformers • K-Means Clustering • Claude AI</p>
        <p style={{ marginTop: '0.5rem' }}>Built with React & D3.js</p>
      </div>

      <style>{`
        @keyframes fadeInDown {
          from {
            opacity: 0;
            transform: translateY(-30px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        /* Custom scrollbar */
        ::-webkit-scrollbar {
          width: 10px;
          height: 10px;
        }

        ::-webkit-scrollbar-track {
          background: rgba(255, 255, 255, 0.05);
          border-radius: 5px;
        }

        ::-webkit-scrollbar-thumb {
          background: rgba(255, 215, 0, 0.5);
          border-radius: 5px;
        }

        ::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 215, 0, 0.7);
        }
      `}</style>
    </div>
  );
};

export default TaxonomyVisualizer;
