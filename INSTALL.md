# Kurulum / Install (for people and their AI agents)

Goal: get the ready-made Obsidian vault (Dersler → dönem → ders → Çıkmış Sorular / Ders Notları / Slaytlar) on this computer.

## Steps (an agent can run these as-is)
1. Download the latest vault zip from the Releases page:
   ```bash
   gh release download --repo isobed18/gazi-bm-mf-notlar --pattern "Gazi-BM-Vault.zip" --dir .
   ```
   (or open https://github.com/isobed18/gazi-bm-mf-notlar/releases/latest and download `Gazi-BM-Vault.zip`;
   the repository is private for now, so you need access to it.)
2. Unzip it to a folder of your choice, e.g. `~/Documents/Gazi-BM-Vault`:
   ```bash
   unzip Gazi-BM-Vault.zip -d ~/Documents/Gazi-BM-Vault          # Windows PowerShell: Expand-Archive Gazi-BM-Vault.zip $HOME\Documents\Gazi-BM-Vault
   ```
3. Open Obsidian → *Open folder as vault* → select that folder. Start at `Başlangıç.md`.

## Updating
Download the newest release again and replace the folder (the vault is generated; do not keep your own notes inside it —
use a separate vault for personal notes).

## Without student notes
Student notes are an optional layer: delete the `Arsiv/student-notes` folders, or skip them when browsing.
