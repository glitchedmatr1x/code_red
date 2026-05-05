from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
svg = ROOT / "docs" / "layout_wireframe.svg"
svg.write_text('''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="760" viewBox="0 0 1280 760">
  <rect width="1280" height="760" fill="#120707"/>
  <rect x="10" y="10" width="1260" height="58" rx="8" fill="#1b0b0b" stroke="#792020"/>
  <text x="28" y="46" fill="#d72b2b" font-family="Segoe UI, Arial" font-size="26" font-weight="700">CODE RED</text>
  <g fill="#792020" stroke="#d72b2b">
    <rect x="190" y="20" width="110" height="36" rx="6"/><rect x="308" y="20" width="120" height="36" rx="6"/>
    <rect x="436" y="20" width="122" height="36" rx="6"/><rect x="566" y="20" width="138" height="36" rx="6"/>
    <rect x="712" y="20" width="130" height="36" rx="6"/>
  </g>
  <text x="214" y="42" fill="#f3eeee" font-size="13">Open File</text>
  <text x="330" y="42" fill="#f3eeee" font-size="13">Open Folder</text>
  <text x="458" y="42" fill="#f3eeee" font-size="13">Scan Archive</text>
  <text x="585" y="42" fill="#f3eeee" font-size="13">Validate</text>
  <text x="736" y="42" fill="#f3eeee" font-size="13">Export Report</text>
  <rect x="10" y="78" width="210" height="640" rx="8" fill="#1b0b0b" stroke="#3b1717"/>
  <text x="24" y="108" fill="#f3eeee" font-size="18" font-weight="700">Resource Lanes</text>
  <g fill="#211010" stroke="#792020">
    <rect x="24" y="128" width="182" height="42" rx="6"/><rect x="24" y="178" width="182" height="42" rx="6"/>
    <rect x="24" y="228" width="182" height="42" rx="6"/><rect x="24" y="278" width="182" height="42" rx="6"/>
    <rect x="24" y="328" width="182" height="42" rx="6"/><rect x="24" y="378" width="182" height="42" rx="6"/>
    <rect x="24" y="428" width="182" height="42" rx="6"/><rect x="24" y="478" width="182" height="42" rx="6"/>
  </g>
  <text x="42" y="154" fill="#f3eeee" font-size="14">Archives</text><text x="42" y="204" fill="#f3eeee" font-size="14">Textures</text>
  <text x="42" y="254" fill="#f3eeee" font-size="14">Meshes</text><text x="42" y="304" fill="#f3eeee" font-size="14">Scripts</text>
  <text x="42" y="354" fill="#f3eeee" font-size="14">Strings</text><text x="42" y="404" fill="#f3eeee" font-size="14">Audio</text>
  <text x="42" y="454" fill="#f3eeee" font-size="14">World</text><text x="42" y="504" fill="#f3eeee" font-size="14">Other</text>
  <rect x="230" y="78" width="650" height="640" rx="8" fill="#1b0b0b" stroke="#3b1717"/>
  <text x="250" y="112" fill="#f3eeee" font-size="20" font-weight="700">Workspace table</text>
  <rect x="250" y="134" width="610" height="566" fill="#100808" stroke="#792020"/>
  <line x1="250" y1="172" x2="860" y2="172" stroke="#792020"/>
  <text x="265" y="158" fill="#b59a9a" font-size="13">Lane | Ext | Size | Source | Path</text>
  <rect x="890" y="78" width="360" height="640" rx="8" fill="#1b0b0b" stroke="#3b1717"/>
  <text x="910" y="112" fill="#f3eeee" font-size="20" font-weight="700">Inspector</text>
  <rect x="910" y="134" width="310" height="42" fill="#211010" stroke="#792020"/><text x="930" y="160" fill="#f3eeee" font-size="14">Details | Report | Log</text>
  <rect x="910" y="188" width="310" height="512" fill="#100808" stroke="#792020"/>
  <rect x="10" y="728" width="1260" height="24" rx="5" fill="#1b0b0b" stroke="#3b1717"/>
  <text x="24" y="745" fill="#b59a9a" font-size="12">Status bar</text>
</svg>
''', encoding="utf-8")
print(svg)
