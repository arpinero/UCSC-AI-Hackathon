<script lang="ts">
  import {Copy, Check} from '@lucide/svelte';
  import {highlightedCode} from './markdown.mjs';
  let {value, label='Response JSON'}:{value:any;label?:string}=$props();
  let copied=$state(false), failed=$state(false);
  let content=$derived(JSON.stringify(value,null,2));
  let html=$derived(highlightedCode(content,'json'));
  async function copy() {try{await navigator.clipboard.writeText(content);copied=true;failed=false;}catch{failed=true;}}
</script>
<div class="code-block">
  <div class="code-caption"><span>{label}</span><button aria-label="Copy JSON" onclick={copy}>{#if copied}<Check size={13}/>{:else}<Copy size={13}/>{/if}{copied?'Copied':failed?'Select text to copy':'Copy'}</button></div>
  <!-- svelte-ignore a11y_no_noninteractive_tabindex (Keyboard access to scrollable code.) -->
  <pre tabindex="0" role="region" aria-label={label}><code class="hljs">{@html html}</code></pre>
</div>
