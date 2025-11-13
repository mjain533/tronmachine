import React, { useEffect, useState } from "react";
import "./CziViewer.css";
import { useParams, useNavigate } from "react-router-dom";

export default function AnalysisViewer() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [imageUrl, setImageUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchAnalysisImage = async () => {
      setLoading(true);
      try {
        const r = await fetch(`https://tronmachine-backend.onrender.com/api/analyze_img_combined/${id}`);
        if (!r.ok) throw new Error(`Failed to fetch analysis image (${r.status})`);
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        setImageUrl(url);
      } catch (err) {
        setError(err.message);
      }
      setLoading(false);
    };

    if (id) fetchAnalysisImage();

    return () => {
      if (imageUrl) URL.revokeObjectURL(imageUrl);
    };
  }, [id]);

  return (
    <div className="viewer-root">
      <div className="viewer-header">
        <button onClick={() => navigate(-1)}>← Back</button>
        <div className="viewer-title">Analysis Results — {id}</div>
      </div>

      <div
        className="viewer-body"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "70vh",
          background: "#f7f7f7",
          borderRadius: 8,
        }}
      >
        {error && <div className="viewer-error">{error}</div>}
        {loading && <div className="viewer-loading">Analyzing...</div>}
        {!loading && imageUrl && (
          <img
            src={imageUrl}
            alt="Analysis Result"
            style={{
              maxWidth: "95%",
              maxHeight: "85vh",
              borderRadius: 10,
              boxShadow: "0 0 10px rgba(0,0,0,0.2)",
            }}
          />
        )}
      </div>
    </div>
  );
}
