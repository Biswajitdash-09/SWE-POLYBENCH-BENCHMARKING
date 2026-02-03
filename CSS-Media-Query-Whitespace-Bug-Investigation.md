# CSS @media Query Whitespace Bug Investigation

## Issue
**Reference**: sveltejs__svelte-765
**Reported Bug**: CSS @media tags are compiled incorrectly with whitespace removed between `@media` and the media query condition.
**Example**: `@media only screen and (min-width: 42em)` becomes `@mediaonly screen and (min-width: 42em)`

## Investigation Summary

### Files Examined
1. `/svelte-repo/packages/svelte/src/compiler/phases/3-transform/css/index.js` - CSS transformation logic
2. `/svelte-repo/packages/svelte/src/compiler/phases/css.js` - CSS utility functions
3. `/svelte-repo/packages/svelte/tests/css/test.ts` - CSS test runner
4. `/svelte-repo/packages/svelte/tests/css/samples/media-query-word/` - Existing media query tests

### Code Analysis

#### Atrule Visitor (lines 82-99)
The CSS Atrule visitor handles CSS at-rules like `@media` and `@keyframes`:
```javascript
Atrule(node, { next, state }) {
    if (is_keyframes_node(node)) {
        // Special handling for keyframes with whitespace manipulation
        if (!state.minify) {
            state.code.prependRight(node.start, '\n');
            // ... additional whitespace handling
        }
    }
    next();
}
```

For media queries, the visitor simply calls `next()` without any special whitespace manipulation.

#### `is_keyframes_node()` Function
```javascript
export const is_keyframes_node = (node) => remove_css_prefix(node.name) === 'keyframes';
```
This function correctly identifies keyframes nodes. For media queries, `node.name` is "media", so this returns false.

#### `remove_preceding_whitespace()` Function
```javascript
function remove_preceding_whitespace(end, state) {
    let start = end;
    while (/\s/.test(state.code.original[start - 1])) start--;
    if (start < end) state.code.remove(start, end);
}
```
This function removes preceding whitespace when `!state.minify` is false (i.e., when minify is true).

### Testing Results

#### Test 1: Basic @media with words
```html
<style>
    @media only screen and (min-width: 400px) {
        div {
            color: red;
        }
    }
</style>
```
**Result**: ✓ WHITESPACE PRESERVED
**Output**: `@media only screen and (min-width: 400px)`

#### Test 2: Dev mode
**Options**: `{ dev: true }`
**Result**: ✓ WHITESPACE PRESERVED

#### Test 3: Vendor prefixes (@-webkit-media)
```html
@-webkit-media only screen and (min-width: 400px)
```
**Result**: ✓ WHITESPACE PRESERVED

#### Test 4: Multiple media rules with preceding CSS
```html
<style>
    div { color: blue; }
    @media only screen and (min-width: 400px) { ... }
    @media print { ... }
</style>
```
**Result**: ✓ WHITESPACE PRESERVED

### Existing Tests
The existing test suite includes:
- `/tests/css/samples/media-query-word/` - Tests @media with words
- `/tests/css/samples/media-query/` - Tests general media queries

Both tests expect and verify that whitespace is preserved, and they pass.

## Conclusion

**The bug does NOT exist in Svelte version 5.49.1.**

All tests confirm that whitespace is correctly preserved between `@media` and the media query conditions. The issue sveltejs__svelte-765 must have been fixed in a previous version of Svelte.

### Possible Explanations
1. The bug was fixed in a previous version during a CSS transformation refactoring
2. The bug was reported against an older version of Svelte.js (possibly version 3.x)
3. The fix may have been part of a larger refactoring and not specifically mentioned in commit messages

## Recommendations

Since the bug doesn't exist in the current codebase:
1. No fix is required for Svelte 5.49.1
2. The existing test suite provides adequate coverage for this scenario
3. If the issue is still reported by users, verify they are using Svelte 5.49.1 or later

## Test Files Created

1. `test-media-query.js` - Basic test for media query whitespace preservation
2. `test-media-query-comprehensive.js` - Comprehensive tests covering multiple scenarios

Both tests passed, confirming the bug is resolved.