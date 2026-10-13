# Models

## Candidates
- **Pix2Pix (Isola et al.)** — paired, UNet + PatchGAN, L1 + cGAN. Baseline for HEMIT.
- **Pix2PixHD** — high-res paired.
- **Dual-Branch Pix2Pix (HEMIT)** — ResNet CNN + Swin Transformer + FMF, SOTA 0.875 SSIM, 29.88 PSNR. Clone from HEMIT repo.
- **CycleGAN (Zhu et al.)** — unpaired, ResNet generator, cycle-consistency + identity. For DAPI->H&E.
- **CUT / SACSI-CUT** — contrastive unpaired, less hallucination, self-attention + cellular intensity loss.
- **RegGAN / mSIGHT / DGR** — registration network to handle misalignment, +23.8% PSNR when misaligned.
- **D-VST (Diffusion Transformer)** — pathology encoder + tone encoder (CLIP ViT) + curriculum learning + frequency-aware WSI sampling. Best quality but slow.
- **Palette / BBDM Diffusion** — conditional diffusion for DAPI->H&E.

## Metrics
- Pixel: SSIM, PSNR (HEMIT reports 0.875/29.88), LPIPS, DISTS, FID/KID (mSIGHT FID 125 vs 321 Pix2Pix)
- Bio: Dice (nuclei seg), MSE per channel (mSIGHT DAPI 0.12), cell density correlation, Pearson R 0.746
- Human: blind pathologist 52% (DGR)

## Checkpoints
Save in `resources/models/checkpoints/` (git-lfs) or HF Hub. ONNX export for docker.
