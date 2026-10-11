import {test} from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
import {renderMarkdown,highlightedCode} from './markdown.mjs';
const browser=new JSDOM('').window;
test('model markdown cannot run scripts, event handlers or remote media',()=>{
  const html=renderMarkdown('<img src="https://example.com/x" onerror="alert(1)"><script>alert(2)</script>\n\n[click](javascript:alert%281%29)',[],browser);
  const document=new JSDOM(html).window.document;
  assert.equal(document.querySelector('script,img,iframe,svg'),null);
  assert.equal(document.querySelector('[onerror],[onclick]'),null);
  assert.equal(document.querySelector('a')?.hasAttribute('href'),false);
});
test('evidence IDs are styled only when supplied and code is preserved literally',()=>{
  const html=renderMarkdown('**M1** supports `M1`; Q9 is unknown.\n\n```json\n{"evidence":"M1", "html":"<script>"}\n```',['M1'],browser);
  const document=new JSDOM(html).window.document;
  assert.equal(document.querySelectorAll('.inline-evidence').length,1);
  assert.ok(document.querySelector('code.hljs .hljs-attr'));
  assert.ok(document.querySelector('pre').textContent.includes('<script>'));
  assert.equal(document.querySelector('script'),null);
});
test('links exclude local and credential schemes; tables and lists stay formatted',()=>{
  const html=renderMarkdown('[local](file:///secret) [safe](https://attack.mitre.org)\n\n- first\n- second\n\n|id|result|\n|-|-|\n|M1|confirmed|',['M1'],browser);
  const document=new JSDOM(html).window.document;
  assert.equal(document.querySelector('a').hasAttribute('href'),false);
  assert.equal(document.querySelector('a[href]').getAttribute('rel'),'noopener noreferrer');
  assert.equal(document.querySelectorAll('li').length,2);
  assert.ok(document.querySelector('table'));
  assert.ok(highlightedCode('<img onerror=evil()>','unknown').includes('&lt;'));
});
test('only known evidence becomes an accessible control, never untrusted markup or code',()=>{
  const html=renderMarkdown('M1 Q9 `M1` <button data-evidence-id="Q9">spoof</button>',['M1'],browser,true);
  const document=new JSDOM(html).window.document;
  const buttons=document.querySelectorAll('button');
  assert.equal(buttons.length,1);
  assert.equal(buttons[0].dataset.evidenceId,'M1');
  assert.equal(buttons[0].type,'button');
  assert.equal(buttons[0].getAttribute('aria-label'),'Inspect evidence M1');
  assert.equal(new JSDOM(renderMarkdown('M1',['M1'],browser)).window.document.querySelector('button'),null);
});
