import { Marked } from 'marked';
import createDOMPurify from 'dompurify';
import hljs from 'highlight.js/lib/core';
import json from 'highlight.js/lib/languages/json';
import python from 'highlight.js/lib/languages/python';
import bash from 'highlight.js/lib/languages/bash';
import javascript from 'highlight.js/lib/languages/javascript';
import yaml from 'highlight.js/lib/languages/yaml';
import sql from 'highlight.js/lib/languages/sql';

for (const [name, language] of Object.entries({json, python, bash, javascript, yaml, sql})) hljs.registerLanguage(name, language);
export const escapeHTML = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function highlightedCode(content, language = 'json') {
  return hljs.getLanguage(language) ? hljs.highlight(String(content), {language, ignoreIllegals:true}).value : escapeHTML(content);
}
const markdown = new Marked({gfm:true, breaks:true, renderer: {
  html({text}) { return escapeHTML(text); },
  code({text, lang}) {
    const language = (lang || 'text').split(/\s/)[0].toLowerCase();
    return `<div class="code-block"><div class="code-caption">${escapeHTML(language)}</div><pre><code class="hljs">${highlightedCode(text, language)}</code></pre></div>`;
  }
}});

/** Captured evidence and model content are untrusted. No remote media or active HTML. */
export function renderMarkdown(content, evidenceIds = [], browserWindow = window) {
  const clean = createDOMPurify(browserWindow).sanitize(markdown.parse(String(content || '')),
    {ALLOWED_TAGS:['p','br','strong','em','del','h1','h2','h3','h4','ul','ol','li','blockquote','pre','code','span','div','a','table','thead','tbody','tr','th','td','hr'],
     ALLOWED_ATTR:['href','title','class'], ALLOW_DATA_ATTR:false});
  const template = browserWindow.document.createElement('template');
  template.innerHTML = clean;
  for (const link of template.content.querySelectorAll('a')) {
    const href = link.getAttribute('href') || '';
    if (!/^(https?:\/\/|#)/i.test(href)) link.removeAttribute('href');
    link.setAttribute('rel','noopener noreferrer'); link.setAttribute('target','_blank');
  }
  const knownIds = new Set(evidenceIds.map(String));
  const walker = browserWindow.document.createTreeWalker(template.content, 4);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    if (node.parentElement?.closest('code,pre,a,.code-caption')) continue;
    const pattern = /\b(?:T\d{4}(?:\.\d{3})?|[A-Za-z]+-\d{2}|[A-Z]\d+)\b/g;
    const text = node.textContent || '';
    const matches = [...text.matchAll(pattern)].filter(match => knownIds.has(match[0]) || /^T\d|^[A-Za-z]+-\d/.test(match[0]));
    if (!matches.length) continue;
    const fragment = browserWindow.document.createDocumentFragment(); let cursor=0;
    for (const match of matches) {
      fragment.append(text.slice(cursor,match.index));
      const chip=browserWindow.document.createElement('span');
      chip.className=knownIds.has(match[0])?'inline-evidence':'inline-entity'; chip.textContent=match[0];
      fragment.append(chip); cursor=match.index+match[0].length;
    }
    fragment.append(text.slice(cursor)); node.replaceWith(fragment);
  }
  return template.innerHTML;
}
