import React from 'react';

/**
 * Renders text that may contain:
 *  - "***" or "---" as horizontal dividers
 *  - "\n" as line breaks
 *  - **bold** markers
 *  - Preserves RTL direction
 */
export function FormattedText({ text, className }: { text: string; className?: string }) {
  // Split on *** or --- dividers (with optional surrounding whitespace)
  const blocks = text.split(/\s*(\*{3,}|-{3,})\s*/);

  const rendered = blocks.map((block, blockIdx) => {
    // If this segment is a divider marker, render an <hr>
    if (/^(\*{3,}|-{3,})$/.test(block)) {
      return <hr key={blockIdx} className="text-divider" />;
    }

    // Split on newlines
    const lines = block.split('\n');
    return (
      <React.Fragment key={blockIdx}>
        {lines.map((line, lineIdx) => (
          <React.Fragment key={lineIdx}>
            {lineIdx > 0 && <br />}
            {renderBold(line)}
          </React.Fragment>
        ))}
      </React.Fragment>
    );
  });

  return (
    <div className={`formatted-text ${className || ''}`} dir="rtl">
      {rendered}
    </div>
  );
}

/** Replace **text** with <strong>text</strong> */
function renderBold(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    const match = part.match(/^\*\*(.+)\*\*$/);
    if (match) {
      return <strong key={i}>{match[1]}</strong>;
    }
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
}
