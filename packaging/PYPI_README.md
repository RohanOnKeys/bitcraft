# BitCraft

Bitcoin transaction intelligence in your terminal: ranked alerts,
provenance-tagged evidence, SHAP reasons and an animated link-analysis view.

## Install

```text
pip install bitcraft          # any OS, Python 3.10+
choco install bitcraft        # Windows, via Chocolatey
```

## Use

```text
bitcraft                 open BitCraft in a new, large terminal window
bitcraft demo            same, with built-in demo data
bitcraft here            run inside the current terminal
bitcraft status          check the API and the last pipeline run
bitcraft --help          everything else
```

BitCraft connects to a BitCraft API at `http://localhost:8000` (change it
with `--api-url` or `BITCRAFT_API_URL`) and falls back to demo data when
none is running. The API and ML pipeline live in the
[source repository](https://github.com/RohanOnKeys/bitcraft).

Best in Windows Terminal, a modern Linux terminal or iTerm2, at 160x46 or
larger.

## License

Apache License 2.0. Copyright 2026 The BitCraft Authors: Rohan Pattanayak,
Jagadish Pattnaik, Shreya Mishra, Shreya Mohanty, Ashutosh Badapada and
Rosalin Nayak.
