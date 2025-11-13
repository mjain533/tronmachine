// src/App.js
import './App.css';
import React from 'react';
import uwcrest from './uwcrest.png';
import PortalMain from './PortalMain';
import CziUpload from './CziUpload';
import CziViewer from './CziViewer';
import AnalysisViewer from './AnalysisViewer';
import { BrowserRouter as Router, Routes, Route, Link, useNavigate } from 'react-router-dom';

function Home() {
  const navigate = useNavigate();

  return (
    <div className="App">
      <div className="App-left">
        <img src={uwcrest} className="App-logo" alt="UW Crest" />
        <h1>Dent Lab’s Tron Machine</h1>
      </div>

      <div className="App-right">
        <p>Exploring neuroscience and technology at UW–Madison</p>
        <div className="App-links">
          <a
            href="https://dent.neuro.wisc.edu"
            target="_blank"
            rel="noopener noreferrer"
          >
            Dent Lab Website
          </a>
          <button className="link-button" onClick={() => navigate('/portal')}>
            Tron Machine Portal
          </button>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/portal" element={<PortalMain />} />
        <Route path="/upload" element={<CziUpload />} />
        <Route path="/viewer/:id" element={<CziViewer />} />
        <Route path="/analysis/:id" element={<AnalysisViewer />} />
        <Route path="*" element={<Home />} />
      </Routes>
    </Router>
  );
}
