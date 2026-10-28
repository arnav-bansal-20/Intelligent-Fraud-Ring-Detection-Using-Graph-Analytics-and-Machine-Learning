import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import cytoscape from 'cytoscape';
import { api } from '../api/client';
import {
  Network,
  ZoomIn,
  ZoomOut,
  Maximize2,
  RefreshCw,
  Info,
  ShieldAlert,
  UserCheck,
  Building2,
  X
} from 'lucide-react';

export default function RingExplorer() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialAccountId = searchParams.get('account') || '1';

  const [accountId, setAccountId] = useState(initialAccountId);
  const [hops, setHops] = useState(1);
  const [graphData, setGraphData] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const containerRef = useRef(null);
  const cyRef = useRef(null);

  const loadRing = async (targetId, targetHops) => {
    setLoading(true);
    setError('');
    setSelectedNode(null);

    try {
      const data = await api.getRing(targetId, targetHops);
      setGraphData(data);
    } catch (err) {
      setError(err.message || 'Failed to load graph data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRing(accountId, hops);
  }, []);

  // Initialize and update Cytoscape instance when graphData changes
  useEffect(() => {
    if (!containerRef.current || !graphData) return;

    // Destroy existing instance
    if (cyRef.current) {
      cyRef.current.destroy();
    }

    // Format elements for Cytoscape
    const elements = [
      ...graphData.nodes.map(n => ({
        data: {
          id: n.id,
          label: n.is_center ? `★ Acc #${n.account_id}` : `Acc #${n.account_id}`,
          raw: n
        }
      })),
      ...graphData.edges.map(e => ({
        data: {
          id: e.id,
          source: e.source,
          target: e.target,
          weight: e.shared_merchant_count,
          label: `${e.shared_merchant_count} shared`
        }
      }))
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'color': '#cbd5e1',
            'font-size': '11px',
            'font-family': 'Inter, sans-serif',
            'text-valign': 'bottom',
            'text-margin-y': 6,
            'background-color': '#8b5cf6',
            'width': 26,
            'height': 26,
            'border-width': 2,
            'border-color': '#0f172a'
          }
        },
        {
          selector: 'node[?raw.is_center]',
          style: {
            'background-color': '#f59e0b',
            'border-color': '#ffffff',
            'border-width': 3,
            'width': 38,
            'height': 38,
            'font-size': '13px',
            'font-weight': 'bold',
            'color': '#fde68a',
            'z-index': 10
          }
        },
        {
          selector: 'node[?raw.is_fraud]',
          style: {
            'background-color': '#ef4444',
            'border-color': '#fca5a5',
            'border-width': 2,
            'width': 30,
            'height': 30,
            'color': '#fca5a5'
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 'mapData(weight, 1, 50, 1.5, 5)',
            'line-color': '#475569',
            'opacity': 0.6,
            'curve-style': 'bezier'
          }
        },
        {
          selector: 'node:selected',
          style: {
            'border-color': '#38bdf8',
            'border-width': 4
          }
        }
      ],
      layout: {
        name: 'concentric',
        concentric: (node) => {
          if (node.data('raw')?.is_center) return 10;
          if (node.data('raw')?.is_fraud) return 7;
          return 4;
        },
        levelWidth: () => 2,
        padding: 50,
        animate: true,
        animationDuration: 500
      }
    });

    cy.on('tap', 'node', (evt) => {
      const nodeData = evt.target.data('raw');
      setSelectedNode(nodeData);
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        setSelectedNode(null);
      }
    });

    cyRef.current = cy;

    return () => {
      if (cyRef.current) cyRef.current.destroy();
    };
  }, [graphData]);

  const handleSearch = (e) => {
    e.preventDefault();
    setSearchParams({ account: accountId });
    loadRing(accountId, hops);
  };

  const handleZoom = (factor) => {
    if (cyRef.current) {
      cyRef.current.zoom(cyRef.current.zoom() * factor);
    }
  };

  const handleFit = () => {
    if (cyRef.current) {
      cyRef.current.fit(undefined, 40);
    }
  };

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '24px' }}>
      {/* Header & Controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.4rem', fontWeight: 800, color: '#fff', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Network size={24} color="#8b5cf6" />
            Interactive Fraud Ring Explorer (Cytoscape.js)
          </h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Visualizes multi-hop account clusters connected through identical 24h merchant transacting footprints.
          </p>
        </div>

        {/* Filter / Search Form */}
        <form onSubmit={handleSearch} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '6px 12px', gap: '8px' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>Account ID:</span>
            <input
              type="number"
              min="1"
              max="999"
              value={accountId}
              onChange={e => setAccountId(e.target.value)}
              className="mono"
              style={{ width: '80px', background: 'transparent', border: 'none', color: '#fff', fontSize: '0.85rem', outline: 'none' }}
              required
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '6px 12px', gap: '8px' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>Hops:</span>
            <select
              value={hops}
              onChange={e => setHops(parseInt(e.target.value))}
              style={{ background: 'transparent', border: 'none', color: '#fff', fontSize: '0.85rem', outline: 'none' }}
            >
              <option value={1} style={{ background: '#111827' }}>1 Hop (Direct)</option>
              <option value={2} style={{ background: '#111827' }}>2 Hops (Expanded)</option>
              <option value={3} style={{ background: '#111827' }}>3 Hops (Syndicate)</option>
            </select>
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              background: '#8b5cf6',
              color: '#fff',
              padding: '8px 16px',
              borderRadius: '8px',
              fontWeight: 600,
              fontSize: '0.82rem',
              cursor: loading ? 'not-allowed' : 'pointer'
            }}
          >
            {loading ? 'Traversing Graph...' : 'Explore Ring'}
          </button>
        </form>
      </div>

      {/* Explanatory Density Banner */}
      {graphData && (
        <div style={{
          background: 'rgba(59, 130, 246, 0.1)',
          border: '1px solid rgba(59, 130, 246, 0.25)',
          borderRadius: '8px',
          padding: '12px 18px',
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          fontSize: '0.82rem',
          color: '#93c5fd'
        }}>
          <Info size={20} style={{ flexShrink: 0 }} />
          <div>
            <strong>Graph Density Optimization:</strong> Raw account neighborhood contains <strong>{graphData.raw_neighborhood_degree} connected peers</strong> (dataset average degree is ~835).
            To eliminate browser freezing and isolate active threats, the explorer returned <strong>{graphData.capped_nodes_count} prioritized nodes</strong> (confirmed fraud syndicates and top shared merchant accounts).
          </div>
        </div>
      )}

      {error && (
        <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#fca5a5', padding: '12px', borderRadius: '8px', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {/* Main Canvas & Inspector Drawer */}
      <div style={{ position: 'relative' }}>
        {/* Cytoscape Canvas Container */}
        <div
          ref={containerRef}
          style={{
            width: '100%',
            height: '620px',
            background: '#070b14',
            borderRadius: '12px',
            border: '1px solid var(--border-color)',
            boxShadow: 'inset 0 2px 10px rgba(0,0,0,0.6)'
          }}
        />

        {/* Legend */}
        <div style={{
          position: 'absolute',
          top: '16px',
          left: '16px',
          background: 'rgba(17, 24, 39, 0.85)',
          backdropFilter: 'blur(8px)',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          padding: '10px 14px',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
          fontSize: '0.74rem'
        }}>
          <div style={{ fontWeight: 600, color: 'var(--text-muted)', marginBottom: '2px' }}>Network Roles</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#f59e0b', border: '2px solid #fff' }} />
            <span>Center Investigated Account</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#ef4444' }} />
            <span>Confirmed Fraud Syndicate Peer</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#8b5cf6' }} />
            <span>High-Traffic Merchant Peer</span>
          </div>
        </div>

        {/* Floating Zoom / Pan Controls */}
        <div style={{
          position: 'absolute',
          bottom: '16px',
          left: '16px',
          display: 'flex',
          gap: '6px',
          background: 'rgba(17, 24, 39, 0.85)',
          backdropFilter: 'blur(8px)',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          padding: '6px'
        }}>
          <button
            onClick={() => handleZoom(1.25)}
            style={{ padding: '6px', borderRadius: '6px', color: 'var(--text-muted)', background: 'transparent' }}
            title="Zoom In"
          >
            <ZoomIn size={18} />
          </button>
          <button
            onClick={() => handleZoom(0.8)}
            style={{ padding: '6px', borderRadius: '6px', color: 'var(--text-muted)', background: 'transparent' }}
            title="Zoom Out"
          >
            <ZoomOut size={18} />
          </button>
          <button
            onClick={handleFit}
            style={{ padding: '6px', borderRadius: '6px', color: 'var(--text-muted)', background: 'transparent' }}
            title="Fit to Screen"
          >
            <Maximize2 size={18} />
          </button>
        </div>

        {/* Node Detail Drawer (Floats on right when node selected) */}
        {selectedNode && (
          <div style={{
            position: 'absolute',
            top: '16px',
            right: '16px',
            width: '320px',
            background: 'rgba(17, 24, 39, 0.95)',
            backdropFilter: 'blur(10px)',
            border: '1px solid var(--border-color)',
            borderRadius: '10px',
            padding: '18px',
            boxShadow: '0 8px 30px rgba(0,0,0,0.5)',
            fontSize: '0.82rem'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
              <span className="badge badge-purple" style={{ textTransform: 'uppercase' }}>
                {selectedNode.risk_level}
              </span>
              <button onClick={() => setSelectedNode(null)} style={{ color: 'var(--text-dim)', padding: '2px' }}>
                <X size={16} />
              </button>
            </div>

            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff', marginBottom: '4px' }}>
              {selectedNode.customer_name || `Account #${selectedNode.account_id}`}
            </h3>
            <div className="mono" style={{ fontSize: '0.74rem', color: 'var(--text-dim)', marginBottom: '14px' }}>
              {selectedNode.account_number || `ACC-${selectedNode.account_id}`}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', color: 'var(--text-muted)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Account ID:</span>
                <strong style={{ color: '#fff' }}>#{selectedNode.account_id}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Known Fraud:</span>
                <strong style={{ color: selectedNode.is_fraud ? '#f87171' : '#34d399' }}>
                  {selectedNode.is_fraud ? 'YES (Confirmed)' : 'No Prior Offenses'}
                </strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Network Degree:</span>
                <strong style={{ color: '#fff' }}>{selectedNode.degree} linked accounts</strong>
              </div>
              {selectedNode.shared_merchants_with_center > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Shared Merchants:</span>
                  <strong style={{ color: '#fbbf24' }}>{selectedNode.shared_merchants_with_center} merchants</strong>
                </div>
              )}
            </div>

            {!selectedNode.is_center && (
              <button
                onClick={() => {
                  setAccountId(selectedNode.account_id);
                  setSearchParams({ account: selectedNode.account_id });
                  loadRing(selectedNode.account_id, hops);
                }}
                style={{
                  marginTop: '16px',
                  width: '100%',
                  background: 'var(--bg-primary)',
                  border: '1px solid #3b82f6',
                  color: '#60a5fa',
                  padding: '8px',
                  borderRadius: '6px',
                  fontWeight: 600,
                  fontSize: '0.78rem',
                  cursor: 'pointer'
                }}
              >
                Re-Center Graph on This Account
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

