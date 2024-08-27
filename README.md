# Update rlig For Subset

Update rlig For Subset PreFilter to remove conditions involving axes not present in a specified list.

Usage: Add `UpdaterligForSubset” as a PreFilter in Glyphs in a Variable Instance, with a list of axis tags you want to keep.

Example: `UpdaterligForSubset;wght,slnt` will remove all conditions where an axis different from wght or slnt is involved.

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

You can also type `UpdatreligForSubset;` without an argument or `UpdaterligForSubset;auto`.

If a custom parameter `Disable Masters` is set, it will analyze the remaining masters and retain only the axes kept at export.

For example, in a setup with Condensed + Normal width, if `Disable Masters` CP removes all your "Condensed" masters, the width axis will be removed at export, and the auto mode will set it as an argument in the filter.
