// CziViewer.jsx
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./CziViewer.css";

function useIdFromPath() {
  const path = window.location.pathname;
  const match = path.match(/\/viewer\/(.+)$/);
  return match ? match[1] : null;
}

export default function CziViewer() {
  const id = useIdFromPath();
  const navigate = useNavigate();
  const [meta, setMeta] = useState(null);
  const [zIndex, setZIndex] = useState(0);
  const [channel, setChannel] = useState(0);
  const [sliceUrl, setSliceUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [keptSlices, setKeptSlices] = useState({ start: 0, end: 0 });

  // fetch metadata
  useEffect(() => {
    if (!id) return;
    (async () => {
      setLoading(true);
      try {
        console.debug("[viewer] fetching metadata for", id);
        const r = await fetch(`/api/metadata/${id}`);
        if (!r.ok) throw new Error(`metadata ${r.status}`);
        const j = await r.json();
        setMeta(j);
        setZIndex(0);
      } catch (err) {
        console.error("[viewer] meta error", err);
        setError(err.message || String(err));
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  // fetch slice image (raw)
  useEffect(() => {
    if (!meta) return;
    let active = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const r = await fetch(`/api/slice/${id}?z=${zIndex}&c=${channel}`);
        if (!r.ok) {
          const txt = await r.text().catch(() => null);
          throw new Error(`slice fetch ${r.status} ${txt || ""}`);
        }
        const blob = await r.blob();
        if (!active) return;
        const url = URL.createObjectURL(blob);
        setSliceUrl(prev => {
          if (prev) URL.revokeObjectURL(prev);
          return url;
        });
      } catch (err) {
        console.error("[viewer] slice fetch error", err);
        setError(err.message || String(err));
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [meta, zIndex, channel, id]);

  // Preprocess batch (keeps slices saved on server)
  async function startPreprocess() {
    if (!meta) return alert("no metadata");
    const start = Number(document.getElementById("sliceStart").value);
    const end = Number(document.getElementById("sliceEnd").value);
    const applyAll = document.getElementById("applyAll").checked;
    if (!start || !end || start < 1 || end > meta.sizes.z || start > end) {
      alert("Invalid slice range");
      return;
    }
    try {
      setLoading(true);
      const r1 = await fetch("/api/slices/keep", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, keepRange: [start, end], applyAll }),
      });
      const j1 = await r1.json();
      if (j1.error) throw new Error(j1.error);
      setKeptSlices({ start, end });

      const r2 = await fetch(`/api/preprocess/${id}/batch?c=${channel}`);
      const j2 = await r2.json();
      if (j2.error) throw new Error(j2.error);
      alert(`Preprocessing complete for ${start}–${end}`);
    } catch (err) {
      console.error("[viewer] preprocess failed", err);
      alert("Preprocess error: " + (err.message || err));
    } finally {
      setLoading(false);
    }
  }

  // Run analysis, wait for response, then navigate to /analysis/:id
 async function runAnalysis() {
  if (!keptSlices.start) {
    alert("Please run preprocess first and set slice range.");
    return;
  }
  try {
    setLoading(true);
    console.debug("[viewer] starting analyze");

    // Call the Flask /api/analyze endpoint
    const r = await fetch(
      `/api/analyze/${id}?c=${channel}`
    );
    const j = await r.json();

    if (r.ok && !j.error) {
      console.debug("[viewer] analyze done", j);
      // wait a short moment to allow server to flush files (helps race)
      await new Promise(res => setTimeout(res, 300));

      // navigate to AnalysisViewer
      navigate(`/analysis/${id}`);
    } else {
      throw new Error(j.error || "analysis failed");
    }
  } catch (err) {
    console.error("[viewer] analyze error", err);
    alert("Analysis failed: " + (err.message || err));
  } finally {
    setLoading(false);
  }
}


  if (!id) return <div className="viewer-root">Invalid viewer id</div>;

  return (
    <div className="viewer-root">
      <div className="viewer-header">
        <button onClick={() => window.location.href = "/upload"}>Back</button>
        <div className="viewer-title">CZI Viewer — {meta ? meta.filename : id}</div>
      </div>

      <div className="viewer-body" style={{ display: "flex", gap: 20 }}>
        {meta && (
          <div style={{ width: 270, padding: 16, background: "#ddd", borderRadius: 8 }}>
            <div style={{ marginBottom: 8 }}>
              <b>Displaying:</b>{" "}
              <input type="text" value={meta.filename} readOnly style={{ width: 140 }} />
            </div>

            <div style={{ marginBottom: 8 }}>
              <b>Select Slices:</b><br />
              <input id="sliceStart" type="number" min={1} max={meta.sizes.z} defaultValue={1} style={{width:70}} />{" "}
              thru{" "}
              <input id="sliceEnd" type="number" min={1} max={meta.sizes.z} defaultValue={meta.sizes.z} style={{width:70}} />
            </div>

            <div style={{ marginBottom: 8 }}>
              <input id="applyAll" type="checkbox" /> <label htmlFor="applyAll">Apply to all</label>
            </div>

            <button onClick={startPreprocess} disabled={loading} style={{ display: "block", marginBottom: 8 }}>
              Run Preprocess (batch)
            </button>

            <button onClick={runAnalysis} disabled={loading || !keptSlices.start} style={{ display: "block" }}>
              Run Analysis → Open Analysis Viewer
            </button>
          </div>
        )}

        <div style={{ flex: 1 }}>
          <div style={{ height: "70vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#fafafa", borderRadius: 8 }}>
            {loading && <div className="viewer-loading">Loading…</div>}
            {error && <div style={{color:"red"}}>{error}</div>}
            {!loading && sliceUrl && <img src={sliceUrl} alt={`z=${zIndex}`} style={{maxHeight:"70vh", maxWidth:"100%"}} />}
          </div>

          {meta && (
            <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 12 }}>
              <div>
                <button onClick={() => setZIndex(z => Math.max(0, z - 1))} disabled={zIndex <= 0}>‹</button>
                <input type="range" min={0} max={meta.sizes.z - 1} value={zIndex} onChange={e => setZIndex(Number(e.target.value))} />
                <button onClick={() => setZIndex(z => Math.min(meta.sizes.z - 1, z + 1))} disabled={zIndex >= meta.sizes.z - 1}>›</button>
                <span style={{marginLeft:8}}>{zIndex + 1}/{meta.sizes.z}</span>
              </div>

              {meta.sizes.c > 1 && (
                <div>
                  Channel{" "}
                  <select value={channel} onChange={e => { setChannel(Number(e.target.value)); setZIndex(0); }}>
                    {Array.from({length: meta.sizes.c}).map((_,i)=> <option key={i} value={i}>Chan {i+1}</option>)}
                  </select>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
