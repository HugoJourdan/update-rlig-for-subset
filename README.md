# Update rlig For Subset

Update rlig For Subset PreFilter to remove conditions involving axes not present in a specified list.

Usage: Add “UpdatereligForSubset” as a PreFilter in Glyphs in a Variable Instance, with a list of axis tags you want to keep.

Example: `UpdatereligForSubset;wght,slnt` will remove all conditions where an axis different from wght or slnt is involved.