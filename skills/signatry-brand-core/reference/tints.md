# Tint Reference Table

Full precomputed tints for every color in `signatry-brand-core`. Loaded on demand — only needed when a deliverable requires a specific lighter shade (backgrounds, subtle fills, chart secondary series, etc.), not for a basic hex/font/logo lookup.

See `SKILL.md`'s **Tints** section for the definition, formula, and application rules (opaque computed color, not alpha transparency). This file is the reference table only.

**Reference table** (all values lowercase hex, no `#`, generated with the formula in `SKILL.md` and spot-checked against `pypdf`/reportlab rendering):

| Color | 100% (base) | 80% | 60% | 40% | 20% | 5% |
|---|---|---|---|---|---|---|
| Legacy | `2b7a78` | `559593` | `80afae` | `aacac9` | `d5e4e4` | `f4f8f8` |
| Glacier | `37a49f` | `5fb6b2` | `87c8c5` | `afdbd9` | `d7edec` | `f5fafa` |
| Ice | `def2f1` | `e5f5f4` | `ebf7f7` | `f2faf9` | `f8fcfc` | `fdfefe` |
| Midnight | `17242a` | `455055` | `747c7f` | `a2a7aa` | `d1d3d4` | `f3f4f4` |
| Dusk | `d77900` | `df9433` | `e7af66` | `efc999` | `f7e4cc` | `fdf8f2` |
| Dawn | `f2a65a` | `f5b87b` | `f7ca9c` | `fadbbd` | `fcedde` | `fefbf7` |
| Jubilee | `8a1e41` | `a14b67` | `b9788d` | `d0a5b3` | `e8d2d9` | `f9f4f6` |
| Heartfelt | `fd4a5c` | `fd6e7d` | `fe929d` | `feb7be` | `ffdbde` | `fff6f7` |
| Passage | `595378` | `7a7593` | `9b98ae` | `bdbac9` | `dedde4` | `f7f6f8` |
| Mist | `8c88a3` | `a3a0b5` | `bab8c8` | `d1cfda` | `e8e7ed` | `f9f9fa` |
| Soar | `68a269` | `86b587` | `a4c7a5` | `c3dac3` | `e1ece1` | `f7faf8` |
| Arctic | `8cb7c9` | `a3c5d4` | `bad4df` | `d1e2e9` | `e8f1f4` | `f9fbfc` |

Notes:
- Ice is already very light, so its tints converge on near-white quickly — expected, not an error.
- Recompute rather than eyeball if a color or its base hex ever changes in `SKILL.md`; this table is a snapshot, not itself the source of truth (the formula + base hex table in `SKILL.md` are).
