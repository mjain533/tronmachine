import React from 'react';
import './PortalMain.css';

export default function PortalMain({ navigate }) {
  return (
    <div className="portal-root">
      <div className="portal-card">
        <h2 className="portal-title">Please select a program.</h2>
        <div className="portal-body">
          <button
            className="portal-button"
            onClick={() => navigate('/upload')}
          >
            Quantify Neuronal Migration
          </button>
        </div>
        <div className="portal-footer">
          <button className="portal-link" onClick={() => navigate('/')}>Return to Home</button>
        </div>
      </div>
    </div>
  );
}
