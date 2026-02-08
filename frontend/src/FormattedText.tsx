import React from 'react';

/**
 * Renders text that may contain:
 *  - "***" or "---" as horizontal dividers
 *  - "\n" as line breaks
 *  - **bold** markers
 *  - ```lang ... ``` fenced code blocks
 *  - `inline code` markers
 *  - Preserves RTL direction
 */
export function FormattedText({ text, className }: { text: string; className?: string }) {
  // First, split on fenced code blocks: ```lang\n...\n```
  const codeBlockRegex = /```(\w*)\n([\s\S]*?)```/g;
  const segments: { type: 'text' | 'code'; content: string; lang?: string }[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = codeBlockRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: 'text', content: text.slice(lastIndex, match.index) });
    }
    segments.push({ type: 'code', content: match[2], lang: match[1] || undefined });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    segments.push({ type: 'text', content: text.slice(lastIndex) });
  }

  const rendered = segments.map((segment, segIdx) => {
    if (segment.type === 'code') {
      return (
        <pre key={segIdx} className="code-block" dir="ltr">
          <code>{segment.content}</code>
        </pre>
      );
    }

    // For text segments, split on *** or --- dividers
    const blocks = segment.content.split(/\s*(\*{3,}|-{3,})\s*/);

    return blocks.map((block, blockIdx) => {
      if (/^(\*{3,}|-{3,})$/.test(block)) {
        return <hr key={`${segIdx}-${blockIdx}`} className="text-divider" />;
      }

      const lines = block.split('\n');
      return (
        <React.Fragment key={`${segIdx}-${blockIdx}`}>
          {lines.map((line, lineIdx) => (
            <React.Fragment key={lineIdx}>
              {lineIdx > 0 && <br />}
              {renderInline(line)}
            </React.Fragment>
          ))}
        </React.Fragment>
      );
    });
  });

  return (
    <div className={`formatted-text ${className || ''}`} dir="rtl">
      {rendered}
    </div>
  );
}

/** Render inline formatting: **bold** and `inline code` */
function renderInline(text: string): React.ReactNode[] {
  // Split on **bold** and `inline code` markers
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    const boldMatch = part.match(/^\*\*(.+)\*\*$/);
    if (boldMatch) {
      return <strong key={i}>{boldMatch[1]}</strong>;
    }
    const codeMatch = part.match(/^`(.+)`$/);
    if (codeMatch) {
      return <code key={i} className="inline-code">{codeMatch[1]}</code>;
    }
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
}
