import React, { useCallback, useState, useRef } from 'react';
import './CziUpload.css';
import { useNavigate } from 'react-router-dom';

function readableSize(bytes) {
  if (bytes === 0) return '0 B';
  const units = ['B','KB','MB','GB','TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return (bytes / Math.pow(1024, i)).toFixed(2) + ' ' + units[i];
}

export default function CziUpload() {
  const [files, setFiles] = useState([]);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const acceptExt = ['.czi'];

  const handleFiles = useCallback((incoming) => {
    const arr = Array.from(incoming);
    const good = [];
    const bad = [];
    arr.forEach(f => {
      const lower = f.name.toLowerCase();
      if (acceptExt.some(ext => lower.endsWith(ext))) good.push(f);
      else bad.push(f);
    });

    if (bad.length) {
      setError(`Ignored ${bad.length} file(s) with unsupported extensions.`);
    } else {
      setError(null);
    }

    if (good.length) {
      setFiles(prev => [...prev, ...good]);
    }
  }, []);

  const onDrop = (ev) => {
    ev.preventDefault();
    handleFiles(ev.dataTransfer.files);
  };

  const onBrowse = (ev) => {
    handleFiles(ev.target.files);
    ev.target.value = null;
  };

  const removeAt = (idx) => setFiles(prev => prev.filter((_,i) => i!==idx));

  const clearAll = () => { setFiles([]); setError(null); };

  const prepareUpload = () => {
    if (!files.length) { setError('No CZI files selected'); return; }
    alert(`Preparing ${files.length} file(s) for upload:` + '\n' + files.map(f => `${f.name} (${readableSize(f.size)})`).join('\n'));
  };

  const uploadAndOpen = async () => {
    if (!files.length) { setError('No CZI files selected'); return; }
    setError(null);
    const file = files[0];
    try {
      const fd = new FormData();
      fd.append('file', file, file.name);
      const resp = await fetch('/api/upload', { method: 'POST', body: fd });
      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(txt || `Upload failed: ${resp.status}`);
      }
      const data = await resp.json();
      if (!data.id) throw new Error('Invalid server response');
      navigate(`/viewer/${data.id}`);
    } catch (err) {
      console.error(err);
      setError('Upload failed: ' + (err.message || err));
    }
  };

  // --- Preview section ---
  const [previewUrl, setPreviewUrl] = useState(null);
  const [previewName, setPreviewName] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState(null);
  const fileBeingPreviewed = useRef(null);

  const openPreview = async (file) => {
    setPreviewError(null);
    setPreviewLoading(true);
    fileBeingPreviewed.current = file;
    setPreviewName(file.name);

    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
  };

  const closePreview = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setPreviewName(null);
    setPreviewLoading(false);
    setPreviewError(null);
    fileBeingPreviewed.current = null;
  };

  const serverFallback = async () => {
    const file = fileBeingPreviewed.current;
    if (!file) return;
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const fd = new FormData();
      fd.append('file', file, file.name);
      const resp = await fetch('/api/preview', { method: 'POST', body: fd });
      if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
      const blob = await resp.blob();
      const blobUrl = URL.createObjectURL(blob);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(blobUrl);
      setPreviewLoading(false);
    } catch (err) {
      console.error(err);
      setPreviewError('Preview not available. Provide a server endpoint at /api/preview to convert CZI to PNG for preview.');
      setPreviewLoading(false);
    }
  };

  return (
    <div className="czi-root">
      <div className="czi-card">
        <h2>Upload CZI Files</h2>

        <div className="dropzone" onDragOver={(e)=>e.preventDefault()} onDrop={onDrop}>
          <p>Drag & drop .czi files here, or</p>
          <label className="browse-label">
            <input type="file" accept=".czi" multiple onChange={onBrowse} />
            Browse files
          </label>
        </div>

        {error && <div className="czi-error">{error}</div>}

        <div className="file-list">
          {files.length === 0 && <div className="file-empty">No files selected</div>}
          {files.map((f, idx) => (
            <div className="file-row" key={idx} onClick={() => openPreview(f)} title="Click to preview">
              <div className="file-meta">
                <div className="file-name">{f.name}</div>
                <div className="file-size">{readableSize(f.size)}</div>
              </div>
              <button className="file-remove" onClick={(e) => { e.stopPropagation(); removeAt(idx); }}>Remove</button>
            </div>
          ))}
        </div>

        <div className="czi-actions">
          <button className="btn-secondary" onClick={clearAll}>Clear</button>
          <button className="btn-primary" onClick={prepareUpload}>Prepare Upload</button>
          <button className="btn-primary" onClick={uploadAndOpen}>Upload & Open</button>
          <button className="btn-link" onClick={() => navigate('/portal')}>Return</button>
        </div>
      </div>

      {previewUrl && (
        <div className="preview-overlay" onClick={closePreview}>
          <div className="preview-card" onClick={(e)=>e.stopPropagation()}>
            <div className="preview-header">
              <div className="preview-title">{previewName}</div>
              <button className="preview-close" onClick={closePreview}>Close</button>
            </div>
            <div className="preview-body">
              {previewLoading && <div className="preview-loading">Loading preview…</div>}
              {previewError && <div className="preview-error">{previewError}</div>}
              {!previewLoading && !previewError && (
                <img src={previewUrl} alt={previewName} onError={() => serverFallback()} onLoad={() => setPreviewLoading(false)} />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
