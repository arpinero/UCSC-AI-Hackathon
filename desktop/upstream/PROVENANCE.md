# llama.cpp UI source attribution

Source: https://github.com/ggml-org/llama.cpp

Revision: 97ebdc98f6053604a19d861c08d8087601b96e0, matching the ASUS installation. The original full web UI source is preserved in llama-webui-src.zip. MIT license: LLAMA-LICENSE.

The browser now renders the original floating Sidebar.Provider, Root, Inset, Trigger and Menu components, along with original Button, Tooltip, Input, Separator, Skeleton and Card components copied into src/lib/ui. Original app.css and css-classes.ts provide the complete llama light/dark theme and composer tokens. Original ChatFormTextarea.svelte, is-mobile.svelte.ts, autoresize-textarea.ts and css.ts are copied unchanged.

App.svelte adapts the upstream +layout.svelte shell and ChatScreen/ChatForm presentation to the council transport. Upstream conversation storage and llama completion transport are replaced by the existing incident bridge; models cannot approve actions through chat. Pipeline events, evidence, metrics, service inventory and written human decisions are application extensions styled by pipeline.css. The old bespoke green workspace stylesheet is no longer imported. This is a source-based adaptation, not the unmodified entire SvelteKit application.
