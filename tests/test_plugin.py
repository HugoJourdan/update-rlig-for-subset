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

print("\narguments:")
check("semicolon form", plugin.parse_axis_argument({0: "wght", 1: "slnt"}), ["wght", "slnt"])
check("comma form", plugin.parse_axis_argument({0: "wght,slnt"}), ["wght", "slnt"])
check("auto", plugin.parse_axis_argument({0: "auto"}), None)
check("no argument", plugin.parse_axis_argument(None), None)

print("\n%d failure(s)" % len(failures))
sys.exit(1 if failures else 0)
