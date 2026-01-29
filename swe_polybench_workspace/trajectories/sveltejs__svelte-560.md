# Trajectory: sveltejs__svelte-560

**Timestamp:** 2026-01-29T18:14:22.340201

I've fixed the "Outros aren't correctly aborted" bug in Svelte (instance sveltejs__svelte-560) by adding .abort() calls to prevent state corruption when blocks are reused while outro transitions are still in progress.

Changes made:

EachBlock.js - Added abort call in the keyed function to cancel ongoing outros when reusing blocks from the lookup table

IfBlock.js - Added 6 abort calls in simple, compound, and compoundWithOutros functions to prevent conflicts between ongoing outros and subsequent intro/mount/update operations

Root cause: When keyed each block items or if block conditions changed rapidly, blocks could be reused while outro transitions were still in progress. The deferred outro callback would eventually execute, setting the lookup entry to null and corrupting the state after the block had been updated and made visible.

Fix: Calling .abort() before reusing blocks or calling .intro(), .mount(), or .update() ensures transitions are cancelled cleanly, preventing deferred callbacks from executing and maintaining consistent state.