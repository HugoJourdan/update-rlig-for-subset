# Update rlig For Subset

Update rlig For Subset PreFilter to remove conditions involving axes not present in a specified list.

Usage: Add `UpdaterligForSubset` as a PreFilter in Glyphs in a Variable Instance, with a list of axis tags you want to keep.

Example: `UpdaterligForSubset;wght,slnt` will remove all conditions where an axis different from wght or slnt is involved. Semicolons work too — `UpdaterligForSubset;wght;slnt` is the same thing.

So if you use `UpdaterligForSubset;wght` and your rlig code looks like:

````markdown
#ifdef VARIABLE
condition 120 < wght;
sub dollar by dollar.rlig;

condition 50 < wdth;
sub cent by cent.rlig;
#endif
````

You will get:

````markdown
#ifdef VARIABLE
condition 120 < wght;
sub dollar by dollar.rlig;
#endif
````

## Auto-Mode

You can also type `UpdaterligForSubset;` without an argument or `UpdaterligForSubset;auto`.

The axes that survive an export are read off the masters of the font Glyphs is exporting, which already
reflect that instance's `Disable Masters`. So in a setup with Condensed + Normal width, if `Disable
Masters` removes all your "Condensed" masters, the width axis is gone at export and its conditions are
removed. Passing an explicit tag list narrows that further; it can never widen it.

## What happens to a condition on an axis that is gone

A dropped axis is not simply gone — it is pinned to whatever single value its remaining masters share,
and the condition is judged against that value:

- `condition 160 < wght, INKT < 0.5;` in a VF pinned to `INKT=0` becomes `condition 160 < wght;`. The
  clause was true everywhere in that font, so it carries no information and the rules stay.
- The same condition in a VF pinned to `INKT=1` is false everywhere, so the whole block is removed.

Earlier versions dropped the block in both cases, which silently cost the INKT=0 subset its
`dollar.rlig` / `cent.rlig` substitutions.

## Why a block is sometimes removed entirely

Two shapes of output make GlyphsApp emit a broken `GSUB`, so the filter never produces them:

1. An `#ifdef VARIABLE` / `#endif` pair left with nothing inside it.
2. A set of conditions that only repeats what the feature already applies unconditionally.

In both cases GlyphsApp skips writing the alternate feature table but still writes the
`FeatureVariations` record, leaving its `alternateFeatureOffset` pointing past the end of `GSUB`.
HarfBuzz's sanitiser then rejects the whole `GSUB` table, and the font loses every feature it has —
Arabic joining included, which is how this shows up first.

When every surviving condition merely repeats the feature's unconditional rules, all the
`#ifdef VARIABLE` blocks are dropped instead; the feature then compiles into its plain form and behaves
the same. Conditions are otherwise kept together, because once a feature carries any condition GlyphsApp
empties its plain form and relies on the conditions to cover every location.

## Tests

The rewriting is pure text work and runs without GlyphsApp:

```sh
python3 tests/test_plugin.py
```
