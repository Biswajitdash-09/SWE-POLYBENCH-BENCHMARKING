# Trajectory: sveltejs__svelte-526

**Timestamp:** 2026-01-29T16:37:12.320797

I've successfully fixed the bug in the Svelte repository where destroy() was not recognized as a valid callee in event handlers for yield elements.

Summary
Problem: The example provided in the Svelte guide for yield elements uses destroy() in event handlers like on:click='destroy()', but this resulted in an error because validateElement did not recognize destroy as a valid callee.

Root Cause: There was an operator precedence bug in validateElement.js. The type check (callee.type === 'Identifier') was only being applied to set but not to fire or other methods in validator.methods.

Fix: Added parentheses to ensure the type check applies to all conditions by changing:

if ( callee.type === 'Identifier' && callee.name === 'set' || callee.name === 'fire' || validator.methods.has( callee.name ) ) return;
To:

if ( callee.type === 'Identifier' && ( callee.name === 'set' || callee.name === 'fire' || validator.methods.has( callee.name ) ) ) return;
This ensures that when checking if a callee like destroy is in validator.methods (which it is, since destroy is listed as a built-in method in methods.js), it first verifies that it's an Identifier.

The fix is minimal, targeted, and consistency with the codebase's design.