# Sky Leviathan — coolest-art-01

A colossal bioluminescent jellyfish drifts above a dark sea at night, lit from
within, its tentacles trailing toward a tiny boat with one warm lantern far
below. The sky is also an ocean.

`main.py` (Python 3.13, standard library only) draws the art pixel by pixel —
a small software rasteriser plus a hand-rolled PNG encoder — and writes a
1024x1024 PNG to `$MAKEFUN_OUTPUT_DIR/entry.png` (default `/output`).

Run it:

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Deterministic: a fixed seed and no clock or network, so two runs write
identical bytes.
