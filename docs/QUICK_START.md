# Quick Start

Code RED is a public-safe research and tooling repo. Keep game files and generated patch experiments outside the repository.

## 1. Clone

```bat
git clone https://github.com/GLITCHEDMATR1X/Code_RED.git
cd Code_RED
```

## 2. Create a Private Dev Kit Folder

```text
Code_RED_DevKit/
├─ private_input/
├─ extracted/
├─ working/
├─ output/
├─ logs/
└─ backups/
```

Do not commit this folder.

## 3. Install Python Requirements

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 4. Run Tools Against Your Own Files

Use your legally owned local game files as inputs. Tools should produce reports, manifests, and patch-style outputs instead of redistributing full archives.

## 5. Validate Before Sharing

Before publishing output, confirm it contains no raw game archives, extracted retail scripts, compiled binaries, logs, or local paths.
