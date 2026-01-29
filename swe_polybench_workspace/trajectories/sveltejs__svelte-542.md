# Trajectory: sveltejs__svelte-542

**Timestamp:** 2026-01-29T16:52:18.661393

Successfully fixed the IE compatibility issue by replacing selectedOptions with querySelector selectors in the Binding.js file:

Line 33: Replaced ${state.parentNode}.selectedOptions[0] with ${state.parentNode}.querySelector(':checked') for single select element bindings

Line 163: Replaced ${state.parentNode}.selectedOptions with ${state.parentNode}.querySelectorAll(':checked') for multi-select element bindings

The querySelector(':checked') and querySelectorAll(':checked') selectors are supported in IE and will maintain the same functionality as the original selectedOptions property. This change enables the <select> tests to run without requiring a new version of JSDOM.