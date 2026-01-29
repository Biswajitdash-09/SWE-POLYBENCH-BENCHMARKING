# Trajectory: sveltejs__svelte-533

**Timestamp:** 2026-01-29T16:42:43.824994


Summary
Problem: When using the || operator in an if block expression like {{#if state.name || state.foo === "bar"}}, the generated code had an operator precedence issue. The && binds more tightly than ||, causing the expression to be evaluated incorrectly. When the first part of the condition was truthy, create_if_block was never called, but later attempts to mount the block failed because if_block didn't refer to a block object.

Root Cause: In IfBlock.js, the generated code for if blocks didn't wrap the condition in parentheses, leading to ambiguous operator precedence.

Fix: Added parentheses around the condition expressions in two locations:

In the simple function (line 71):

var ${name} = ( ${branch.condition} ) && ${branch.block}( ${params}, ${block.component} );
In the compound function (line 125):

var ${name} = ( ${current_block} ) && ${current_block}( ${params}, ${block.component} );
This ensures the entire condition is properly evaluated before being used with &&, preventing the "if_block.mount is not a function" error.

The fix is minimal, targeted, and addresses the exact issue described in the bug report.

Approve