Viewer server (Python)

This small server accepts CZI uploads and serves metadata and Z-slices as PNGs used by the React viewer.

1) Create a virtualenv (recommended) and install requirements:

   python -m venv .venv
   .venv\Scripts\Activate.ps1   # Windows PowerShell
   pip install -r requirements.txt

2) Run the server:

   python app.py

The server listens on port 5001. The React dev server proxies requests under `/api/*` to it (configure as needed).

Notes
- `czifile` reads CZI files and returns numpy arrays. This simple example chooses a naive Z-indexing strategy and returns a single plane as PNG. For multi-dimensional or multi-channel data you will want to extend the logic.
