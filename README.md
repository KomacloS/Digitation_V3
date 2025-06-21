
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
python main.py
```

## Features

* 📸 **Pad digitisation GUI** – place pads, anchors, component footprints on high‑res board images  
* 📊 **BOM / ALF verifier** – highlight mismatches between schematic and physical layout  
* 🛠 **Quick placer & ghost overlay** – rapid placement with row/column logic and visual feedback  
* 🔌 **Protocol helpers** – SPI / MDIO scripting utilities and packet logger
* 🧰 **Extensible plugin architecture** – add new component libraries or exporters easily

## Creating Projects

Choose **Create Project** from the menu and select either:

* **Manual** – pick images and fill in settings yourself.
* **Automatic** – select a VIVA `.mdb` file and the tool loads images and coordinates for you (an "Uploading data" dialog will appear).

## Roadmap

See `CHANGELOG.md` for release history and upcoming milestones.

## License

Released under the MIT License – see `LICENSE` for details.

## Stand-alone Build

To create a frozen copy that can run without a Python installation:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller

pyinstaller --noconfirm --onedir \
    --add-data "constants:constants" \
    --add-data "component_libraries:component_libraries" \
    --icon=icon.ico \
    --windowed \
    --name Digitation main.py
```

Including the `--windowed` option ensures no console window appears when
running the resulting executable under Windows.

The resulting `dist/Digitation` directory contains the application along with
`constants/constants.txt`, `constants/functions_ref.txt` and the
`component_libraries` folder, all of which remain editable after installation.
