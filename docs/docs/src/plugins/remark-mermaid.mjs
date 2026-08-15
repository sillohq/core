/**
 * Takes ```mermaid fences away from Expressive Code.
 *
 * Starlight renders every fenced block through Expressive Code, which turns
 * the diagram source into syntax-highlighted text: the 248 diagrams in
 * /advanced/ shipped as literal `graph TD` and `-->` on the page. Expressive
 * Code has no per-language opt-out, so the fence has to stop being a `code`
 * node before it reaches that plugin.
 *
 * Rewriting it to a raw `html` node does exactly that, and leaves a plain
 * <pre class="mermaid"> for the browser-side renderer to pick up. The source is
 * kept as text inside the element rather than in an attribute so that a page
 * with no JavaScript still shows the diagram definition instead of nothing.
 */
import { visit } from 'unist-util-visit';

/** Escape for a text position inside an element. */
function escapeHtml(value) {
    return value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

export function remarkMermaid() {
    return function transformer(tree) {
        visit(tree, 'code', (node, index, parent) => {
            if (node.lang !== 'mermaid' || !parent || index === null) {
                return;
            }

            parent.children[index] = {
                type: 'html',
                value:
                    '<pre class="mermaid" data-mermaid-source>'
                    + escapeHtml(node.value)
                    + '</pre>',
            };
        });
    };
}

export default remarkMermaid;
