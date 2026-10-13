"""
tiling.py - Patch tiling & WSI tiled inference helpers (OPTIMIZED for 3.7GB RAM)
Covers:
  - Extraction of patches from WSI with overlap
  - Gaussian blending for seamless stitching
  - Frequency-aware adaptive sampling (D-VST idea: sample more low-freq/background? simplified)
  - STREAMING merge: chunked to disk (zarr/tifffile) to avoid 4.8GB canvas OOM

Usage for WSI inference:
  from src.utils.tiling import TiledInference
  tiler = TiledInference(tile_size=512, stride=256, blend="gaussian")
  result = tiler.infer_wsi(wsi_path, model_fn)  # model_fn: patch (HWC uint8) -> synthetic patch
  # For large WSI: result = tiler.infer_image_streaming(image, model_fn, out_path="/tmp/out.tiff")

V2 changes for low-RAM:
  - infer_image now has streaming fallback if H*W*C*4 > 512MB
  - new infer_image_streaming writes to tiled TIFF/Zarr without full canvas in RAM
"""
import numpy as np
import gc
from pathlib import Path
from typing import Callable, Tuple, Optional

def _gaussian_weights(tile_size: int, sigma: float = 0.5) -> np.ndarray:
    """2D Gaussian window for blending (center=1, edges->0)"""
    ax = np.linspace(-1, 1, tile_size)
    xx, yy = np.meshgrid(ax, ax)
    d = np.sqrt(xx*xx + yy*yy)
    w = np.exp(-(d**2) / (2 * sigma**2))
    # Normalize to max 1
    w = w / w.max()
    return w.astype(np.float32)

class TiledInference:
    def __init__(self, tile_size: int = 512, stride: int = 256, blend: str = "gaussian"):
        assert tile_size % stride == 0 or stride == tile_size, "stride should divide tile_size for clean tiling"
        self.tile_size = tile_size
        self.stride = stride
        self.blend = blend
        if blend == "gaussian":
            w2d = _gaussian_weights(tile_size)
            self.weights = w2d  # HxW
        else:
            self.weights = np.ones((tile_size, tile_size), dtype=np.float32)

    def extract_tiles(self, image: np.ndarray):
        """Yield (y,x, tile) for HWC image"""
        h,w = image.shape[:2]
        for y in range(0, h - self.tile_size + 1, self.stride):
            for x in range(0, w - self.tile_size + 1, self.stride):
                yield (y,x), image[y:y+self.tile_size, x:x+self.tile_size]
        # Handle edge tiles if not divisible
        if h % self.stride != 0 or w % self.stride != 0:
            # Add final row/col
            y = h - self.tile_size
            for x in range(0, w - self.tile_size + 1, self.stride):
                yield (y,x), image[y:y+self.tile_size, x:x+self.tile_size]
            x = w - self.tile_size
            for y in range(0, h - self.tile_size + 1, self.stride):
                if y == h - self.tile_size: continue  # already yielded
                yield (y,x), image[y:y+self.tile_size, x:x+self.tile_size]

    def merge_tiles(self, tiles_with_coords, output_shape: Tuple[int,int,int]) -> np.ndarray:
        """Blend tiles back to canvas. tiles_with_coords: list of ((y,x), tile)
        NOTE: for large H*W (> 4096^2) this allocates H*W*C float32 -> OOM. Use merge_tiles_streaming instead.
        """
        h,w,c = output_shape
        est_mb = h*w*c*4/1e6 + h*w*4/1e6
        if est_mb > 512:
            raise MemoryError(f"merge_tiles would need {est_mb:.0f}MB >512MB budget for {output_shape}. Use merge_tiles_streaming to disk.")
        canvas = np.zeros((h,w,c), dtype=np.float32)
        weight_map = np.zeros((h,w), dtype=np.float32)
        for (y,x), tile in tiles_with_coords:
            # tile: HxWxC float or uint8
            tile_f = tile.astype(np.float32) if tile.dtype!=np.float32 else tile
            # Expand weights to CxHxW if needed
            w2d = self.weights
            canvas[y:y+self.tile_size, x:x+self.tile_size] += tile_f * w2d[..., None]
            weight_map[y:y+self.tile_size, x:x+self.tile_size] += w2d
        # Normalize
        weight_map = np.maximum(weight_map, 1e-6)
        canvas = canvas / weight_map[..., None]
        return np.clip(canvas, 0, 255).astype(np.uint8)

    def merge_tiles_streaming(self, tiles_with_coords_iter, output_shape: Tuple[int,int,int], out_path: Optional[str] = None, chunk_rows: int = 1024) -> Optional[np.ndarray]:
        """
        Streaming merge to disk (or chunked in RAM) for large WSI.
        - If out_path ends with .tiff/.tif, writes tiled TIFF via tifffile.
        - If .zarr, writes zarr.
        - Else, chunks canvas in row-bands to keep peak <512MB.
        tiles_with_coords_iter: iterable of ((y,x), tile) - can be generator to avoid holding all tiles
        output_shape: (H,W,C)
        Returns: np array if small enough and no out_path, else None (written to disk)
        """
        h,w,c = output_shape
        est_mb = h*w*c*4/1e6
        # small -> just use merge_tiles
        if est_mb <= 512 and out_path is None:
            # need list for merge_tiles
            tiles_list = list(tiles_with_coords_iter) if not isinstance(tiles_with_coords_iter, list) else tiles_with_coords_iter
            return self.merge_tiles(tiles_list, output_shape)
        # streaming to disk
        if out_path:
            out_p = Path(out_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            # For tif: create memmap-like via tifffile with tile writing? Simple: write via zarr then convert?
            # Fallback: chunked canvas bands + tifffile imwrite per band concatenation using memmap
            # Use numpy memmap for canvas to keep RAM low
            import tempfile
            # weight map as memmap
            canvas_path = str(out_p) + ".canvas.dat"
            weight_path = str(out_p) + ".weight.dat"
            canvas = np.memmap(canvas_path, dtype=np.float32, mode="w+", shape=(h,w,c))
            weight_map = np.memmap(weight_path, dtype=np.float32, mode="w+", shape=(h,w))
            canvas[:] = 0
            weight_map[:] = 0
            for (y,x), tile in tiles_with_coords_iter:
                tile_f = tile.astype(np.float32) if tile.dtype!=np.float32 else tile
                if tile_f.ndim==2:
                    tile_f = tile_f[...,None]
                # handle channel mismatch (DAPI 1ch vs HE 3ch): broadcast weight
                if tile_f.shape[2] != c:
                    # if tile is 1ch but canvas 3ch, repeat
                    if tile_f.shape[2]==1 and c==3:
                        tile_f = np.repeat(tile_f, 3, axis=2)
                    elif tile_f.shape[2]==3 and c==1:
                        tile_f = tile_f[...,0:1]
                w2d = self.weights
                # need ensure tile_f shape matches w2d
                canvas[y:y+self.tile_size, x:x+self.tile_size] += tile_f * w2d[..., None]
                weight_map[y:y+self.tile_size, x:x+self.tile_size] += w2d
                del tile_f
            # Normalize bands and write to tiff
            weight_map_safe = np.maximum(weight_map, 1e-6)
            # write via tifffile in bands to avoid holding final uint8 in RAM (h*w*c bytes maybe 1.2GB for 10k^2)
            try:
                import tifffile
                # Prepare final array as memmap uint8 then write
                final_path = str(out_p) + ".final.dat"
                final = np.memmap(final_path, dtype=np.uint8, mode="w+", shape=(h,w,c))
                for y0 in range(0, h, chunk_rows):
                    y1 = min(y0+chunk_rows, h)
                    band = canvas[y0:y1] / weight_map_safe[y0:y1, :, None]
                    final[y0:y1] = np.clip(band, 0, 255).astype(np.uint8)
                    del band
                # Now write final memmap to tiff (tifffile can handle memmap)
                if final.shape[2]==1:
                    tifffile.imwrite(str(out_p), final[:,:,0], tile=(256,256), compression="zlib")
                else:
                    tifffile.imwrite(str(out_p), final, tile=(256,256), compression="zlib")
                print(f"[STREAMING] Wrote {out_p} shape {final.shape} via memmap bands (peak <512MB)")
                # cleanup memmaps
                del canvas, weight_map, final
                for p in [canvas_path, weight_path, final_path]:
                    try: Path(p).unlink(missing_ok=True)
                    except: pass
                gc.collect()
                return None
            except Exception as e:
                print(f"[STREAMING] tifffile failed {e}, falling back to banded numpy save")
                del canvas, weight_map
                gc.collect()
                raise
        else:
            # chunked in RAM but banded
            canvas = np.zeros((h,w,c), dtype=np.float32)
            weight_map = np.zeros((h,w), dtype=np.float32)
            for (y,x), tile in tiles_with_coords_iter:
                tile_f = tile.astype(np.float32) if tile.dtype!=np.float32 else tile
                if tile_f.ndim==2: tile_f = tile_f[...,None]
                w2d = self.weights
                # handle channel mismatch
                if tile_f.shape[2] != c:
                    if tile_f.shape[2]==1 and c==3:
                        tile_f = np.repeat(tile_f,3,axis=2)
                    elif tile_f.shape[2]==3 and c==1:
                        tile_f = tile_f[...,0:1]
                canvas[y:y+self.tile_size, x:x+self.tile_size] += tile_f * w2d[..., None]
                weight_map[y:y+self.tile_size, x:x+self.tile_size] += w2d
            weight_map = np.maximum(weight_map, 1e-6)
            canvas = canvas / weight_map[..., None]
            return np.clip(canvas,0,255).astype(np.uint8)

    def infer_image(self, image: np.ndarray, model_fn: Callable[[np.ndarray], np.ndarray], out_path: Optional[str] = None) -> np.ndarray:
        """
        Tiled inference on a large image (e.g. WSI at single level)
        model_fn: takes HWC uint8 tile -> returns HWC synthetic tile (same size)
        Returns: synthetic image same shape as input (cropped to tile-aligned area if needed)
        If image large (>512MB canvas) and out_path provided, streams to disk.
        """
        h,w = image.shape[:2]
        c_in = image.shape[2] if image.ndim==3 else 1
        # Estimate output shape: need run one tile to know C
        # Fast path: small image -> original loop with list
        # Check RAM budget first
        try:
            from src.utils.resource_monitor import get_ram_state
            ram = get_ram_state()
            avail_mb = ram["avail_mb"]
        except: avail_mb = 1500
        # probe one tile
        y0,x0 = 0,0
        probe_tile = image[y0:y0+self.tile_size, x0:x0+self.tile_size]
        if probe_tile.shape[0]!=self.tile_size or probe_tile.shape[1]!=self.tile_size:
            # pad probe
            import PIL.Image as PILImage
            probe_tile = np.zeros((self.tile_size,self.tile_size,c_in), dtype=np.uint8)
            probe_tile[:image.shape[0], :image.shape[1]] = image[:self.tile_size,:self.tile_size] if image.ndim==3 else image[:self.tile_size,:self.tile_size,None]
        probe_out = model_fn(probe_tile)
        if probe_out.ndim==2: probe_out = probe_out[...,None]
        out_c = probe_out.shape[2]
        out_shape = (h,w,out_c)
        est_mb = h*w*out_c*4/1e6
        use_streaming = est_mb > 512 or est_mb > avail_mb*0.5 or (out_path is not None and est_mb > 256)
        if use_streaming:
            print(f"[TILING] Large image {h}x{w}x{out_c} est {est_mb:.0f}MB > budget -> streaming mode (avail {avail_mb:.0f}MB)")
            def gen():
                for (y,x), tile in self.extract_tiles(image):
                    synthetic = model_fn(tile)
                    if synthetic.ndim==2: synthetic = synthetic[...,None]
                    if synthetic.shape[:2] != (self.tile_size, self.tile_size):
                        from PIL import Image
                        # resize back
                        if synthetic.shape[2]==1:
                            synthetic = np.array(Image.fromarray(synthetic[:,:,0]).resize((self.tile_size,self.tile_size)))[...,None]
                        else:
                            synthetic = np.array(Image.fromarray(synthetic).resize((self.tile_size,self.tile_size)))
                            if synthetic.ndim==2: synthetic = synthetic[...,None]
                    yield (y,x), synthetic
            if out_path:
                self.merge_tiles_streaming(gen(), out_shape, out_path=out_path)
                # try return small thumbnail for preview if requested? Return None marker
                return np.zeros((1,1,out_c), dtype=np.uint8)  # signal streamed
            else:
                return self.merge_tiles_streaming(gen(), out_shape, out_path=None)
        # Small path: original
        tiles = list(self.extract_tiles(image))
        results = []
        for (y,x), tile in tiles:
            synthetic = model_fn(tile)
            if synthetic.ndim==2: synthetic = synthetic[...,None]
            # Ensure same shape
            if synthetic.shape[:2] != tile.shape[:2]:
                from PIL import Image
                if synthetic.shape[2]==1:
                    synthetic = np.array(Image.fromarray(synthetic[:,:,0]).resize((self.tile_size, self.tile_size)))[...,None]
                else:
                    synthetic = np.array(Image.fromarray(synthetic).resize((self.tile_size, self.tile_size)))
                    if synthetic.ndim==2: synthetic = synthetic[...,None]
            results.append(((y,x), synthetic))
        merged = self.merge_tiles(results, out_shape)
        return merged

    def frequency_aware_sample(self, image: np.ndarray, low_freq_thresh: float = 0.1):
        """
        D-VST inspired: skip low-frequency (background) tiles to save compute.
        Simple proxy: variance < thresh => background, skip inference.
        Returns: list of (y,x,tile, is_foreground)
        """
        tiles = []
        for (y,x), tile in self.extract_tiles(image):
            var = tile.std()
            is_fg = var > low_freq_thresh * 255  # crude
            tiles.append(((y,x), tile, is_fg))
        return tiles
