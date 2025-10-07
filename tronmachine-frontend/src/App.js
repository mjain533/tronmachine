import './App.css';
import React, { useEffect, useState } from 'react';
import uwcrest from './uwcrest.png'; // Add crest image into src/
import PortalMain from './PortalMain';
import CziUpload from './CziUpload';
import CziViewer from './CziViewer';

function AppContent({ route, navigate }) {
  if (route === '/portal') {
    return <PortalMain navigate={navigate} />;
  }

  if (route === '/upload') {
    return <CziUpload navigate={navigate} />;
  }

  if (route.startsWith('/viewer/')) {
    return <CziViewer navigate={navigate} />;
  }

  return (
    <div className="App">
      <div className="App-left">
        <img src={uwcrest} className="App-logo" alt="UW Crest" />
        <h1>Dent Lab’s Tron Machine</h1>
      </div>

      <div className="App-right">
        <p>Exploring neuroscience and technology at UW–Madison</p>
        <div className="App-links">
          <a href="https://dent.neuro.wisc.edu" target="_blank" rel="noopener noreferrer">
            Dent Lab Website
          </a>
          <button className="link-button" onClick={() => navigate('/portal')}>Tron Machine Portal</button>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [route, setRoute] = useState(window.location.pathname || '/');

  useEffect(() => {
    const onPop = () => setRoute(window.location.pathname);
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const navigate = (to) => {
    if (to === window.location.pathname) return;
    window.history.pushState({}, '', to);
    setRoute(to);
  };

  return <AppContent route={route} navigate={navigate} />;
}

export default App;
