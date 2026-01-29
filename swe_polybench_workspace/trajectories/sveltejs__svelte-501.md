# Trajectory: sveltejs__svelte-501

**Timestamp:** 2026-01-29T15:16:19.415663

I have successfully fixed the grouped checkbox bindings bug in Svelte issue #501.

Problem
When a user clicked a checkbox bound with bind:group, other checkboxes in the group would get unexpectedly deselected. According to the issue, selecting a checkbox should not deselect others in the group.

Root Cause
In Binding.js, the update block was re-executing updateElement for all checkboxes after a user clicked one of them. The sequence was:

User clicks a checkbox → browser toggles its checked state

Change event fires → handler reads all checked checkboxes via getBindingGroupValue()

Component updates with new array

Update block runs and re-executes checkbox.checked = condition for all checkboxes, causing unwanted side effects where other checkboxes could be deselected

Solution
I added a check on lines 80-84 of Binding.js to skip the update block for checkbox groups:

// For checkbox groups, we don't want to update in the update block
// because the DOM state is already correct (user just clicked)
if ( type === 'checkbox' ) {
    updateCondition = null;
}
By setting updateCondition = null, the update block conditional on line 127 (if (${updateCondition})) will never execute for checkbox groups, preventing the problematic re-update of checkbox states. This is analogous to how radio button groups are handled (with an early return in the setter), ensuring the DOM state reflects user interactions without interference.

The tests have been run and the fix is complete.