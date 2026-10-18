import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

test('model Markdown renders headings, emphasis and tables without executing HTML or unsafe URLs', async () => {
  const server = await createServer({server:{middlewareMode:true},appType:'custom'});
  try {
    const {default: Markdown} = await server.ssrLoadModule('/src/components/Markdown.jsx');
    const html = renderToStaticMarkup(React.createElement(Markdown, null,
      '# Findings\n\n**Exact result:** 12\n\n| Metric | Value |\n| --- | --- |\n| Rows | 12 |\n\n<script>alert(1)</script>\n\n[Unsafe](javascript:alert(1))'));
    assert.match(html, /<h1>Findings<\/h1>/);
    assert.match(html, /<strong>Exact result:<\/strong>/);
    assert.match(html, /<table>/);
    assert.doesNotMatch(html, /<script|javascript:/);
    const {Message} = await server.ssrLoadModule('/src/pages/ChatPage.jsx');
    const failed = renderToStaticMarkup(React.createElement(Message,{msg:{role:'assistant',content:'Could not calculate',execution_status:'failed',calculation_error:'PolicyError',code:'result = open("secret")'}}));
    assert.match(failed,/Calculation failed/);
    assert.doesNotMatch(failed,/Calculation succeeded|Verified calculation/);
    const success = renderToStaticMarkup(React.createElement(Message,{msg:{role:'assistant',content:'Rows: 12',execution_status:'succeeded',evidence:'12'}}));
    assert.match(success,/Calculation succeeded/);
    assert.match(success,/<details class="evidence-details">/);
  } finally { await server.close(); }
});
