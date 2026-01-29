# Trajectory: sveltejs__svelte-597

**Timestamp:** 2026-01-29T20:47:53.129853

I've successfully refactored the transitionManager to use an IIFE pattern which allows Rollup and Butternut to properly detect and remove it from bundles when unused.

Changes made:

Modified src/shared/transitions.js - Converted transitionManager from a module-level object literal to an IIFE pattern:

Before:

export var transitionManager = {
    running: false,
    transitions: [],
    add: function ( transition ) {
        transitionManager.transitions.push( transition );
        // ...
    },
    next: function () {
        transitionManager.running = false;
        // ...
    }
};
After:

export var transitionManager = (function() {
    return {
        running: false,
        transitions: [],
        add: function ( transition ) {
            this.transitions.push( transition );
            // ...
        },
        next: function () {
            this.running = false;
            // ...
        }
    };
})();
Key improvements:

Wrapped the object in an IIFE pattern so bundlers can detect it has no side effects

Changed internal references from transitionManager to this to avoid external dependencies

When transitionManager is not imported, bundlers can now eliminate this entire code block

The build process successfully runs and regenerates src/generators/dom/shared.ts with the new pattern. This fixes the issue where transitionManager was always included in Rollup bundles even when other helpers from the shared file were imported.