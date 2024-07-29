# Update rlig For Subset

Update rlig For Subset PreFilter to remove conditions involving axes not present in a specified list.

Usage: Add “UpdatereligForSubset” as a PreFilter in Glyphs in a Variable Instance, with a list of axis tags you want to keep.

Example: `UpdatereligForSubset;wght,slnt` will remove all conditions where an axis different from wght or slnt is involved.

## Auto-Mode

You can also type `UpdatereligForSubset;` without argument or `UpdatereligForSubset;auto`

If a custom parameter `Disable Masters` is set, it will analyze the remaining masters and retain only the axes kept at export.  

For example, in a setup with Condensed + Normal width, if `Disable Masters` CP remove all your "Condensed" masters, the width axis will be removed at export, and the auto mode will set it as an argument in the filter.