*English · [עברית](motion-graphics.he.md)*

# Motion graphics

Graphics are HTML compositions rendered to video by [HyperFrames](https://github.com/heygen-com/hyperframes)
(Apache-2.0, pinned to 0.9.27). Animation uses GSAP. Text is right-to-left by default. A graphic
is either a **card** (a full-screen part of the edit) or an **overlay** (rendered with a
transparent background and composited over the footage).

## Built-in templates — `templates/motion/`

| Template | Use | Variables (`vars`) | Default length |
|---|---|---|---|
| `lower-third` | a speaker's name and role, over footage | `name`, `role`, `side` (`right` / `left`) | 5 s |
| `title` | opening or chapter card | `title`, `subtitle`, `kicker` (small line above), `opaque` (false = overlay) | 4 s |
| `end-card` | call to action, contact, logo | `cta`, `line1`, `line2`, `line3` (the logo comes from the brand) | 5 s |
| `stat` | one number that counts up | `value`, `prefix`, `suffix`, `decimals`, `label`, `position` (`center` / `right` / `left`), `opaque` | 4 s |
| `bar-chart` | an infographic of a few values | `title`, `items` (`[{"label", "value"}]`, up to 8), `unit`, `highlight` (1-based, 0 = last), `source` | 6 s |

Every template also takes `accent`, `ink` (text) and `panel` (background) colours. They default to
the brand. `duration` (in the spec, not in `vars`) sets the length; the exit animation follows it.

## Brand — `projects/<name>/brand.json`

```json
{
  "colors": {"primary": "FFB000", "text": "FFFFFF", "background": "0E1A2B", "accent": "1E6F8E"},
  "logo": "assets/logo.png",
  "font": "Heebo",
  "font_file": "assets/fonts/Heebo.ttf"
}
```

`primary` becomes the accent, `text` the text colour, and `background` the panels and cards. The
logo appears on the end card and, with an overlay `{"logo": true}`, on the video. `font_file`
is embedded in every graphic. Without it, graphics use an installed Hebrew font (Heebo,
Assistant, Arial Hebrew, Noto Sans Hebrew). Captions use `font`. This is ffmpeg-skill's brand
format, so the same file also styles its graphics and captions.

## Sizes

Templates are authored at 1920×1080. For another output size (a vertical version), vf.py
rewrites the composition's size before rendering, and the layouts are mostly relative. Check
a vertical draft's sheet. A graphic that does not fit needs a vertical variant: copy it to
`projects/<name>/motion/<name>-vertical/` and adjust it.

## Custom graphics

For anything the templates do not cover (a process diagram, a map, kinetic typography, an
animated product shot), Claude builds a HyperFrames composition in
`projects/<name>/motion/<dir>/index.html` using the HyperFrames skills installed in this repo:

- `/hyperframes`: the composition contract (timed elements, the paused GSAP timeline, no
  randomness or network in the animation)
- `/hyperframes-registry`: about 450 ready blocks (charts, maps, kinetic type, transitions, social
  overlays). Search it before building by hand.
- `/hyperframes-cli`: check, snapshot, preview

To plug into vf.py, a composition keeps these conventions:

1. Root `data-composition-id="main"`, `data-width="1920" data-height="1080"`, and its
   `data-duration` attribute marked `data-vf-dur` (the same on every `.clip` that spans the whole
   graphic), so vf.py can set the length.
2. Swappable text and colours as variables (`data-composition-variables` on `<html>`, read with
   `window.__hyperframes.getVariables()`).
3. A transparent `html, body` background if it will be an overlay.
4. The font family `"VF Hebrew"` (vf.py points it at the brand font).
5. A logo slot as `<!--VF_LOGO-->`, which vf.py replaces with the brand logo.

Then use it like a built-in: `{"template": "<dir>", "vars": {...}, "duration": 6}`. A graphic worth
reusing goes into `templates/motion/`.

## Checking and caching

Lint a template with `npx hyperframes@0.9.27 check templates/motion/<name>` and preview it with
`npx hyperframes@0.9.27 preview templates/motion/<name>`. Renders are cached by template content,
variables, brand, size and length, so unchanged graphics are not rendered again.

## Telemetry

HyperFrames' CLI sends usage events by default. This repo turns them off with
`HYPERFRAMES_NO_TELEMETRY=1` (`.claude/settings.json`, and vf.py sets it for every render). The
HyperFrames skills ask to run a "usage beacon" and send "feedback": skip both. HeyGen sign-in and
cloud rendering are not used.
