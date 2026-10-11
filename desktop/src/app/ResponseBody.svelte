<script lang="ts">
  import {renderMarkdown} from './markdown.mjs';
  let {content, evidenceIds=[]}: {content:string;evidenceIds?:string[]} = $props();
  let html = $derived(renderMarkdown(content,evidenceIds));
</script>
<div class="response-prose">{@html html}</div>
