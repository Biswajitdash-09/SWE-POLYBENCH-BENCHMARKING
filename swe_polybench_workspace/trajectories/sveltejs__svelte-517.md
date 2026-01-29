# Trajectory: sveltejs__svelte-517

**Timestamp:** 2026-01-29T15:57:54.461878

I've successfully fixed the bug in Svelte where custom element tags with hyphens were causing invalid JavaScript to be generated.

Summary
Bug: Svelte was creating invalid JavaScript when using custom element tags (like <custom-element>) in templates. The compiler was generating code like:

var custom-element = createElement('custom-element');  // Syntax Error!
Root Cause: In Element.js, the element name was passed directly to getUniqueName() without sanitizing it for valid JavaScript identifier characters.

Fix: Added sanitization to replace non-word characters (anything other than letters, digits, underscores) with underscores:

const name = block.getUniqueName( node.name.replace( /[^\w]/g, '_' ) );
This now generates valid JavaScript:

var custom_element = createElement('custom-element');  // Valid!
Files Modified:

swe_polybench_workspace/sveltejs__svelte-517/src/generators/dom/visitors/Element/Element.js

Test Case Created: Added a test case for custom elements with hyphenated names:

swe_polybench_workspace/sveltejs__svelte-517/test/runtime/samples/custom-element/main.html

swe_polybench_workspace/sveltejs__svelte-517/test/runtime/samples/custom-element/_config.js

Tests: All tests passed successfully, confirming the fix works correctly.

The fix follows the same sanitization pattern already used in Attribute.js, ensuring consistent behavior across the codebase.