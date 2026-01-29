# Trajectory: sveltejs__svelte-510

**Timestamp:** 2026-01-29T15:24:40.946738

I've successfully fixed the bug in EachBlock.js where the else block reference was not being nulled out after destruction.

The fix was applied to two locations where the else block is destroyed:

Lines 68-69 (in the hasUpdateMethod branch):

${each_block_else}.destroy( true );
${each_block_else} = null;
Lines 76-77 (in the else branch for no hasUpdateMethod):

${each_block_else}.destroy( true );
${each_block_else} = null;
This ensures that when an each block transitions from showing the else block to showing items (when the array has items), the else block is properly destroyed AND its reference is cleaned up to prevent stale references and potential memory leaks.