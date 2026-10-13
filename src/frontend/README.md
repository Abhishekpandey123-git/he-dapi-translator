# src/frontend - React Drag & Drop UI

Stack: React + Vite + react-dropzone + OpenSeadragon (WSI viewer) + slider compare

Quick start (after npm init):
```
cd src/frontend
npm install
npm run dev  # -> http://localhost:3000
```

Features (per WORKPLAN Phase 3):
- Dropzone: .png .tiff .svs .ome.tiff
- Direction toggle: H&E->DAPI / DAPI->H&E
- Model selector: fast (Pix2Pix) vs quality (Diffusion stub)
- Result: side-by-side slider, download TIFF, watermark SYNTHETIC
- WSI viewer: OpenSeadragon tiled view + overlay confidence heatmap

Backend proxy: vite.config.js proxies /translate -> http://localhost:8000

Stub until React scaffold is created - backend alone works via curl:
```
curl -X POST -F "file=@data/examples/he_example.png" -F "direction=he2dapi" http://localhost:8000/translate --output /tmp/out.png
```
