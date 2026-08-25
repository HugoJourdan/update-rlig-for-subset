# encoding: utf-8

###########################################################################################################
#
#
# Filter without dialog plug-in
#
# Read the docs:
# https://github.com/schriftgestalt/GlyphsSDK/tree/master/Python%20Templates/Filter%20without%20Dialog
#
#
###########################################################################################################

from __future__ import division, print_function, unicode_literals
import objc
import re
from GlyphsApp import *
from GlyphsApp.plugins import *


# One clause of a `condition` line: `160 < wght`, `INKT < 0.5`, `100 < wght < 200`. The numbers are in
# design coordinates, the same space as GSFontMaster.internalAxesValues.
CLAUSE = re.compile(
    r"""^\s*
    (?:(?P<min>[-+]?\d+(?:\.\d+)?)\s*<\s*)?
    (?P<tag>[A-Za-z][A-Za-z0-9]{0,3})
    (?:\s*<\s*(?P<max>[-+]?\d+(?:\.\d+)?))?
    \s*$""",
    re.VERBOSE,
)

LOOKUP_OPEN = re.compile(r"^lookup\s+\S+\s*\{")
LOOKUP_CLOSE = re.compile(r"^\}\s*\S*\s*;")


def axis_summary(font):
    """Split the font's axes into the ones that still vary and the ones pinned to a single value.

    `font` is the copy GlyphsApp built for the instance currently exporting, so its masters already
    reflect that instance's `Disable Masters`. Reading the axes off those masters is what keeps one
    variable instance from being subsetted with another instance's axis list.
    """
    tags = [axis.axisTag for axis in font.axes]
    values = [set() for _ in tags]
    for master in font.masters:
        master_values = list(master.internalAxesValues)
        for index in range(min(len(tags), len(master_values))):
            values[index].add(round(float(master_values[index]), 6))

    kept, pinned = [], {}
    for index, tag in enumerate(tags):
        if len(values[index]) == 1:
            pinned[tag] = next(iter(values[index]))
        else:
            # No masters at all also lands here; keeping the axis is the safe reading.
            kept.append(tag)
    return kept, pinned


def parse_axis_argument(customParameters):
    """Read the filter's arguments as a list of axis tags, or None for auto.

    GlyphsApp hands the arguments over as `{0: "wght", 1: "slnt"}` for `UpdaterligForSubset;wght;slnt`
    and as `{0: "wght,slnt"}` for the comma form the README documents, so accept both separators.
    """
    if not customParameters:
        return None
    if hasattr(customParameters, "keys"):
        values = [customParameters[key] for key in sorted(customParameters.keys())]
    else:
        values = list(customParameters)

    tags = []
    for value in values:
        tags.extend(tag for tag in re.split(r"[,\s]+", str(value).strip()) if tag)
    if not tags or tags == ["auto"]:
        return None
    return tags


def unconditional_rules(lines):
    """The rules the feature applies outside any `#ifdef` block, ignoring lookup definitions.

    A definition's body is skipped: `sub x by y;` inside `lookup foo { … } foo;` only runs where `foo`
    itself is invoked, so it is not something the feature applies on its own.
    """
    rules = set()
    inside_lookup = False
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if line.startswith("#if"):
            while index < len(lines) and not lines[index].strip().startswith("#endif"):
                index += 1
            index += 1
            continue
        if LOOKUP_OPEN.match(line):
            inside_lookup = True
        elif inside_lookup and LOOKUP_CLOSE.match(line):
            inside_lookup = False
        elif not inside_lookup and line and not line.startswith("#"):
            rules.add(line)
        index += 1
    return rules


def rewrite_condition(line, kept_tags, pinned):
    """Rewrite one `condition` line for the axes this export keeps, or None to drop its block.

    A clause on a pinned axis is decided here rather than thrown away: `INKT < 0.5` is simply true in a
    VF pinned to INKT=0, so the clause goes and the rules stay; it is false in one pinned to INKT=1, so
    the whole block goes.
    """
    body = line.strip()[len("condition"):].strip().rstrip(";").strip()

    clauses = []
    for clause in body.split(","):
        clause = clause.strip()
        match = CLAUSE.match(clause)
        if match is None:
            clauses.append(clause)  # Unrecognised syntax: leave it exactly as it was.
            continue

        tag = match.group("tag")
        if tag in kept_tags:
            clauses.append(clause)
            continue
        if tag not in pinned:
            return None  # Axis is gone and we have no value to test it against.

        value = pinned[tag]
        minimum, maximum = match.group("min"), match.group("max")
        if minimum is not None and not float(minimum) < value:
            return None
        if maximum is not None and not value < float(maximum):
            return None
        # True everywhere in this export, so the clause carries no information any more.

    if not clauses:
        # Every axis was pinned and satisfied, so the rules below are unconditional. They still run via
        # the feature's own unconditional copy; a condition-less block is not expressible here.
        return None

    indent = line[: len(line) - len(line.lstrip())]
    return "%scondition %s;" % (indent, ", ".join(clauses))


def split_blocks(body):
    """Split the inside of an `#ifdef VARIABLE` block into its leading lines and its condition blocks."""
    preamble, blocks, current = [], [], None
    for line in body:
        if line.lstrip().startswith("condition"):
            if current is not None:
                blocks.append(current)
            current = [line]
        elif current is None:
            preamble.append(line)
        else:
            current.append(line)
    if current is not None:
        blocks.append(current)
    return preamble, blocks


def block_rules(block):
    """The substitution lines a condition block contributes, without its `condition` line."""
    return [line.strip() for line in block[1:] if line.strip() and not line.strip().startswith("#")]


def update_feature_code(code, kept_tags, pinned):
    """Drop the conditions this export cannot satisfy, and the `#ifdef VARIABLE` blocks left hollow."""
    lines = code.split("\n")
    unconditional = unconditional_rules(lines)

    # Split the code into plain runs and `#ifdef VARIABLE` regions, filtering each region as we go.
    segments = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip() != "#ifdef VARIABLE":
            segments.append(("plain", [line]))
            index += 1
            continue

        end = index + 1
        while end < len(lines) and lines[end].strip() != "#endif":
            end += 1
        closing = lines[end] if end < len(lines) else "#endif"

        preamble, blocks = split_blocks(lines[index + 1:end])
        kept = []
        for block in blocks:
            condition = rewrite_condition(block[0], kept_tags, pinned)
            if condition is not None:
                kept.append([condition] + block[1:])
        segments.append(("variable", line, preamble, kept, closing))
        index = end + 1 if end < len(lines) else len(lines)

    # Once a feature carries any condition, GlyphsApp empties its plain form and expects the conditions
    # to cover every location, so the blocks have to be kept together or dropped together. Dropping them
    # is only safe when every one that survived merely repeats what the feature already does
    # unconditionally — and it is also necessary: GlyphsApp skips writing an alternate feature table that
    # matches the default one, yet still writes the FeatureVariations record, leaving its
    # alternateFeatureOffset pointing past the end of GSUB. HarfBuzz's sanitiser then rejects the whole
    # GSUB table and the font loses every feature it has, Arabic joining included.
    surviving = [block for segment in segments if segment[0] == "variable" for block in segment[3]]
    variations_add_nothing = all(
        all(rule in unconditional for rule in block_rules(block)) for block in surviving
    )

    output = []
    for segment in segments:
        if segment[0] == "plain":
            output.extend(segment[1])
            continue
        _, header, preamble, kept, closing = segment
        if not kept or variations_add_nothing:
            continue
        output.append(header)
        output.extend(preamble)
        for block in kept:
            output.extend(block)
        output.append(closing)

    return "\n".join(output)


class UpdaterligForSubset(FilterWithoutDialog):
    @objc.python_method
    def settings(self):
        self.menuName = Glyphs.localize(
            {
                "en": "Update rlig for subset",
            }
        )

    @objc.python_method
    def filter(self, layer, inEditView, customParameters):
        font = layer.font()
        # The rewrite is per font, not per glyph; one layer is enough to trigger it.
        if not font.glyphs or layer.parent != font.glyphs[0]:
            return

        feature = font.features["rlig"]
        if feature is None:
            return

        kept_tags, pinned = axis_summary(font)
        requested = parse_axis_argument(customParameters)
        if requested is not None:
            kept_tags = [tag for tag in kept_tags if tag in requested]

        updated = update_feature_code(feature.code, kept_tags, pinned)
        if feature.code != updated:
            feature.code = updated
            print(
                "UpdaterligForSubset: rewrote rlig for axes [%s], pinned [%s]"
                % (", ".join(kept_tags) or "-", ", ".join("%s=%g" % (t, v) for t, v in sorted(pinned.items())) or "-")
            )

    @objc.python_method
    def __file__(self):
        """Please leave this method unchanged"""
        return __file__
