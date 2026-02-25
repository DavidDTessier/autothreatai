import DOMPurify from 'dompurify';

const ALLOWED_TAGS = ['p', 'h1', 'h2', 'h3', 'strong', 'em', 'code', 'pre', 'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'td', 'th', 'br', 'blockquote'];
const ALLOWED_ATTR = [];

/**
 * Convert simple markdown to HTML, then sanitize to prevent XSS.
 */
export function markdownToSafeHtml(markdown) {
  if (!markdown || !String(markdown).trim()) return '';
  let html = String(markdown)
    .replace(/^# (.*)$/gim, '<h1>$1</h1>')
    .replace(/^## (.*)$/gim, '<h2>$1</h2>')
    .replace(/^### (.*)$/gim, '<h3>$1</h3>')
    .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/gim, '<em>$1</em>')
    .replace(/`(.*?)`/gim, '<code>$1</code>')
    .replace(/\n\n/gim, '</p><p>');
  html = '<p>' + html + '</p>';
  return DOMPurify.sanitize(html, { ALLOWED_TAGS, ALLOWED_ATTR });
}
