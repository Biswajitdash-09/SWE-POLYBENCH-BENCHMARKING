# Trajectory: sveltejs__svelte-580

**Timestamp:** 2026-01-29T20:27:44.782022

I've successfully fixed the bug in the sveltejs/svelte repository (sveltejs__svelte-580) by changing an unnecessary build-time error to a warning.

Changes Made:
Modified src/validate/html/validateEventHandler.js:

Changed validator.error(message, start) to validator.warn(message, start) on line 34

This allows builds to continue when event handlers reference methods that will be added dynamically at instantiation-time

Updated test expectations:

Created test/validator/samples/method-nonexistent/warnings.json with the warning message

Deleted test/validator/samples/method-nonexistent/errors.json

Created test/validator/samples/method-nonexistent-helper/warnings.json with the warning message

Deleted test/validator/samples/method-nonexistent-helper/errors.json

Problem Solved:
Previously, when developers added methods at instantiation-time (e.g., instance.foo = function() {}), the validator would throw an error: '[method name]' is an invalid callee (should be one of this.*, event.*, set, fire, destroy, complete or restore). This caused the build to fail, even though the code would work correctly at runtime.

Now, the validator will only issue a warning, allowing the build to continue while still informing developers about unrecognized callees. This enables legitimate use cases where methods are dynamically added to component instances.