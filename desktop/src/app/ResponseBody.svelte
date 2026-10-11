<script lang="ts">
  import {renderMarkdown} from './markdown.mjs';
  let {content, evidenceIds=[], onEvidence}: {content:string;evidenceIds?:string[];onEvidence?:(id:string)=>void} = $props();
  let html = $derived(renderMarkdown(content,evidenceIds,window,!!onEvidence));
  function openEvidence(event:MouseEvent) {
    const target = (event.target as HTMLElement).closest<HTMLButtonElement>('button[data-evidence-id]');
    const id = target?.dataset.evidenceId;
    if(id && evidenceIds.includes(id)) onEvidence?.(id);
  }
  function bindEvidence(node:HTMLDivElement) {
    node.addEventListener('click',openEvidence);
    return {destroy(){node.removeEventListener('click',openEvidence);}};
  }
</script>
<!-- Evidence controls are real keyboard-accessible buttons generated after sanitization. -->
<div class="response-prose" use:bindEvidence>{@html html}</div>
