"""Tests for the rlig rewriting, run without GlyphsApp.

    python3 tests/test_plugin.py
"""

import importlib.util
import os
import sys
import types

# The plugin imports objc and GlyphsApp at module level; stub them so the pure functions can be read.
for _name in ("objc", "GlyphsApp", "GlyphsApp.plugins"):
    sys.modules[_name] = types.ModuleType(_name)
sys.modules["objc"].python_method = lambda function: function
sys.modules["GlyphsApp"].Glyphs = types.SimpleNamespace(localize=lambda strings: strings)
sys.modules["GlyphsApp.plugins"].FilterWithoutDialog = type("FilterWithoutDialog", (), {})

_PLUGIN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "UpdaterligForSubset.glyphsFilter", "Contents", "Resources", "plugin.py",
)
_spec = importlib.util.spec_from_file_location("updaterligforsubset", _PLUGIN)
plugin = importlib.util.module_from_spec(_spec)
sys.modules["updaterligforsubset"] = plugin
_spec.loader.exec_module(plugin)

update = plugin.update_feature_code
failures = []


def check(name, got, want):
    if got == want:
        print("  ok   " + name)
        return
    failures.append(name)
    print("  FAIL " + name)
    print("     got : " + repr(got))
    print("     want: " + repr(want))


# An rlig shaped like the ones this filter runs on: a variable block gated on two axes, the lookup the
# Arabic ligatures live in, the variable block that turns that lookup on, and the plain call for statics.
RLIG = "\n".join([
    "#ifdef VARIABLE",
    "",
    "condition 160 < wght, INKT < 0.5;",
    "sub dollar by dollar.rlig;",
    "",
    "#endif",
    "",
    "lookup rlig_arab_0 {",
    "\tsub lam-ar.init alef-ar.fina by lam_alef-ar;",
    "} rlig_arab_0;",
    "",
    "#ifdef VARIABLE",
    "condition 30 < wght;",
    "lookup rlig_arab_0;",
    "#endif",
    "",
    "lookup rlig_arab_0;",
])


def variable_blocks(code):
    return [line for line in code.split("\n") if line.strip() in ("#ifdef VARIABLE", "#endif")]


print("full-axis variable font (nothing to subset):")
check("left byte for byte alone", update(RLIG, ["INKT", "wght"], {}), RLIG)

print("\nvariable font pinned to INKT=0 (the condition is true there):")
arabic = update(RLIG, ["wght"], {"INKT": 0.0})
check("INKT clause resolved away, rules kept",
      [l for l in arabic.split("\n") if l.startswith("condition")],
      ["condition 160 < wght;", "condition 30 < wght;"])
check("both blocks still present", variable_blocks(arabic),
      ["#ifdef VARIABLE", "#endif", "#ifdef VARIABLE", "#endif"])

print("\nvariable font pinned to INKT=1 (the condition is false there):")
inktrap = update(RLIG, ["wght"], {"INKT": 1.0})
# Only the block that repeats the plain `lookup rlig_arab_0;` would be left, and a lone block whose
# lookups match the feature's own is what GlyphsApp mis-serialises, so every block has to go.
check("no variable block survives", variable_blocks(inktrap), [])
check("the ligature lookup is untouched", "lookup rlig_arab_0 {" in inktrap, True)
check("statics still call it", inktrap.rstrip().endswith("lookup rlig_arab_0;"), True)

print("\nnever leave a hollow #ifdef VARIABLE behind:")
for name, kept, pinned in [("INKT=0", ["wght"], {"INKT": 0.0}),
                           ("INKT=1", ["wght"], {"INKT": 1.0}),
                           ("no pin", ["wght"], {})]:
    lines = update(RLIG, kept, pinned).split("\n")
    hollow = False
    for i, line in enumerate(lines):
        if line.strip() == "#ifdef VARIABLE":
            j = i + 1
            while j < len(lines) and lines[j].strip() != "#endif":
                j += 1
            hollow |= not [x for x in lines[i + 1:j] if x.strip()]
    check("%s leaves no hollow block" % name, hollow, False)
    opens = sum(1 for l in lines if l.strip() == "#ifdef VARIABLE")
    closes = sum(1 for l in lines if l.strip() == "#endif")
    check("%s keeps #ifdef/#endif balanced" % name, opens, closes)

print("\nrunning the filter twice changes nothing the second time:")
for name, kept, pinned in [("INKT=0", ["wght"], {"INKT": 0.0}),
                           ("INKT=1", ["wght"], {"INKT": 1.0}),
                           ("full", ["INKT", "wght"], {})]:
    once = update(RLIG, kept, pinned)
    check("%s idempotent" % name, update(once, kept, pinned), once)

print("\nsmaller cases:")
check("code without any #ifdef is untouched",
      update("sub a by b;", ["wght"], {}), "sub a by b;")
check("empty code", update("", ["wght"], {}), "")
check("a condition on an axis we cannot place drops its block",
      update("#ifdef VARIABLE\ncondition 100 < wdth;\nsub a by b;\n#endif", ["wght"], {}), "")
check("a missing #endif is written back",
      update("#ifdef VARIABLE\ncondition 100 < wght;\nsub a by b;", ["wght"], {}),
      "#ifdef VARIABLE\ncondition 100 < wght;\nsub a by b;\n#endif")
check("#ifndef blocks are left alone",
      update("#ifndef VARIABLE\nsub a by b;\n#endif", ["wght"], {}),
      "#ifndef VARIABLE\nsub a by b;\n#endif")
check("a range clause that holds is dropped",
      update("#ifdef VARIABLE\ncondition 100 < wght < 200, 0.2 < INKT < 0.8;\nsub a by b;\n#endif",
             ["wght"], {"INKT": 0.5}),
      "#ifdef VARIABLE\ncondition 100 < wght < 200;\nsub a by b;\n#endif")
check("a range clause that does not hold drops the block",
      update("#ifdef VARIABLE\ncondition 0.2 < INKT < 0.8;\nsub a by b;\n#endif",
             ["wght"], {"INKT": 0.9}), "")
check("a lookup definition body is not read as an unconditional rule",
      update("lookup L {\nsub a by a.alt;\n} L;\n#ifdef VARIABLE\ncondition 100 < wght;\nsub a by a.alt;\n#endif",
             ["wght"], {}),
      "lookup L {\nsub a by a.alt;\n} L;\n#ifdef VARIABLE\ncondition 100 < wght;\nsub a by a.alt;\n#endif")

# The shape issue #2 reports: the whole feature lives inside `#ifdef VARIABLE`, so there is no
# unconditional copy of the rules to fall back on and a dropped block loses them outright.
MONO_RLIG = "\n".join([
    "#ifdef VARIABLE",
    "",
    "condition 180 < wght;",
    "sub dollar by dollar.rlig;",
    "",
    "condition 180 < wght, 0.4 < MONO;",
    "sub Q by Q.rlig;",
    "",
    "condition 0.4 < MONO;",
    "sub at by at.rlig;",
    "sub at.case by at.case.rlig;",
    "",
    "#endif",
])
# MONO wdth wght slnt, as the report has them; wdth is not in this font's masters.
RANGES = {"MONO": (0.0, 1.0), "wght": (30.0, 900.0), "slnt": (-10.0, 0.0)}


def conditions(code):
    return [line.strip() for line in code.split("\n") if line.strip().startswith("condition")]


print("\nmono variable font, MONO pinned to 1 (issue #2):")
mono = update(MONO_RLIG, ["wght", "slnt"], {"MONO": 1.0}, RANGES)
check("the satisfied block is hung on the weight axis instead of dropped", conditions(mono),
      ["condition 180 < wght;", "condition 180 < wght;", "condition 30 < wght;"])
check("its rules survive", [l for l in mono.split("\n") if l.startswith("sub at")],
      ["sub at by at.rlig;", "sub at.case by at.case.rlig;"])
check("mono idempotent", update(mono, ["wght", "slnt"], {"MONO": 1.0}, RANGES), mono)

print("\nthe same font pinned to MONO=0 (the condition is false there):")
prop = update(MONO_RLIG, ["wght", "slnt"], {"MONO": 0.0}, RANGES)
check("only the weight-gated block is left", conditions(prop), ["condition 180 < wght;"])
check("the mono rules are gone", "at.rlig" in prop, False)
check("prop idempotent", update(prop, ["wght", "slnt"], {"MONO": 0.0}, RANGES), prop)

print("\nwhat the full-range fallback needs:")
SATISFIED = "#ifdef VARIABLE\ncondition 0.4 < MONO;\nsub at by at.rlig;\n#endif"
check("with every axis pinned there is nothing to hang the condition on",
      update(SATISFIED, [], {"MONO": 1.0}, RANGES), "")
check("a kept axis with no known range is no help either",
      update(SATISFIED, ["wght"], {"MONO": 1.0}, {}), "")
check("no range information at all leaves the old behaviour",
      update(SATISFIED, ["wght"], {"MONO": 1.0}), "")
check("a negative design minimum is written the way a source would",
      update(SATISFIED, ["slnt"], {"MONO": 1.0}, {"slnt": (-10.0, 0.0)}),
      "#ifdef VARIABLE\ncondition -10 < slnt;\nsub at by at.rlig;\n#endif")
check("a fractional design minimum keeps its decimals",
      update(SATISFIED, ["opsz"], {"MONO": 1.0}, {"opsz": (5.5, 72.0)}),
      "#ifdef VARIABLE\ncondition 5.5 < opsz;\nsub at by at.rlig;\n#endif")
check("the indent of the condition line is kept",
      update("#ifdef VARIABLE\n\tcondition 0.4 < MONO;\n\tsub at by at.rlig;\n#endif",
             ["wght"], {"MONO": 1.0}, RANGES),
      "#ifdef VARIABLE\n\tcondition 30 < wght;\n\tsub at by at.rlig;\n#endif")

print("\nthe fallback does not resurrect the GSUB the sanitiser rejects:")
# The rules this block would carry everywhere are already what the feature does unconditionally, so an
# alternate feature table identical to the default one is exactly what GlyphsApp mis-serialises.
check("a block that only repeats the plain feature is still dropped",
      update("lookup L {\nsub a by a.alt;\n} L;\nlookup L;\n"
             "#ifdef VARIABLE\ncondition 0.4 < MONO;\nlookup L;\n#endif",
             ["wght"], {"MONO": 1.0}, RANGES),
      "lookup L {\nsub a by a.alt;\n} L;\nlookup L;")

print("\npassing ranges changes nothing where no block was being dropped:")
for name, kept, pinned in [("INKT=0", ["wght"], {"INKT": 0.0}),
                           ("INKT=1", ["wght"], {"INKT": 1.0}),
                           ("full", ["INKT", "wght"], {})]:
    check("%s unchanged" % name, update(RLIG, kept, pinned, {"wght": (30.0, 900.0), "INKT": (0.0, 1.0)}),
          update(RLIG, kept, pinned))

print("\naxis summary:")
_font = types.SimpleNamespace(
    axes=[types.SimpleNamespace(axisTag=tag) for tag in ("MONO", "wght", "slnt")],
    masters=[types.SimpleNamespace(internalAxesValues=values)
             for values in ([1, 30, 0], [1, 900, 0], [1, 900, -10])],
)
_kept, _pinned, _ranges = plugin.axis_summary(_font)
check("the single-value axis is pinned", (_kept, _pinned), (["wght", "slnt"], {"MONO": 1.0}))
check("every axis reports its design range", _ranges,
      {"MONO": (1.0, 1.0), "wght": (30.0, 900.0), "slnt": (-10.0, 0.0)})

print("\narguments:")
check("semicolon form", plugin.parse_axis_argument({0: "wght", 1: "slnt"}), ["wght", "slnt"])
check("comma form", plugin.parse_axis_argument({0: "wght,slnt"}), ["wght", "slnt"])
check("auto", plugin.parse_axis_argument({0: "auto"}), None)
check("no argument", plugin.parse_axis_argument(None), None)

print("\n%d failure(s)" % len(failures))
sys.exit(1 if failures else 0)
