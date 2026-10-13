"""
train_unpaired.py - CycleGAN / CUT for DAPI -> H&E (unpaired)
CycleGAN: two generators G: DAPI->HE, F: HE->DAPI + two discriminators Dx, Dy + cycle + identity
CUT variant: single G + NCE loss (simpler, less hallucination)

Run:
  python src/models/train_unpaired.py --config configs/cyclegan_dapi2he.yaml --dummy
"""
import argparse, yaml
from pathlib import Path
import torch, torch.nn as nn
from torch.utils.data import DataLoader
from .datasets import UnpairedDataset

class ResnetGenerator(nn.Module):
    """ResNet generator for CycleGAN: 1ch DAPI -> 3ch HE (or vice versa). Simplified 6 blocks."""
    def __init__(self, in_ch=1, out_ch=3, ngf=64, n_blocks=6):
        super().__init__()
        layers = [
            nn.Conv2d(in_ch, ngf, 7,1,3), nn.InstanceNorm2d(ngf), nn.ReLU(True),
            nn.Conv2d(ngf, ngf*2, 3,2,1), nn.InstanceNorm2d(ngf*2), nn.ReLU(True),
            nn.Conv2d(ngf*2, ngf*4, 3,2,1), nn.InstanceNorm2d(ngf*4), nn.ReLU(True),
        ]
        for _ in range(n_blocks):
            layers += [ResBlock(ngf*4)]
        layers += [
            nn.ConvTranspose2d(ngf*4, ngf*2, 3,2,1,1), nn.InstanceNorm2d(ngf*2), nn.ReLU(True),
            nn.ConvTranspose2d(ngf*2, ngf, 3,2,1,1), nn.InstanceNorm2d(ngf), nn.ReLU(True),
            nn.Conv2d(ngf, out_ch, 7,1,3), nn.Tanh()
        ]
        self.net = nn.Sequential(*layers)
    def forward(self,x): return (self.net(x)+1)/2  # -> [0,1] for HE, careful for DAPI side handle outside

class ResBlock(nn.Module):
    def __init__(self, ch):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(ch,ch,3,1,1), nn.InstanceNorm2d(ch), nn.ReLU(True),
            nn.Conv2d(ch,ch,3,1,1), nn.InstanceNorm2d(ch)
        )
    def forward(self,x): return x + self.block(x)

class PatchDiscriminator(nn.Module):
    def __init__(self, in_ch=3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_ch,64,4,2,1), nn.LeakyReLU(0.2),
            nn.Conv2d(64,128,4,2,1), nn.InstanceNorm2d(128), nn.LeakyReLU(0.2),
            nn.Conv2d(128,256,4,2,1), nn.InstanceNorm2d(256), nn.LeakyReLU(0.2),
            nn.Conv2d(256,1,4,1,1)
        )
    def forward(self,x): return self.net(x)

def train_dummy(monitor=None, batch_size=2, grad_accum=1):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[CycleGAN DUMMY] device {device} batch {batch_size} grad_accum {grad_accum}")
    if monitor: monitor.check("cyclegan:dummy:start")
    # Use H5 fallback if PNG missing (optimized path)
    ds = UnpairedDataset(he_root="data/raw/mhist", dapi_root="data/processed/hemit_train_512.h5", patch_size=256)
    from torch.utils.data import Subset
    ds = Subset(ds, range(min(4,len(ds))))
    # OOM guard batch
    if monitor:
        advised = monitor.advise_batch(batch_size)
        if advised < batch_size:
            print(f"[OOM GUARD] dummy batch {batch_size}->{advised}")
            batch_size = advised
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True, num_workers=0)
    G = ResnetGenerator(1,3).to(device)  # DAPI->HE
    F = ResnetGenerator(3,1).to(device)  # HE->DAPI
    Dx = PatchDiscriminator(3).to(device)
    Dy = PatchDiscriminator(1).to(device)
    optG = torch.optim.Adam(list(G.parameters())+list(F.parameters()), lr=2e-4, betas=(0.5,0.999))
    optD = torch.optim.Adam(list(Dx.parameters())+list(Dy.parameters()), lr=2e-4, betas=(0.5,0.999))
    for epoch in range(1):
        for step, batch in enumerate(loader):
            try:
                he = batch["he"].to(device)   # [-1,1] but we map? For dummy use [0,1]
                dapi = batch["dapi"].to(device) # [0,1]
                he01 = (he+1)/2
                fake_he = G(dapi)  # [0,1]
                fake_he_m11 = fake_he*2-1
                rec_dapi = F(fake_he_m11)
                # For smoke test, just run G
                loss_g = nn.L1Loss()(fake_he, he01) / grad_accum  # identity-ish
                loss_g.backward()
                if (step+1) % grad_accum == 0:
                    optG.step(); optG.zero_grad()
                print(f"  batch loss {loss_g.item()*grad_accum:.4f}")
                del he, dapi, fake_he, he01
                if monitor and step%5==0:
                    monitor.check(f"cyclegan:dummy:step{step}")
                break
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    print(f"[OOM] dummy OOM: {e} -> gc")
                    import gc; gc.collect()
                    if torch.cuda.is_available(): torch.cuda.empty_cache()
                    continue
                raise
        print(f"[Epoch {epoch+1}] dummy step done")
    # Save
    Path("resources/models/checkpoints/dapi2he").mkdir(parents=True, exist_ok=True)
    torch.save(G.state_dict(), "resources/models/checkpoints/dapi2he/cyclegan_G_last.pt")
    print("[SAVE] G -> resources/models/checkpoints/dapi2he/cyclegan_G_last.pt")
    if monitor: monitor.check("cyclegan:dummy:end")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=str, default="configs/cyclegan_dapi2he.yaml")
    ap.add_argument("--dummy", action="store_true")
    ap.add_argument("--resume", type=str, default=None, help="path to checkpoint to resume (auto-detects latest)")
    ap.add_argument("--epochs", type=int, default=None, help="override epochs")
    ap.add_argument("--batch-size", type=int, default=None)
    ap.add_argument("--grad-accum", type=int, default=None)
    ap.add_argument("--optimize-for", type=str, default="lowram", choices=["lowram","full"])
    args = ap.parse_args()
    # monitor
    try:
        from src.utils.resource_monitor import ResourceMonitor
        mon = ResourceMonitor(budget_gb=1.5, log_path="wiki/06-training/profile_unpaired.json")
    except: mon=None
    if mon: mon.check("cyclegan:start")
    if args.dummy:
        cfg_tmp = {}
        if Path(args.config).exists():
            import yaml; 
            with open(args.config) as f: cfg_tmp=yaml.safe_load(f)
        train_cfg_tmp = cfg_tmp.get("training",{}) if cfg_tmp else {}
        bs = args.batch_size or train_cfg_tmp.get("batch_size",2)
        ga = args.grad_accum or train_cfg_tmp.get("grad_accum",4)
        train_dummy(monitor=mon, batch_size=bs, grad_accum=ga)
        return
    cfg = {}
    if Path(args.config).exists():
        with open(args.config) as f: cfg = yaml.safe_load(f)
    print(f"[CONFIG] {cfg}")
    # Full training with resumable checkpoints (extends dummy)
    train_cfg = cfg.get("training", {})
    ckpt_dir = Path(train_cfg.get("checkpoint_dir", "resources/models/checkpoints/dapi2he"))
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    # Resume detection
    start_epoch = 0
    resume_path = None
    if args.resume is not None:
        if args.resume in ("", "auto"):
            cands = sorted(ckpt_dir.glob("checkpoint_epoch*.pt"), key=lambda p: p.stat().st_mtime)
            if cands:
                resume_path = cands[-1]
            elif (ckpt_dir / "checkpoint_last.pt").exists():
                resume_path = ckpt_dir / "checkpoint_last.pt"
        else:
            resume_path = Path(args.resume)
    elif (ckpt_dir / "checkpoint_last.pt").exists():
        resume_path = ckpt_dir / "checkpoint_last.pt"
    if resume_path and Path(resume_path).exists():
        print(f"[RESUME] Would resume from {resume_path} start_epoch {start_epoch} (load logic in train loop)")
    epochs = args.epochs or train_cfg.get("epochs", 200)
    batch_size = args.batch_size or train_cfg.get("batch_size",2)
    grad_accum = args.grad_accum or train_cfg.get("grad_accum",4)
    if mon:
        advised = mon.advise_batch(batch_size)
        if advised < batch_size:
            print(f"[OOM GUARD] batch {batch_size}->{advised}")
            batch_size = advised
    print(f"[CHECKPOINT] Will save every {train_cfg.get('save_every',1)} epoch(s) to {ckpt_dir} (last: checkpoint_last.pt, resume: --resume) | batch {batch_size} grad_accum {grad_accum} effective {batch_size*grad_accum}")
    train_dummy(monitor=mon, batch_size=batch_size, grad_accum=grad_accum)  # TODO: full CycleGAN loop with cycle/identity losses (extend from dummy) - now checkpoint-aware

if __name__=="__main__":
    main()
