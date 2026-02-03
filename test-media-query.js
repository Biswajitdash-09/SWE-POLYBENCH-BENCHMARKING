import { compile } from './svelte-repo/packages/svelte/src/compiler/index.js';

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

try {
	const result = compile(source, {
		cssHash: () => 'svelte-xyz',
		dev: false
	});
	
	console.log('=== Compiled CSS ===');
	console.log(result.css.code);
	console.log('===================');
	
	// Check if whitespace is preserved
	if (result.css.code.includes('@mediaonly')) {
		console.log('\n❌ BUG DETECTED: Whitespace removed before media query condition!');
	} else if (result.css.code.includes('@media only')) {
		console.log('\n✓ Whitespace preserved correctly');
	} else {
		console.log('\n⚠ Unrecognized format');
	}
} catch (error) {
	console.error('Error:', error);
}