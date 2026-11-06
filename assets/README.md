# Repository artwork

| Asset | Purpose |
| --- | --- |
| [banner.jpg](banner.jpg) | 1200 × 600 GitHub README banner. Also suitable for a future catalog image or GitHub social preview. |
| [banner-art.png](banner-art.png) | Original 1672 × 941 image-generation output, before cropping and typesetting. |
| [how-it-works.svg](how-it-works.svg) | Editable diagram of the snapshot and review workflow. |
| [activation-modes.svg](activation-modes.svg) | Editable comparison of manual, suggest and auto activation. |

The dark editorial composition, yellow headings and cobalt accents take inspiration
from the presentation of [NousResearch's official plugins](https://github.com/NousResearch/hermes-official-plugins).
The elephant, document and goldfish artwork is original. No Nous or Google logos or
reference images were used. This remains an independent plugin, not an official product.
The assets are distributed under this repository's [Apache-2.0 license](../LICENSE).

## Image generation

The illustration was generated using Hermes's bundled **OpenAI (Codex auth)**
image-generation provider, not drawn as SVG. The requested tier was
`gpt-image-2-medium`; the service reported medium quality and returned 1672 × 941
pixels. Codex uses a server-managed image engine, so the requested tier is not a
verified identity of the underlying model. No reference images or upscaling were used.
The title and subtitle were typeset afterward for reliable spelling and legibility.

Prompt:

> Create an original, beautifully art-directed editorial illustration for the GitHub banner of HERMES EGM, an independent software-design review plugin. Wide landscape, near-black charcoal background, tactile antique scientific-engraving and photographic cut-paper collage, warm ivory engraved elephant on the LEFT, a richly detailed flowing-finned GOLDEN GOLDFISH on the RIGHT, a single cream engineering-specification sheet floating between them. The elephant has an elegant realistic head and trunk, expressive but serious, natural anatomy and intricate engraved hatching; layered cobalt-blue blueprint sheets stay behind the elephant to symbolize retained project context. The fish is large, luminous gold and orange with detailed scales and flowing red-orange tail; a delicate cobalt circular orbit around it suggests an isolated fresh perspective. The single central paper travels from elephant toward fish along a fine yellow directional trace. Both animals must be instantly identifiable. Heroic museum-book engraving meets experimental retro scientific publishing, with visible paper grain and imperfect halftone print texture, deep ink blacks, ivory, electric yellow, cobalt blue, one restrained vermilion accent. Sophisticated, warm, memorable and slightly surreal; not cute vector clipart, not a flat SVG icon, not a glossy 3D render, not a SaaS dashboard. Strong silhouette and generous negative space. Keep the complete elephant head/body, document and fish inside the central 85 percent of image width. Place the illustration in the TOP 60 percent; leave the BOTTOM 35 percent essentially empty near-black for later professional title typesetting. No words, no letters, no typography, no brand names, no logos, no watermarks, no frames. Do not reproduce an existing company artwork; make an original image expressing deep context versus fresh review.

## Rebuild the banner

Requires ImageMagick and the DejaVu fonts. These are artwork tools, not plugin
runtime dependencies. From the repository root:

```sh
work="$(mktemp -d)"
magick assets/banner-art.png -crop 1672x836+0+0 +repage -resize 1200x600 \
  -font DejaVu-Sans-Bold -pointsize 91 -fill '#FFDE1A' \
  -annotate +45+504 'HERMES EGM' \
  -font DejaVu-Sans -pointsize 27 -fill '#E5DEC9' \
  -annotate +49+546 'Design with context. Review with fresh eyes.' \
  -font DejaVu-Sans-Mono -pointsize 13 -fill '#A9ADA5' \
  -annotate +50+577 'ELEPHANT / GOLDFISH MODEL  ·  FRESH-CONTEXT DESIGN REVIEW' \
  -fill '#E5DEC9' -annotate +954+577 'INDEPENDENT HERMES PLUGIN' \
  "$work/banner.png"
magick "$work/banner.png" -sampling-factor 4:4:4 -quality 92 assets/banner.jpg
```

The crop removes empty lower background, not the animals or document. JPEG keeps
the README image small; the unmodified generated PNG remains available above.
To use the banner as the GitHub social preview, select it in the repository settings.

## Edit the diagrams

The README embeds the SVGs directly with Markdown image syntax. They contain no
scripts, external images or font downloads. Each includes a title and description;
the README also explains the diagrams in ordinary text for narrow screens and
readers who cannot view images. No Mermaid renderer is needed.

Edit the SVG text and geometry together. Keep at least 12 SVG pixels of internal
padding around text, and measure actual rendered text bounds before committing.
Use DejaVu Sans / DejaVu Sans Mono, then check a sans-serif / monospace fallback.
Do not rely on visual inspection alone: a heading can look acceptable while
extending a few pixels beyond its box.

For a raster proof with librsvg:

```sh
work="$(mktemp -d)"
rsvg-convert assets/how-it-works.svg -o "$work/how-it-works.png"
rsvg-convert assets/activation-modes.svg -o "$work/activation-modes.png"
```

Check the proofs and the rendered README at normal reading width, including both
light and dark page backgrounds. The diagrams have their own opaque backgrounds.
