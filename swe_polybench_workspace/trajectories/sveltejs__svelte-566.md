# Trajectory: sveltejs__svelte-566

**Timestamp:** 2026-01-29T18:56:21.858011

Successfully implemented transition directive validation for Svelte task sveltejs__svelte-566.

Implementation
Added validation in src/validate/html/validateElement.js to detect problematic transition directive patterns:

Duplicate in: transitions - Reports "Only one 'in:{name}' transition allowed per element"

Duplicate out: transitions - Reports "Only one 'out:{name}' transition allowed per element"

Mixing transition: with in: - Reports "Cannot mix 'transition:{name}' with 'in:{name}'"

Mixing transition: with out: - Reports "Cannot mix 'transition:{name}' with 'out:{name}'"

Using all three of same name - Reports "Cannot mix 'transition:{name}' with 'in:{name}' and 'out:{name}'"

Test Cases
Created 5 test cases in test/validator/samples/:

transition-duplicate-in - Tests <div in:fade in:fade></div>

transition-duplicate-out - Tests <div out:fade out:fade></div>

transition-mix-in-transition - Tests <div transition:fade in:fade></div>

transition-mix-out-transition - Tests <div transition:fade out:fade></div>

transition-mix-all-three - Tests <div transition:fade in:fade out:fade></div>

Results
All 5 validation tests passed, confirming the implementation correctly prevents problematic transition directive combinations on the same element.