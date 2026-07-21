# Workspace button source assets

These assets are shared by the live DIY workspace controls and the workspace guide.
They are upload sources only: `project.config.json` excludes this folder from the
Mini Program package, while runtime URLs are resolved through `utils/assets.js`
and `config/asset-manifest.*`.

Publish these files to both test and production COS before building the matching
environment package. Keep both UI surfaces on the same CDN object instead of
recreating an icon in WXSS.

| Asset | Control |
| --- | --- |
| `workspace-undo.png` | Undo |
| `workspace-wrist.png` | Wrist size |
| `share-button-gold.png` | Share |
| `workspace-save-download.png` | Save draft |
| `workspace-energy-five-elements.png` | Five-element chart |
| `workspace-clear-pastel.png` | Clear tray |
| `workspace-string-dice.png` | String / scatter |

The tray theme and cart controls contain dynamic text or state. Their guide previews
reuse the live control dimensions, colors, and spacing instead of a baked image.
