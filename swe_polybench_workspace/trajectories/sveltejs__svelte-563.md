# Trajectory: sveltejs__svelte-563

**Timestamp:** 2026-01-29T18:20:45.593280

I've fixed the bug where {{yield}} content wasn't being injected in the correct place.

Changes made to YieldTag.js:

Added node as the first parameter to the function (matching other visitor functions like IfBlock and EachBlock)

Calculated the anchor using the pattern from IfBlock/EachBlock: (node.next && node.next._state.name) || 'null'

Marked the next sibling as used as an anchor if it exists: node.next.usedAsAnchor = true

Changed the mount call to use the anchor instead of null as the second parameter

Root cause: The original code always mounted the yield content with null as the anchor, which means it was appended to the end of the parent. This caused the button (next sibling) to appear before the yielded content, when it should appear after.

Fix: By using the next sibling as an anchor, the yielded content is now inserted before the button, ensuring correct ordering. If there's no next sibling, it still appends to the end as before.

The fix follows the same pattern used by IfBlock and EachBlock visitors for proper DOM insertion positioning.