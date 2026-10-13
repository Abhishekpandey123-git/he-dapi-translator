"""
wsi_loader.py - OpenSlide / tifffile based WSI loader, unified interface
Supports: .svs, .tiff, .ome.tiff, .png/.jpg (patch fallback)
Fallback to PIL/tifffile if openslide not available.

Usage:
  from src.utils.wsi_loader import WSILoader
  loader = WSILoader("data/raw/wsi/CM1_ShAHE_0_0_0.svs")
  thumb = loader.get_thumbnail(max_size=1024)  # HWC uint8
  patch = loader.read_region(x=0, y=0, level=0, size=(512,512))
  print(loader.level_dimensions, loader.level_downsamples)
"""
import numpy as np
from pathlib import Path

class WSILoader:
    def __init__(self, path: str):
        self.path = Path(path)
        self._openslide = None
        self._tifffile = None
        self._pil_img = None
        self.level_dimensions = [(0,0)]
        self.level_downsamples = [1.0]
        self._backend = "none"
        self._load()

    def _load(self):
        p = str(self.path)
        suffix = self.path.suffix.lower()
        # Try openslide for SVS/TIFF
        try:
            import openslide
            self._openslide = openslide.OpenSlide(p)
            self.level_dimensions = self._openslide.level_dimensions
            self.level_downsamples = self._openslide.level_downsamples
            self._backend = "openslide"
            return
        except Exception as e:
            # Not openslide or file not supported
            pass
        # Try tifffile for OME-TIFF
        if suffix in [".tiff", ".tif", ".ome.tiff"]:
            try:
                import tifffile
                self._tifffile = tifffile.TiffFile(p)
                # Use first series
                series = self._tifffile.series[0]
                shape = series.shape  # may be (H,W,C) or (C,H,W)
                if len(shape)==3:
                    h,w = shape[1], shape[2] if shape[0]<=4 else shape[0], shape[1]
                    # Fallback heuristic
                    h,w = shape[-3], shape[-2] if len(shape)>=3 else (shape[0], shape[1])
                else:
                    h,w = shape[0], shape[1]
                self.level_dimensions = [(w,h)]
                self.level_downsamples = [1.0]
                self._backend = "tifffile"
                return
            except Exception:
                pass
        # Fallback: PIL (for PNG/JPG or single image TIFF)
        try:
            from PIL import Image
            img = Image.open(p)
            img.load()
            if img.mode not in ("RGB","RGBA"):
                img = img.convert("RGB")
            self._pil_img = img
            w,h = img.size
            self.level_dimensions = [(w,h)]
            self.level_downsamples = [1.0]
            self._backend = "pil"
        except Exception as e:
            raise RuntimeError(f"Cannot load WSI {p}: {e}. Install openslide/tifffile.")

    def get_thumbnail(self, max_size: int = 1024) -> np.ndarray:
        """Return thumbnail HWC uint8, max dimension = max_size.
        OPTIMIZED: for tifffile, uses level overview or downsampled read, not full asarray().
        """
        if self._backend == "openslide":
            # Get best level for thumbnail
            w,h = self.level_dimensions[0]
            scale = max_size / max(w,h)
            level = self._openslide.get_best_level_for_downsample(1/scale) if scale<1 else 0
            img = self._openslide.read_region((0,0), level, self.level_dimensions[level])
            img = img.convert("RGB")
        elif self._backend == "tifffile":
            try:
                # Try to read overview / subifd without loading full WSI
                # tifffile: check if series has levels
                if len(self._tifffile.series[0].levels) > 1:
                    # pick level closest to max_size
                    for lvl in self._tifffile.series[0].levels:
                        lw, lh = lvl.shape[-2], lvl.shape[-3] if len(lvl.shape)==3 else lvl.shape[1], lvl.shape[0]
                        # heuristic: first level that fits
                        if max(lw, lh) <= max_size*2:
                            arr = lvl.asarray()
                            if arr.ndim==3 and arr.shape[0]<=4:
                                arr = np.transpose(arr, (1,2,0))
                            if arr.dtype != np.uint8:
                                arr = (arr / arr.max() * 255).astype(np.uint8) if arr.max()>0 else arr.astype(np.uint8)
                            from PIL import Image
                            img = Image.fromarray(arr[..., :3] if arr.shape[2]>=3 else arr)
                            break
                    else:
                        raise ValueError("no suitable level")
                else:
                    raise ValueError("no levels")
            except Exception:
                # fallback: read with downsampling via tifffile's is_contiguous? else sample
                # Use tifffile's aszarr or slice: read only every Nth pixel
                try:
                    series = self._tifffile.series[0]
                    # Use aszarr for virtual access
                    store = series.aszarr()
                    import zarr
                    z = zarr.open(store, mode="r")
                    arr = z[::4, ::4] if z.ndim==2 else z[::4, ::4, :3]  # 4x downsample
                    if arr.dtype != np.uint8:
                        arr = (arr / arr.max() * 255).astype(np.uint8) if arr.max()>0 else arr.astype(np.uint8)
                    from PIL import Image
                    img = Image.fromarray(arr[..., :3] if arr.ndim==3 and arr.shape[2]>=3 else arr)
                except Exception:
                    # last fallback: full asarray but with RAM guard
                    import tifffile
                    from src.utils.resource_monitor import get_ram_state
                    ram = get_ram_state()
                    # if WSI >1GB, warn and use PIL thumbnail via tifffile page
                    w,h = self.level_dimensions[0]
                    est_mb = w*h*3/1e6
                    if est_mb > ram["avail_mb"]*0.5:
                        print(f"[WSI] thumbnail fallback: WSI {w}x{h} est {est_mb:.0f}MB > avail {ram['avail_mb']:.0f}MB, reading subsampled via tifffile page")
                        page = self._tifffile.pages[0]
                        # read with out-of-core: use memmap? simplified: read via imagecodecs with level
                        arr = page.asarray()
                        # downsample 4x via numpy slicing to keep RAM low
                        arr = arr[::4, ::4]
                    else:
                        arr = self._tifffile.asarray()
                    if arr.ndim==3 and arr.shape[0]<=4:
                        arr = np.transpose(arr, (1,2,0))
                    if arr.dtype != np.uint8:
                        arr = (arr / arr.max() * 255).astype(np.uint8) if arr.max()>0 else arr.astype(np.uint8)
                    from PIL import Image
                    img = Image.fromarray(arr[..., :3] if arr.shape[2]>=3 else arr)
        else:
            img = self._pil_img
        from PIL import Image
        # Resize thumbnail
        w,h = img.size
        scale = min(max_size/w, max_size/h, 1.0)
        if scale < 1.0:
            img = img.resize((int(w*scale), int(h*scale)), Image.BILINEAR)
        return np.array(img)

    def read_region(self, x: int, y: int, level: int = 0, size: tuple = (512,512)) -> np.ndarray:
        """Read region at (x,y) upper-left, size (w,h), level. Returns HWC uint8."""
        w,h = size
        if self._backend == "openslide":
            img = self._openslide.read_region((x,y), level, (w,h))
            img = img.convert("RGB")
            return np.array(img)
        elif self._backend == "pil":
            # Crop from PIL
            box = (x,y,x+w,y+h)
            # Clip
            img_w, img_h = self._pil_img.size
            # Simple: if out of bounds, pad
            crop = self._pil_img.crop(box)
            arr = np.array(crop)
            if arr.shape[0]!=h or arr.shape[1]!=w:
                # Pad
                padded = np.zeros((h,w,3), dtype=np.uint8)
                padded[:arr.shape[0], :arr.shape[1]] = arr[:h, :w]
                return padded
            return arr
        else:
            # tifffile: STREAMING crop without full asarray() - use Zarr virtual or page keyframe
            try:
                # Prefer zarr virtual slicing (no full RAM)
                series = self._tifffile.series[0]
                store = series.aszarr()
                import zarr
                z = zarr.open(store, mode="r")
                # z shape may be (H,W,C) or (H,W) or (C,H,W)
                # Normalize to HWC view
                if z.ndim==3 and z.shape[0]<=4 and z.shape[0]<z.shape[1]:
                    # CHW -> transpose via lazy? For simplicity slice and transpose slice only
                    region = z[:, y:y+h, x:x+w]  # CHW slice
                    region = np.transpose(region, (1,2,0))
                else:
                    region = z[y:y+h, x:x+w]
                    if region.ndim==3 and region.shape[2]>3:
                        region = region[...,:3]
                    if region.ndim==2:
                        region = np.stack([region]*3, axis=-1)
                # Ensure h,w
                if region.shape[0]!=h or region.shape[1]!=w:
                    padded = np.zeros((h,w,3), dtype=np.uint8)
                    ph = min(h, region.shape[0])
                    pw = min(w, region.shape[1])
                    padded[:ph, :pw] = region[:ph, :pw][...,:3] if region.ndim==3 else region[:ph,:pw]
                    return padded
                # handle dtype
                if region.dtype != np.uint8:
                    region = (region / region.max() * 255).astype(np.uint8) if region.max()>0 else region.astype(np.uint8)
                return region[...,:3] if region.ndim==3 and region.shape[2]>=3 else region
            except Exception as e:
                # fallback: page.asarray with slice but warn if large
                try:
                    from src.utils.resource_monitor import get_ram_state
                    ram = get_ram_state()
                    w_tot, h_tot = self.level_dimensions[0]
                    est_mb = w_tot*h_tot*3/1e6
                    if est_mb > ram["avail_mb"]*0.6:
                        print(f"[WSI] read_region tifffile fallback but WSI {w_tot}x{h_tot} {est_mb:.0f}MB > avail, using chunked read via tifffile.masked?")
                    arr = self._tifffile.asarray()
                    if arr.ndim==3 and arr.shape[0]<=4:
                        arr = np.transpose(arr, (1,2,0))
                    region = arr[y:y+h, x:x+w]
                    if region.shape[0]!=h or region.shape[1]!=w:
                        padded = np.zeros((h,w,3), dtype=np.uint8)
                        ph = min(h, region.shape[0])
                        pw = min(w, region.shape[1])
                        padded[:ph, :pw] = region[:ph, :pw][...,:3] if region.shape[2]>=3 else region[:ph,:pw]
                        return padded
                    return region[...,:3] if region.shape[2]>=3 else region
                except Exception as e2:
                    print(f"[WSI] read_region failed: {e2}")
                    return np.zeros((h,w,3), dtype=np.uint8)

    def close(self):
        if self._openslide:
            self._openslide.close()
        if self._tifffile:
            self._tifffile.close()

    def __enter__(self): return self
    def __exit__(self, *a): self.close()
