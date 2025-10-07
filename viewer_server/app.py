from flask import Flask, request, jsonify, send_file, abort
import os
import uuid
from werkzeug.utils import secure_filename
try:
    from aicspylibczi import CziFile as AiCziFile
    HAVE_AICS = True
except Exception:
    AiCziFile = None
    HAVE_AICS = False

from czifile import CziFile
import imageio.v2 as imageio
import numpy as np
import traceback

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)

@app.route('/api/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return 'No file', 400
    f = request.files['file']
    filename = secure_filename(f.filename)
    id = str(uuid.uuid4())
    dest = os.path.join(UPLOAD_DIR, f"{id}.czi")
    f.save(dest)
    return jsonify({'id': id, 'filename': filename})

@app.route('/api/metadata/<id>')
def metadata(id):
    path = os.path.join(UPLOAD_DIR, f"{id}.czi")
    if not os.path.exists(path):
        return 'Not found', 404
    try:
        # Try aics first (faster metadata), fallback to czifile
        if HAVE_AICS and AiCziFile is not None:
            try:
                cz = AiCziFile(path)
                # try get_shape if available
                if hasattr(cz, 'get_shape'):
                    shapes = cz.get_shape()
                    z_count = int(shapes.get('Z', 1))
                    c_count = int(shapes.get('C', 1))
                    meta = {'filename': os.path.basename(path), 'sizes': {'z': z_count, 'c': c_count}, 'raw_shape': shapes}
                    return jsonify(meta)
                # try metadata/dim info
                if hasattr(cz, 'metadata') and cz.metadata is not None:
                    md = cz.metadata
                    # attempt common keys
                    z_count = int(getattr(md, 'Z', md.get('Z', 1)) if isinstance(md, dict) else 1)
                    c_count = int(getattr(md, 'C', md.get('C', 1)) if isinstance(md, dict) else 1)
                    meta = {'filename': os.path.basename(path), 'sizes': {'z': z_count, 'c': c_count}, 'raw_meta': str(type(md))}
                    return jsonify(meta)
                # if none of the above work, fall through to czifile fallback
            except Exception:
                app.logger.exception('aics metadata parsing failed, falling back to czifile')

        # czifile fallback
        with CziFile(path) as czi:
            arr = czi.asarray()
            arr = np.asarray(arr)
            shape = arr.shape
            # Heuristic: assume last two dims are Y,X. Z and C before them.
            z_count = 1
            c_count = 1
            if arr.ndim >= 3:
                # try detection: if shape length >=4 then likely (C,Z,Y,X) or (Z,C,Y,X)
                # we'll fallback to find axis with small size >1
                for i,s in enumerate(shape[:-2]):
                    if s > 1:
                        # prefer first >1 as channel or z; we can't be certain
                        if c_count == 1:
                            c_count = int(s)
                        else:
                            z_count = int(s)
            meta = {'filename': os.path.basename(path), 'sizes': {'z': z_count, 'c': c_count}, 'shape': shape}
            return jsonify(meta)
    except Exception as e:
        tb = traceback.format_exc()
        app.logger.error('metadata error: %s', tb)
        return jsonify({'error': str(e), 'trace': tb}), 500

@app.route('/api/slice/<id>')
def slice_endpoint(id):
    z = int(request.args.get('z', 0))
    c = int(request.args.get('c', 0))
    path = os.path.join(UPLOAD_DIR, f"{id}.czi")
    if not os.path.exists(path):
        return 'Not found', 404
    try:
        if HAVE_AICS and AiCziFile is not None:
            cz = AiCziFile(path)
            # aics can extract plane by indexes; request shape map
            shapes = cz.get_shape()
            z_count = int(shapes.get('Z', 1))
            c_count = int(shapes.get('C', 1))
            z = max(0, min(z, z_count-1))
            c = max(0, min(c, c_count-1))
            # read single plane as numpy array (Y,X) or (Y,X,C)
            plane = cz.read_region(c=c, z=z)
            plane = np.asarray(plane)
        else:
            with CziFile(path) as czi:
                arr = czi.asarray()
                arr = np.asarray(arr)
                shape = arr.shape
                # attempt to detect Z and C axes
                # assume last two dims are Y,X
                backend_z = None
                backend_c = None
                if arr.ndim >= 3:
                    # check dims before last two
                    pre = shape[:-2]
                    if len(pre) == 1:
                        # single pre-dim: ambiguous -> treat as Z
                        backend_z = 0
                        z_count = pre[0]
                    elif len(pre) >= 2:
                        # assume last two of pre are C and Z or Z and C; choose bigger dim as Z
                        if pre[-1] >= pre[-2]:
                            backend_z = len(pre) - 1
                            backend_c = len(pre) - 2
                        else:
                            backend_z = len(pre) - 2
                            backend_c = len(pre) - 1
                # default counts
                z_count = int(shape[backend_z]) if backend_z is not None else 1
                c_count = int(shape[backend_c]) if backend_c is not None else 1
                if backend_z is not None:
                    z = max(0, min(z, z_count-1))
                    plane = np.take(arr, indices=z, axis=backend_z)
                else:
                    plane = arr
                plane = np.squeeze(plane)
                # if we still have channel dim, pick requested channel
                if plane.ndim > 2:
                    # assume channel axis is first
                    plane = plane[..., min(c, plane.shape[-1]-1)]

        # Ensure 2D grayscale and normalize
        plane = np.squeeze(plane)
        if plane.dtype != np.uint8:
            pmin = float(np.min(plane)) if np.size(plane)>0 else 0.0
            pmax = float(np.max(plane)) if np.size(plane)>0 else 0.0
            if pmax > pmin:
                plane = (255.0 * (plane - pmin) / (pmax - pmin)).astype(np.uint8)
            else:
                plane = np.zeros_like(plane, dtype=np.uint8)

        out_path = os.path.join(UPLOAD_DIR, f"{id}_z{z}_c{c}.png")
        imageio.imwrite(out_path, plane)
        return send_file(out_path, mimetype='image/png')
    except Exception as e:
        tb = traceback.format_exc()
        app.logger.error('slice error: %s', tb)
        return jsonify({'error': str(e), 'trace': tb}), 500

if __name__ == '__main__':
    app.run(port=5001, debug=True)
