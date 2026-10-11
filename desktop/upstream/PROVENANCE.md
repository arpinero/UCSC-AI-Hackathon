# llama.cpp source attribution

Source repository: https://github.com/ggml-org/llama.cpp

Copied revision: `b97ebdc98f6053604a19d861c08d8087601b96e0`.
This matches the installed source checkout observed on the ASUS on October 10, 2026.

`llama-webui-src.zip` preserves the complete original `tools/server/webui/src`, its package/configuration files, README and MIT license. It can be extracted to inspect the original chat UI without downloading it again. No credentials or model weights are included.

The running Sentinel UI uses original Button, Textarea, Badge and shared utilities from that source under `src/lib/ui`. These primitives retain their original source, with an alias resolving their utility imports. Sentinel's pipeline workspace, styling, event transport and approval flow are new application code. The complete llama chat application is archived, not falsely claimed to be wired to the council API unchanged.

Original license: `LLAMA-LICENSE`. Copyright notices must accompany copies.
