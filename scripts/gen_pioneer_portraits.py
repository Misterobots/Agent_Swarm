#!/usr/bin/env python3
"""
Generate flat-vector pioneer portraits via local ComfyUI (SDXL Turbo) and write
them to ui/public/pioneers/<name>.png, then downscale + palette-quantize for the
repo. These back PioneerPortrait (ui/src/components/swarm/pioneer-portrait.tsx),
which renders the PNG with the hand-SVG bust as the automatic fallback.

Why SDXL Turbo and not Flux: ComfyUI on this box runs in a ~12.5 GB-RAM context.
Flux's load spikes system RAM past that ceiling (even though it runs on the GPU);
SDXL Turbo (~6.9 GB) fits with headroom. There is a RAM guard below regardless.

Usage:
    python scripts/gen_pioneer_portraits.py [name1,name2,...]   # subset, default = all
Env:
    COMFYUI_HOST   default http://localhost:8188
    PIONEER_OUT    default ui/public/pioneers
"""
import json, urllib.request, urllib.parse, urllib.error, time, random, os, sys, glob

COMFY = os.getenv("COMFYUI_HOST", "http://localhost:8188")
OUT = os.getenv("PIONEER_OUT", os.path.join(os.path.dirname(__file__), "..", "ui", "public", "pioneers"))
CKPT = "sd_xl_turbo_1.0_fp16.safetensors"

# Pioneer → descriptor (era + signature features drive the likeness).
DESC = {
    "shannon": "Claude Shannon, mid-20th-century American man, short neat dark hair, round glasses, suit and bow tie",
    "minsky": "Marvin Minsky, balding older man, glasses, small goatee, suit",
    "johnson": "Katherine Johnson, African-American woman mathematician, short curled black hair, glasses, smart 1960s dress",
    "babbage": "Charles Babbage, bold flat vector cartoon portrait, Victorian inventor, side-parted dark hair, wide mutton-chop sideburns, tall stiff white cravat collar pressed against chin, black frock coat, warm skin tones, vivid saturated colors",
    "dijkstra": "Edsger Dijkstra, lean older European man, longish swept-back greying hair, no glasses, casual shirt",
    "hamilton": "Margaret Hamilton, young brunette woman in her twenties, long straight dark brown hair no grey, dark rectangular glasses, bright red blouse, warm olive skin",
    "knuth": "Donald Knuth, older man, bald on top with grey hair at the sides, round glasses, white beard, sweater",
    "lovelace": "Ada Lovelace, woman with dark center-parted upswept hair with ringlets, wearing a dark Victorian high-neck dress, banded collar rises straight up to touch the chin, small lace ruffle at collar edge, very close-up portrait, plain soft blue background",
    "ritchie": "Dennis Ritchie, 1970s man, medium brown hair, full brown beard and moustache, casual shirt",
    "cerf": "Vint Cerf, distinguished older man, grey hair, full neat grey beard, three-piece suit and tie",
    "torvalds": "Linus Torvalds, middle-aged man, short brown hair, oval wire glasses, casual collared shirt",
    "perlman": "Radia Perlman, woman engineer, shoulder-length brown wavy hair, large round glasses, black turtleneck collar pulled completely up to chin with no neck visible, jacket",
    "codd": "Edgar Codd, older British man, greying side-parted hair, rectangular glasses, shirt and tie",
    "hopper": "Grace Hopper, woman United States naval officer, navy dress uniform with peaked officer cap and gold insignia, high collar buttoned to the chin",
    "boole": "George Boole, bold flat vector cartoon portrait, Victorian mathematician, dark swept hair, short side whiskers, tall stiff white cravat collar pressed against chin, dark frock coat, warm golden skin tones, vivid saturated colors",
    "hoare": "Tony Hoare, distinguished older man, silver grey hair, rectangular glasses, jacket and shirt",
    "turing": "Alan Turing, young man, short side-parted brown hair, tweed jacket, open-collar shirt",
    "liskov": "Barbara Liskov, older woman computer scientist, short neat greying hair, rectangular dark-framed glasses, black turtleneck sweater pulled up to chin completely covering neck, navy blazer",
}
STYLE = ("flat vector illustration, tight head and shoulders close-up, front-facing, looking straight at the viewer, "
         "face large and filling most of the frame, chin close to a high collar, very short neck barely visible, "
         "anatomically correct proportions, symmetrical clean well-defined facial features, "
         "plain pastel background, bold clean outlines, flat cel shading, limited color palette, "
         "corporate memphis editorial style, warm friendly approachable expression, gentle pleasant smile, kind eyes, dignified")
NEG = ("photograph, photo, realistic, 3d render, cgi, text, watermark, signature, blurry, deformed, extra faces, nsfw, "
       "stern, frowning, scowling, grim, angry, furrowed brow, severe, unhappy, mugshot, "
       "decorative border, ornate frame, picture frame, vignette, cropped head, head touching top edge, "
       "asymmetric face, lopsided eyes, uneven eyes, distorted features, three-quarter view, profile, "
       "long neck, elongated neck, swan neck, thick neck, no neck, distorted neck, deformed neck, twisted neck, "
       "anatomical errors, malformed anatomy, disproportionate, extra head, two heads, sagging jowls")


def workflow(prompt, seed):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 640, "height": 768, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
              "latent_image": ["4", 0], "seed": seed, "steps": 8, "cfg": 2.0,
              "sampler_name": "euler_ancestral", "scheduler": "normal", "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "pio"}},
    }


def _sys():
    return json.load(urllib.request.urlopen(COMFY + "/system_stats", timeout=10))["system"]


def generate(name):
    if _sys()["ram_free"] / 1e9 < 2.2:
        print("ABORT: ram_free too low"); return False
    p = f"{DESC[name]}. {STYLE}"
    body = json.dumps({"prompt": workflow(p, random.randint(1, 2 ** 31)), "client_id": "piogen"}).encode()
    req = urllib.request.Request(COMFY + "/prompt", data=body, headers={"Content-Type": "application/json"})
    try:
        pid = json.load(urllib.request.urlopen(req, timeout=60))["prompt_id"]
    except urllib.error.HTTPError as e:
        print(name, "WORKFLOW ERROR", e.code, e.read().decode()[:300]); return False
    img = None
    for _ in range(90):
        time.sleep(2)
        try:
            h = json.load(urllib.request.urlopen(COMFY + f"/history/{pid}", timeout=20))
        except Exception:
            continue
        if pid in h and h[pid].get("outputs"):
            for node in h[pid]["outputs"].values():
                for im in node.get("images", []):
                    img = im; break
                if img: break
            if img: break
    if not img:
        print(name, "TIMEOUT"); return False
    qs = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img.get("subfolder", ""), "type": img.get("type", "output")})
    data = urllib.request.urlopen(f"{COMFY}/view?{qs}", timeout=60).read()
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, f"{name}.png"), "wb") as f:
        f.write(data)
    print(name, "ok", len(data))
    return True


def _remove_bg(im):
    """Flat-illustration background removal: flood-fill the solid background from
    top/side seeds (the figure's bold outline stops the fill, so collars/hair are
    kept) and return a transparent RGBA. Portraits are used in the UI cards, so
    they must have no background."""
    from PIL import Image, ImageDraw
    import numpy as np
    W, H = im.size
    work = im.copy()
    S = (0, 255, 1)  # sentinel unlikely to occur in the art
    # Seed from the top corners/edge and upper sides only (never the bottom,
    # where the shoulders/clothing reach the frame edge).
    seeds = [(1, 1), (W - 2, 1), (W // 2, 1),
             (1, int(H * 0.15)), (W - 2, int(H * 0.15)),
             (1, int(H * 0.33)), (W - 2, int(H * 0.33))]
    for s in seeds:
        try:
            ImageDraw.floodfill(work, s, S, thresh=50)
        except Exception:
            pass
    arr = np.array(work)
    mask = (arr[:, :, 0] == 0) & (arr[:, :, 1] == 255) & (arr[:, :, 2] == 1)
    alpha = np.where(mask, 0, 255).astype("uint8")
    return Image.fromarray(np.dstack([np.array(im), alpha]), "RGBA")


def optimize():
    """Downscale to 384w, palette-quantize, and remove the background (transparent)."""
    from PIL import Image
    for f in sorted(glob.glob(os.path.join(OUT, "*.png"))):
        im = Image.open(f).convert("RGB")
        w, h = im.size
        im = im.resize((384, int(h * 384 / w)), Image.LANCZOS)
        im = im.quantize(colors=128, method=Image.FASTOCTREE, dither=Image.Dither.NONE).convert("RGB")
        im = _remove_bg(im)
        im.save(f, "PNG", optimize=True)
    print("optimized+transparent", len(glob.glob(os.path.join(OUT, "*.png"))), "files")


if __name__ == "__main__":
    which = sys.argv[1].split(",") if len(sys.argv) > 1 else list(DESC)
    for n in which:
        generate(n)
    optimize()
