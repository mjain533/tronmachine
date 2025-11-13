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
import cv2
import numpy as np
from skimage.filters import threshold_otsu, threshold_local
from scipy.ndimage import gaussian_filter, binary_opening, binary_closing
from skimage.measure import regionprops_table
from scipy.ndimage import label
from PIL import Image, ImageChops

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
# Store kept slices in memory (or you could persist to disk)
kept_slices = {}
@app.route('/api/analyze/<id>')
def analyze(id):
    c = int(request.args.get('c', 0))

    # make sure slices were kept
    if id not in kept_slices:
        return jsonify({'error': 'No kept slices found'}), 400

    start, end = kept_slices[id]['start'], kept_slices[id]['end']
    slices = []

    for z in range(start, end + 1):
        path = os.path.join(UPLOAD_DIR, f"{id}_z{z}_c{c}_mask.png")
        if not os.path.exists(path):
            continue
        img = imageio.imread(path)
        slices.append(img)

    if not slices:
        return jsonify({'error': 'No preprocessed slices found'}), 400

    # Combine slices vertically (or however you want)
    combined = np.vstack(slices)
    out_path = os.path.join(UPLOAD_DIR, f"{id}_analyze_combined_c{c}.png")
    imageio.imwrite(out_path, combined)

    return jsonify({'status': 'ok', 'combined_path': f"/api/analyze_img_combined/{id}/{c}"})

@app.route('/api/analyze_img/<id>/<int:z>/<int:c>')
def get_analyze_img(id, z, c):
    try:
        path = os.path.join(UPLOAD_DIR, f"{id}_z{z}_c{c}_analyze.png")
        if not os.path.exists(path):
            abort(404)
        return send_file(path, mimetype='image/png')
    except Exception as e:
        tb = traceback.format_exc()
        app.logger.error(f'analyze_img error: {tb}')
        return jsonify({'error': str(e), 'trace': tb}), 500
    
@app.route('/api/slices/keep', methods=['POST'])
def keep_slices():
    data = request.get_json()
    id = data.get('id')
    keep_range = data.get('keepRange')  # [start, end]
    apply_all = data.get('applyAll', False)

    if not id or not keep_range or len(keep_range) != 2:
        return jsonify({'error': 'Invalid request'}), 400

    kept_slices[id] = {
        'start': keep_range[0] - 1,  # convert to 0-index
        'end': keep_range[1] - 1,
        'apply_all': apply_all
    }
    return jsonify({'status': 'ok'})

@app.route("/api/analyze_img_combined/<id>")
def get_analyze_img_combined(id):
    folder = os.path.join("analyzed_images", id)
    if not os.path.exists(folder):
        abort(404)

    images = []
    for fname in sorted(os.listdir(folder)):
        if fname.endswith(".png"):
            path = os.path.join(folder, fname)
            img = Image.open(path).convert("RGBA")
            images.append(img)

    if not images:
        abort(404)

    combined = images[0].copy()
    for img in images[1:]:
        combined = Image.alpha_composite(combined, img)

    output_path = os.path.join(folder, "combined_overlay.png")
    combined.save(output_path)
    return send_file(output_path, mimetype="image/png")


@app.route('/api/preprocess/<id>/batch')
def preprocess_batch(id):
    path = os.path.join(UPLOAD_DIR, f"{id}.czi")
    if not os.path.exists(path):
        return 'Not found', 404

    c = int(request.args.get('c', 0))
    blur = request.args.get('blur', 'true').lower() == 'true'
    thresh_mode = request.args.get('threshold', 'otsu')

    # Get kept slice range
    if id not in kept_slices:
        return jsonify({'error': 'No kept slices found'}), 400

    z_start = kept_slices[id]['start']
    z_end = kept_slices[id]['end']

    try:
        with CziFile(path) as czi:
            data = np.asarray(czi.asarray())
            axes = czi.axes
            shape = czi.shape
            axis_idx = {a: i for i, a in enumerate(axes)}

            for z in range(z_start, z_end + 1):
                slicer = [0] * data.ndim
                if 'Z' in axis_idx:
                    slicer[axis_idx['Z']] = z
                if 'C' in axis_idx:
                    slicer[axis_idx['C']] = c
                if 'Y' in axis_idx:
                    slicer[axis_idx['Y']] = slice(None)
                if 'X' in axis_idx:
                    slicer[axis_idx['X']] = slice(None)

                plane = np.squeeze(data[tuple(slicer)]).astype(np.float32)
                pmin, pmax = plane.min(), plane.max()
                if pmax > pmin:
                    plane = (plane - pmin) / (pmax - pmin)
                else:
                    plane[:] = 0.0

                if blur:
                    plane = gaussian_filter(plane, sigma=1.0)

                if thresh_mode == 'otsu':
                    t = threshold_otsu(plane)
                    mask = plane > t
                elif thresh_mode == 'adaptive':
                    local_thresh = threshold_local(plane, 35)
                    mask = plane > local_thresh
                else:
                    try:
                        t = float(thresh_mode)
                        mask = plane > t
                    except ValueError:
                        mask = plane > 0.5

                mask = binary_opening(mask, structure=np.ones((3,3)))
                mask = binary_closing(mask, structure=np.ones((3,3)))

                overlay = np.zeros((*mask.shape, 3), dtype=np.uint8)
                overlay[..., 0] = (plane * 255).astype(np.uint8)
                overlay[..., 1] = np.where(mask, 255, 0)

                out_path = os.path.join(UPLOAD_DIR, f"{id}_z{z}_c{c}_mask.png")
                imageio.imwrite(out_path, overlay)

        return jsonify({'status': 'ok', 'processed_slices': list(range(z_start, z_end + 1))})
    except Exception as e:
        tb = traceback.format_exc()
        app.logger.error(f'batch preprocess error: {tb}')
        return jsonify({'error': str(e), 'trace': tb}), 500

    
@app.route('/api/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return 'No file', 400
    f = request.files['file']
    filename = f.filename
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
            app.logger.info(f'Raw CZI shape: {shape}')
            
            # Look for dimension sizes that match expected patterns
            z_count = 1
            c_count = 1
            
            # Try to find dimensions matching expected sizes
            if arr.ndim >= 4:
                # Find the Z dimension - often around 12-50 slices
                z_count = int (shape[5])
                c_count = int (shape[4])
        

            meta = {'filename': os.path.basename(path), 
                   'sizes': {'z': z_count, 'c': c_count}, 
                   'shape': shape}
            app.logger.info(f'Detected Z count: {z_count}, C count: {c_count}')
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
        with CziFile(path) as czi:
            axes = czi.axes          # e.g. "BHSTCZYX0"
            shape = czi.shape
            app.logger.info(f"CZI axes: {axes}, shape: {shape}")

            data = czi.asarray()
            data = np.asarray(data)
            app.logger.info(f"Array ndim: {data.ndim}, shape: {data.shape}")

            # Find axis indices
            axis_idx = {a: i for i, a in enumerate(axes)}
            z_axis = axis_idx.get("Z", None)
            c_axis = axis_idx.get("C", None)

            # Build slicer
            slicer = [0] * data.ndim  # start with all zeros
            if c_axis is not None:
                slicer[c_axis] = min(c, shape[c_axis] - 1)
            if z_axis is not None:
                slicer[z_axis] = min(z, shape[z_axis] - 1)

            # Turn to slice objects for Y/X axes so we keep them fully
            y_axis = axis_idx.get("Y", None)
            x_axis = axis_idx.get("X", None)
            if y_axis is not None:
                slicer[y_axis] = slice(None)
            if x_axis is not None:
                slicer[x_axis] = slice(None)

            plane = data[tuple(slicer)]
            plane = np.squeeze(plane)
            app.logger.info(f"Extracted plane shape: {plane.shape}")

        # Normalize
        if plane.dtype != np.uint8:
            pmin, pmax = float(plane.min()), float(plane.max())
            if pmax > pmin:
                plane = ((plane - pmin) / (pmax - pmin) * 255).astype(np.uint8)
            else:
                plane = np.zeros_like(plane, dtype=np.uint8)

        # Color map per channel
        if plane.ndim == 2:
            rgb = np.zeros((plane.shape[0], plane.shape[1], 3), dtype=np.uint8)
            if c == 0:
                rgb[..., 1] = plane  # green
            elif c == 1:
                rgb[..., 0] = plane  # red
            elif c == 2:
                rgb[..., 2] = plane  # blue
            elif c == 3:
                rgb[:] = plane[..., None]  # white
            plane = rgb

        out_path = os.path.join(UPLOAD_DIR, f"{id}_z{z}_c{c}.png")
        imageio.imwrite(out_path, plane)
        return send_file(out_path, mimetype='image/png')

    except Exception as e:
        tb = traceback.format_exc()
        app.logger.error('slice error: %s', tb)
        return jsonify({'error': str(e), 'trace': tb}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
    
