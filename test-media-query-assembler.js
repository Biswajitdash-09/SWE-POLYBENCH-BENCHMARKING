import { compile } from './svelte-repo/packages/svelte/compiler/index.js';

// Test with @media query containing words
const source = `
<div>hello</div>

<style>
    @media only screen and (min-width: 400px) {
        div {
            color: red;
        }
    }
</style>
`;

console.log('Testing @media query compilation...\n');

try {
    const result = compile(source, {
        cssHash: () => 'svelte-xyz'
    });
    
    console.log('Generated CSS:');
    console.log(result.css);
    console.log('\n');
    
    // Check for the space issue
    if (result.css.includes('@mediaonly')) {
        console.error('❌ BUG FOUND: Space is removed between @media and query!');
        console.error('Contains "@mediaonly" instead of "@media only"');
    } else if (result.css.includes('@media only')) {
        console.log('✓ Space is preserved correctly');
    } else {
        console.log('⚠ No @media directive found in output');
    }
    
} catch (error) {
    console.error('Error compiling:', error.message);
    process.exit(1);
}