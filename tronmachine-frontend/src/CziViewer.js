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
  }, [meta, zIndex, channel]);

  if (!id) return <div className="viewer-root">Invalid viewer id</div>;

  return (
    <div className="viewer-root">
      <div className="viewer-header">
        <button onClick={() => navigate('/upload')}>Back</button>
        <div className="viewer-title">CZI Viewer — {meta ? meta.filename : id}</div>
      </div>
      <div className="viewer-body" style={{display:'flex',alignItems:'flex-start',justifyContent:'center',minHeight:'60vh',background:'#f7f7f7',borderRadius:8}}>
        {meta && (
          <div className="slice-select-panel" style={{background:'#ddd',padding:16,borderRadius:8,width:270,minWidth:270,marginRight:24,marginTop:0}}>
            <div style={{marginBottom:8}}>
              <label style={{fontWeight:'bold'}}>Displaying:</label>
              <input type="text" value={meta.filename} readOnly style={{marginLeft:8,width:120}} />
            </div>
            <div style={{marginBottom:8}}>
              <label style={{fontWeight:'bold'}}>Select Slices:</label>
              <input type="number" min={1} max={meta.sizes.z} defaultValue={1} id="sliceStart" style={{width:50,marginLeft:8}} />
              <span style={{margin:'0 8px'}}>thru</span>
              <input type="number" min={1} max={meta.sizes.z} defaultValue={meta.sizes.z} id="sliceEnd" style={{width:50}} />
            </div>
            <div style={{marginBottom:8}}>
              <input type="checkbox" id="applyAll" style={{marginRight:4}} />
              <label htmlFor="applyAll">Apply to all (if possible)</label>
            </div>
            <button
              style={{padding:'4px 18px',fontWeight:'bold',borderRadius:4,border:'1px solid #888',background:'#eee',cursor:'pointer'}}
              onClick={async () => {
                const start = parseInt(document.getElementById('sliceStart').value);
                const end = parseInt(document.getElementById('sliceEnd').value);
                const applyAll = document.getElementById('applyAll').checked;
                if (isNaN(start) || isNaN(end) || start < 1 || end > meta.sizes.z || start > end) {
                  alert('Please enter a valid slice range.');
                  return;
                }
                // Send request to backend to delete unwanted slices
                try {
                  const r = await fetch(`/api/slices/keep`, {
                    method: 'POST',
                    headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({
                      id,
                      keepRange: [start, end],
                      applyAll,
                    })
                  });
                  if (!r.ok) throw new Error('Failed to update slices');
                  alert('Slices updated!');
                } catch (err) {
                  alert('Error: ' + err.message);
                }
              }}
            >Next</button>
          </div>
        )}
        <div style={{flex:1,display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',maxHeight:"100vh"}}>
          <div style={{width:'100%',height:'80vh',maxWidth:'100%',display:'flex',alignItems:'center',justifyContent:'center',position:'relative'}}>
            {error && <div className="viewer-error">{error}</div>}
            {loading && <div className="viewer-loading">Loading…</div>}
            {!loading && sliceUrl && (
              <img className="viewer-image" src={sliceUrl} alt={`z=${zIndex}`} style={{maxHeight:'80vh',maxWidth:'100%'}} />
            )}
          </div>
          {meta && (
            <div className="viewer-controls" style={{width:'100%',marginTop:16}}>
              <label style={{marginRight:12, display:'flex', alignItems:'center', gap:8}}>
                Slices:
                <button
                  style={{padding:'2px 8px', fontSize:'1.1em'}}
                  disabled={zIndex <= 1}
                  onClick={() => setZIndex(z => Math.max(0, z-2))}
                >«</button>
                <button
                  style={{padding:'2px 8px', fontSize:'1.1em'}}
                  disabled={zIndex <= 0}
                  onClick={() => setZIndex(z => Math.max(0, z-1))}
                >‹</button>
                <input
                  type="range"
                  min={0}
                  max={meta.sizes.z - 1}
                  value={zIndex}
                  onChange={e => setZIndex(Number(e.target.value))}
                  style={{ verticalAlign: 'middle', margin: '0 8px', width:120 }}
                />
                <button
                  style={{padding:'2px 8px', fontSize:'1.1em'}}
                  disabled={zIndex >= meta.sizes.z - 1}
                  onClick={() => setZIndex(z => Math.min(meta.sizes.z - 1, z+1))}
                >›</button>
                <button
                  style={{padding:'2px 8px', fontSize:'1.1em'}}
                  disabled={zIndex >= meta.sizes.z - 2}
                  onClick={() => setZIndex(z => Math.min(meta.sizes.z - 1, z+2))}
                >»</button>
                <span style={{marginLeft:8}}>{zIndex + 1} / {meta.sizes.z}</span>
              </label>
              {meta.sizes.c > 1 && (
                <label style={{marginLeft:12}}>
                  Channel:
                  <select value={channel} onChange={(e)=>{ setChannel(parseInt(e.target.value)); setZIndex(0); }}>
                    {Array.from({length: meta.sizes.c}).map((_,i)=> {
                      const channelNames = ['Green', 'Red', 'Blue', 'White'];
                      const label = channelNames[i] || `Channel ${i+1}`;
                      return <option key={i} value={i}>{label}</option>;
                    })}
                  </select>
                </label>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
