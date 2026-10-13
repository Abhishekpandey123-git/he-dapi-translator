# src/models

- train_paired.py : Pix2Pix + DISTS loss + dual-branch (CNN+Swin)
- train_unpaired.py : CycleGAN / CUT / SACSI-CUT
- infer.py : patch + WSI tiled inference, ONNX export
- utils/stain_norm.py : Macenko/Reinhard

Configs in `configs/hemit_dual_branch.yaml`

Run:
```
python src/models/train_paired.py --config configs/hemit_dual_branch.yaml
python src/models/infer.py --input data/examples/he_example.png --direction he2dapi
```
