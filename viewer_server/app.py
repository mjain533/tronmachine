from flask import Flask, request, jsonify, send_file, abort
import os
import uuid
from werkzeug.utils import secure_filename
try:
    from aicspylibczi import CziFile as AiCziFile
    HAVE_AICS = False  # Disable aicspylibczi due to dimension specification issues
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
                # try read_mosaic to get dimensions
                elif hasattr(cz, 'read_mosaic'):
                    # Try to read with default dimensions first
                    try:
                        sample = cz.read_mosaic(C=0)  # Specify channel 0
                        sample = np.asarray(sample)
                        if sample.ndim >= 3:
                            z_count = sample.shape[1] if sample.ndim >= 4 else 1
                            c_count = sample.shape[0] if sample.ndim >= 4 else 1
                        else:
                            z_count = 1
                            c_count = 1
                        meta = {'filename': os.path.basename(path), 'sizes': {'z': z_count, 'c': c_count}, 'method': 'read_mosaic'}
                        return jsonify(meta)
                    except Exception as e:
                        app.logger.warning(f'read_mosaic with C=0 failed: {e}, trying without C')
                        # Fallback: try to get dimensions from file info
                        try:
                            # Try to read a small sample to determine dimensions
                            sample = cz.read_mosaic()
                            sample = np.asarray(sample)
                            if sample.ndim >= 3:
                                z_count = sample.shape[1] if sample.ndim >= 4 else 1
                                c_count = sample.shape[0] if sample.ndim >= 4 else 1
                            else:
                                z_count = 1
                                c_count = 1
                            meta = {'filename': os.path.basename(path), 'sizes': {'z': z_count, 'c': c_count}, 'method': 'read_mosaic_fallback'}
                            return jsonify(meta)
                        except Exception as e2:
                            app.logger.warning(f'read_mosaic fallback failed: {e2}')
                            # If both fail, use defaults
                            meta = {'filename': os.path.basename(path), 'sizes': {'z': 1, 'c': 1}, 'method': 'default'}
                            return jsonify(meta)
                # try metadata/dim info
                elif hasattr(cz, 'metadata') and cz.metadata is not None:
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
            # aics can extract plane by indexes; get dimensions from the file
            try:
                # Try to get shape information using available methods
                if hasattr(cz, 'get_shape'):
                    shapes = cz.get_shape()
                    z_count = int(shapes.get('Z', 1))
                    c_count = int(shapes.get('C', 1))
                elif hasattr(cz, 'read_mosaic'):
                    # Use read_mosaic to get dimensions
                    sample = cz.read_mosaic()
                    sample = np.asarray(sample)
                    # Assume standard CZI format: (C, Z, Y, X) or similar
                    if sample.ndim >= 3:
                        z_count = sample.shape[1] if sample.ndim >= 4 else 1
                        c_count = sample.shape[0] if sample.ndim >= 4 else 1
                    else:
                        z_count = 1
                        c_count = 1
                else:
                    # Default fallback
                    z_count = 1
                    c_count = 1
                
                z = max(0, min(z, z_count-1))
                c = max(0, min(c, c_count-1))
                
                # Try different methods to read the plane
                if hasattr(cz, 'read_mosaic'):
                    # Use read_mosaic with specific channel and z-slice
                    try:
                        # Try to read the specific plane directly
                        plane = cz.read_mosaic(C=c, Z=z)
                        plane = np.asarray(plane)
                    except Exception as e:
                        app.logger.warning(f'read_mosaic with C={c}, Z={z} failed: {e}, trying full read')
                        # Fallback: read full data and extract plane
                        try:
                            full_data = cz.read_mosaic(C=c)  # Read specific channel
                            full_data = np.asarray(full_data)
                            if full_data.ndim >= 3:
                                # Assume (Z, Y, X) format for single channel
                                if z < full_data.shape[0]:
                                    plane = full_data[z, :, :]
                                else:
                                    plane = full_data[0, :, :]  # Use first Z if requested Z doesn't exist
                            else:
                                plane = full_data
                        except Exception as e2:
                            app.logger.warning(f'read_mosaic fallback failed: {e2}, using default')
                            # Last resort: try to read without specifying dimensions
                            try:
                                full_data = cz.read_mosaic()
                                full_data = np.asarray(full_data)
                                if full_data.ndim >= 4:
                                    # Assume (C, Z, Y, X) format
                                    c_idx = min(c, full_data.shape[0] - 1)
                                    z_idx = min(z, full_data.shape[1] - 1)
                                    plane = full_data[c_idx, z_idx, :, :]
                                elif full_data.ndim == 3:
                                    # Assume (Z, Y, X) or (C, Y, X) format
                                    if z_count > 1:
                                        z_idx = min(z, full_data.shape[0] - 1)
                                        plane = full_data[z_idx, :, :]
                                    else:
                                        c_idx = min(c, full_data.shape[0] - 1)
                                        plane = full_data[c_idx, :, :]
                                else:
                                    plane = full_data
                            except Exception as e3:
                                app.logger.error(f'All read_mosaic attempts failed: {e3}')
                                raise e3
                else:
                    # If no suitable method, fall through to czifile
                    raise AttributeError("No suitable read method found")
                    
            except Exception as e:
                # If aics fails, fall through to czifile
                app.logger.warning(f'aics methods failed: {e}, falling back to czifile')
                raise e
        else:
            # Simple czifile approach - go back to basics
            with CziFile(path) as czi:
                arr = czi.asarray()
                arr = np.asarray(arr)
                shape = arr.shape
                app.logger.info(f'CZI array shape: {shape}, ndim: {arr.ndim}')
                
                # Simple approach: just squeeze and take slices
                plane = arr
                
                # Squeeze out all dimensions of size 1
                plane = np.squeeze(plane)
                app.logger.info(f'After squeeze: {plane.shape}')
                
                # If we still have more than 2 dimensions, take slices
                while plane.ndim > 2:
                    if plane.shape[0] > 1:
                        # Take the requested slice from the first dimension
                        if plane.ndim == 4 and plane.shape[0] == 4:  # First dimension is channels (4)
                            plane = plane[c, ...]  # Take requested channel
                            app.logger.info(f'Selected channel {c} from {plane.shape[0]} channels')
                        elif plane.ndim == 3 and plane.shape[0] == 12:  # First dimension is something else (12)
                            plane = plane[0, ...]  # Take first slice of this dimension
                            app.logger.info(f'Selected first slice from dimension of size 12')
                        else:
                            plane = plane[0, ...]  # Take first slice
                    else:
                        plane = plane[0, ...]  # Remove dimension of size 1
                    plane = np.squeeze(plane)
                    app.logger.info(f'After dimension reduction: {plane.shape}')
                
                app.logger.info(f'Final plane shape: {plane.shape}')

        # Ensure 2D and normalize, then apply channel colors
        plane = np.squeeze(plane)
        if plane.dtype != np.uint8:
            pmin = float(np.min(plane)) if np.size(plane)>0 else 0.0
            pmax = float(np.max(plane)) if np.size(plane)>0 else 0.0
            app.logger.info(f'Channel {c}, Z {z}: min={pmin:.2f}, max={pmax:.2f}, mean={np.mean(plane):.2f}')
            if pmax > pmin:
                plane = (255.0 * (plane - pmin) / (pmax - pmin)).astype(np.uint8)
            else:
                plane = np.zeros_like(plane, dtype=np.uint8)
        
        # Apply channel colors
        if plane.ndim == 2:
            # Create RGB image
            colored_plane = np.zeros((plane.shape[0], plane.shape[1], 3), dtype=np.uint8)
            
            if c == 0:  # Channel 1 - Green
                colored_plane[:, :, 1] = plane  # Green channel
            elif c == 1:  # Channel 2 - Red  
                colored_plane[:, :, 0] = plane  # Red channel
            elif c == 2:  # Channel 3 - Blue
                colored_plane[:, :, 2] = plane  # Blue channel
            elif c == 3:  # Channel 4 - White (all channels)
                colored_plane[:, :, 0] = plane  # Red
                colored_plane[:, :, 1] = plane  # Green  
                colored_plane[:, :, 2] = plane  # Blue
            else:  # Default to grayscale
                colored_plane[:, :, 0] = plane
                colored_plane[:, :, 1] = plane
                colored_plane[:, :, 2] = plane
                
            plane = colored_plane

        out_path = os.path.join(UPLOAD_DIR, f"{id}_z{z}_c{c}.png")
        imageio.imwrite(out_path, plane)
        return send_file(out_path, mimetype='image/png')
    except Exception as e:
        tb = traceback.format_exc()
        app.logger.error('slice error: %s', tb)
        return jsonify({'error': str(e), 'trace': tb}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
