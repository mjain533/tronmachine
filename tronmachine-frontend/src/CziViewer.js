import React, { useEffect, useState } from 'react';
import './CziViewer.css';

function useIdFromPath() {
  const path = window.location.pathname;
  const match = path.match(/\/viewer\/(.+)$/);
  return match ? match[1] : null;
}

export default function CziViewer({ navigate }) {
  const id = useIdFromPath();
  const [meta, setMeta] = useState(null);
  const [zIndex, setZIndex] = useState(0);
  const [channel, setChannel] = useState(0);
  const [sliceUrl, setSliceUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!id) return;
    const fetchMeta = async () => {
      setLoading(true);
      try {
        const r = await fetch(`/api/metadata/${id}`);
        if (!r.ok) throw new Error('Failed to fetch metadata');
        const j = await r.json();
        setMeta(j);
        setZIndex(0);
      } catch (err) { setError(err.message); }
      setLoading(false);
    };
    fetchMeta();
  }, [id]);

  useEffect(() => {
    if (!meta) return;
    const fetchSlice = async () => {
      setLoading(true);
      try {
        const r = await fetch(`/api/slice/${id}?z=${zIndex}&c=${channel}`);
        if (!r.ok) {
          // try to parse json error
          let body = null;
          try { body = await r.json(); } catch(e) { /* ignore */ }
          const msg = body && body.error ? `${body.error}` : `Failed to fetch slice (${r.status})`;
          throw new Error(msg);
        }
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        setSliceUrl(url);
      } catch (err) { setError(err.message); }
      setLoading(false);
    };
    fetchSlice();
    return () => { if (sliceUrl) URL.revokeObjectURL(sliceUrl); };
  }, [meta, zIndex]);

  if (!id) return <div className="viewer-root">Invalid viewer id</div>;

  return (
    <div className="viewer-root">
      <div className="viewer-header">
        <button onClick={() => navigate('/upload')}>Back</button>
        <div className="viewer-title">CZI Viewer — {meta ? meta.filename : id}</div>
      </div>
      <div className="viewer-body">
        {error && <div className="viewer-error">{error}</div>}
        {loading && <div className="viewer-loading">Loading…</div>}
        {!loading && sliceUrl && (
          <img className="viewer-image" src={sliceUrl} alt={`z=${zIndex}`} />
        )}
      </div>
      {meta && (
        <div className="viewer-controls">
          <button onClick={() => setZIndex(z => Math.max(0, z-1))}>Prev Z</button>
          <span>Z: {zIndex + 1} / {meta.sizes.z}</span>
          <button onClick={() => setZIndex(z => Math.min(meta.sizes.z - 1, z+1))}>Next Z</button>
          {meta.sizes.c > 1 && (
            <label style={{marginLeft:12}}>
              Channel:
              <select value={channel} onChange={(e)=>{ setChannel(parseInt(e.target.value)); setZIndex(0); }}>
                {Array.from({length: meta.sizes.c}).map((_,i)=> (
                  <option key={i} value={i}>{i+1}</option>
                ))}
              </select>
            </label>
          )}
        </div>
      )}
    </div>
  );
}
