from huggingface_hub import hf_hub_download
import shutil
from pathlib import Path

dest = Path.home() / ".tars" / "needle.pkl"
dest.parent.mkdir(parents=True, exist_ok=True)

print("Downloading Needle weights...")
cached = hf_hub_download(
    repo_id="Cactus-Compute/Needle",
    filename="needle.pkl"
)
shutil.copy2(cached, dest)
print(f"Saved to {dest}")
