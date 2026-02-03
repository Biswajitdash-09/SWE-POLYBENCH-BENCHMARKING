import { compile } from './svelte-repo/packages/svelte/src/compiler/index.js';

const tests = [
	{
		name: 'Basic @media with words',
		source: `<div>hello</div>
<style>
	@media only screen and (min-width: 400px) {
		div {
			color: red;
		}
	}
</style>`,
		options: { cssHash: () => 'svelte-xyz', dev: false }
	},
	{
		name: 'With inject_styles',
		source: `<div>hello</div>
<style>
	@media only screen and (min-width: 400px) {
		div {
			color: red;
		}
	}
</style>`,
		options: { cssHash: () => 'svelte-xyz', dev: false, inject_styles: true }
	},
	{
		name: 'Dev mode',
		source: `<div>hello</div>
<style>
	@media only screen and (min-width: 400px) {
		div {
			color: red;
		}
	}
</style>`,
		options: { cssHash: () => 'svelte-xyz', dev: true }
	},
	{
		name: '@-webkit-media vendor prefix',
		source: `<div>hello</div>
<style>
	@-webkit-media only screen and (min-width: 400px) {
		div {
			color: red;
		}
	}
</style>`,
		options: { cssHash: () => 'svelte-xyz', dev: false }
	},
	{
		name: 'Multiple media rules with preceding CSS',
		source: `<div>hello</div>
<style>
	div {
		color: blue;
	}
	@media only screen and (min-width: 400px) {
		div {
			color: red;
		}
	}
	@media print {
		div {
			color: black;
		}
	}
</style>`,
		options: { cssHash: () => 'svelte-xyz', dev: false }
	}
];

for (const test of tests) {
	try {
		const result = compile(test.source, test.options);
		const css = result.css ? result.css.code : '';
		
		console.log(`\n=== Test: ${test.name} ===`);
		console.log('Options:', test.options);
		console.log('CSS:', css);
		
		// Check for the bug pattern
		if (css.includes('@mediaonly') || css.includes('@-webkit-mediaonly')) {
			console.log('❌ BUG DETECTED: Whitespace removed!');
		} else if (css.includes('@media only') || css.includes('@-webkit-media only')) {
			console.log('✓ Whitespace preserved');
		} else {
			console.log('⚠ No @media found or different format');
		}
	} catch (error) {
		console.error('❌ Error:', error.message);
	}
}