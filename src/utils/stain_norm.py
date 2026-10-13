"""
stain_norm.py - Macenko & Reinhard stain normalization for H&E (critical for domain shift)
Refs:
  Macenko et al. 2009 - "A method for normalizing histology slides for quantitative analysis"
  Reinhard et al. 2001 - Color transfer
Used in WORKPLAN Phase 1 & 4: reduces OOD rejection.

Usage:
  from src.utils.stain_norm import MacenkoNormalizer, ReinhardNormalizer
  norm = MacenkoNormalizer(target_path="data/examples/he_example.png")
  he_norm = norm.transform(he_image)  # uint8 HxWx3
"""
import numpy as np

class MacenkoNormalizer:
    """
    Macenko method: estimate stain vectors via SVD in OD space.
    Simplified implementation without full deconvolution - good for demo.
    For production: use `stainlib` or `torchstain`.
    """
    def __init__(self, target_path: str = None, target_image: np.ndarray = None):
        self.target_concentrations = None
        self.target_stain_matrix = None
        if target_path or target_image is not None:
            if target_path:
                from PIL import Image
                target_image = np.array(Image.open(target_path).convert("RGB"))
            self.fit(target_image)

    def fit(self, target: np.ndarray):
        """Estimate stain matrix from target HE image (HxWx3, uint8)"""
        # Convert to OD: OD = -log((I+1)/240)
        od = self._rgb_to_od(target)
        # Remove transparent pixels (OD < 0.15)
        od = od.reshape(-1, 3)
        od = od[np.all(od > 0.15, axis=1)]
        if len(od) < 100:
            # Fallback: identity
            self.target_stain_matrix = np.array([[0.65,0.70,0.29],[0.07,0.99,0.11]])
            return
        # SVD
        _, _, Vt = np.linalg.svd(od, full_matrices=False)
        # First two vectors are stain vectors
        stain_matrix = Vt[:2]
        # Normalize
        stain_matrix = stain_matrix / np.linalg.norm(stain_matrix, axis=1, keepdims=True)
        self.target_stain_matrix = stain_matrix
        # Store concentration percentiles for normalization (99th percentile)
        # Solve OD = C @ Stain  -> C = OD @ pinv(Stain^T)? Use lstsq: Stain^T C^T = OD^T
        conc = np.linalg.lstsq(stain_matrix.T, od.T, rcond=None)[0].T  # Nx2
        self.target_concentrations = np.percentile(conc, 99, axis=0)

    def transform(self, image: np.ndarray) -> np.ndarray:
        """Normalize image to target stain distribution"""
        if self.target_stain_matrix is None:
            return image  # no fit
        od = self._rgb_to_od(image)
        h,w,_ = od.shape
        od_flat = od.reshape(-1,3)
        # Estimate source stain matrix
        od_valid = od_flat[np.all(od_flat > 0.15, axis=1)]
        if len(od_valid) < 100:
            return image
        _, _, Vt = np.linalg.svd(od_valid, full_matrices=False)
        src_matrix = Vt[:2]
        src_matrix = src_matrix / np.linalg.norm(src_matrix, axis=1, keepdims=True)
        # Deconvolve: conc = OD * pinv(stain) via lstsq
        src_conc = np.linalg.lstsq(src_matrix.T, od_flat.T, rcond=None)[0].T
        # Normalize concentrations to target 99th percentile
        src_percentile = np.percentile(src_conc, 99, axis=0)
        # Avoid divide by zero
        scale = self.target_concentrations / (src_percentile + 1e-6)
        src_conc = src_conc * scale
        # Reconstruct with target stain
        od_norm = np.dot(src_conc, self.target_stain_matrix)
        od_norm = od_norm.reshape(h,w,3)
        # Convert back to RGB
        rgb = self._od_to_rgb(od_norm)
        return rgb.astype(np.uint8)

    @staticmethod
    def _rgb_to_od(img):
        # OD = -log((I+1)/240)  (as in Macenko)
        img = img.astype(np.float32)
        od = -np.log((img + 1) / 240.0)
        return od

    @staticmethod
    def _od_to_rgb(od):
        rgb = 240 * np.exp(-od) - 1
        rgb = np.clip(rgb, 0, 255)
        return rgb

class ReinhardNormalizer:
    """Reinhard color transfer in LAB space - faster, less accurate than Macenko"""
    def __init__(self, target_path: str = None, target_image: np.ndarray = None):
        self.target_mean = None
        self.target_std = None
        if target_path or target_image is not None:
            if target_path:
                from PIL import Image
                target_image = np.array(Image.open(target_path).convert("RGB"))
            self.fit(target_image)

    def fit(self, target: np.ndarray):
        try:
            from skimage.color import rgb2lab
        except ImportError:
            # Fallback to simple RGB mean/std
            self.target_mean = target.mean(axis=(0,1))
            self.target_std = target.std(axis=(0,1)) + 1e-6
            self._use_lab = False
            return
        self._use_lab = True
        lab = rgb2lab(target)
        self.target_mean = lab.mean(axis=(0,1))
        self.target_std = lab.std(axis=(0,1)) + 1e-6

    def transform(self, image: np.ndarray) -> np.ndarray:
        if self.target_mean is None:
            return image
        if not getattr(self, "_use_lab", True):
            # Simple RGB standardization
            mean = image.mean(axis=(0,1))
            std = image.std(axis=(0,1)) + 1e-6
            norm = (image - mean) / std * self.target_std + self.target_mean
            return np.clip(norm, 0, 255).astype(np.uint8)
        from skimage.color import rgb2lab, lab2rgb
        lab = rgb2lab(image)
        mean = lab.mean(axis=(0,1))
        std = lab.std(axis=(0,1)) + 1e-6
        lab_norm = (lab - mean) / std * self.target_std + self.target_mean
        rgb = lab2rgb(lab_norm) * 255
        return np.clip(rgb, 0, 255).astype(np.uint8)

def get_normalizer(name: str, target_path: str = None):
    if name == "macenko":
        return MacenkoNormalizer(target_path)
    elif name == "reinhard":
        return ReinhardNormalizer(target_path)
    else:
        return None  # No-op
