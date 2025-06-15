
# Digitation V3

> **PCB Digitization & Test‑Automation Toolkit**

*(Working title – change as you like)*

Digitation V3 is an internal tool that lets engineers analyse a board image, place and manage pads, cross‑check pads against BOM / ALF data, and export standardized **`.nod`** files for ATE systems.  
It also provides helpers for MDIO / SPI communication scripts, thermal‑simulation models for laser soldering, and a PyQt5 UI that integrates these features.

## Quick install (dev mode)

```bash
git clone https://github.com/your-user/digitation_v3.git
cd digitation_v3
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pip install -e .
python codes/main.py
```

## Features

* 📸 **Pad digitisation GUI** – place pads, anchors, component footprints on high‑res board images  
* 📊 **BOM / ALF verifier** – highlight mismatches between schematic and physical layout  
* 🛠 **Quick placer & ghost overlay** – rapid placement with row/column logic and visual feedback  
* 🔥 **Laser‑solder thermal simulator** – predict optimal power/time for through‑hole pads  
* 🔌 **Protocol helpers** – SPI / MDIO scripting utilities and packet logger  
* 🧰 **Extensible plugin architecture** – add new component libraries or exporters easily

## Roadmap

See `CHANGELOG.md` for release history and upcoming milestones.

## License

Released under the MIT License – see `LICENSE` for details.
