# Trajectory: sveltejs__svelte-515

**Timestamp:** 2026-01-29T15:44:21.126509

Fixed the bug where nested components with static content were calling .update without defining it.

Changes Made:
Fixed the bug in Component.js:

Added a conditional check to only call update() on the yield fragment if the child block has an update method (childBlock.hasUpdateMethod)

This prevents errors when a parent component updates and tries to call update on a child component's fragment that contains only static HTML (which won't have an update method)

Created test case in test/runtime/samples/component-yield-static/:

main.html: Parent component with dynamic content ({{x}}) that uses a child component

StaticContent.html: Child component with only static HTML (no dynamic expressions)

_config.js: Test that updates the parent component and verifies it doesn't crash

The fix ensures that when a parent component with reactive content updates, it only calls update() on child components that actually have an update method, preventing runtime errors for components with static-only content.