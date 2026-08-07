/* eslint-disable ts/explicit-function-return-type */
/* eslint-disable accessor-pairs */
/* eslint-disable ts/strict-boolean-expressions */

import { PAGE_TITLE_ID } from '../../../../core/config/constants';

export class StarlightTOC extends HTMLElement {
    private _current = this.querySelector<HTMLAnchorElement>('a[aria-current="true"]');
    private minH = Number.parseInt(this.dataset.minH || '2', 10);
    private maxH = Number.parseInt(this.dataset.maxH || '3', 10);

    protected set current(link: HTMLAnchorElement) {
        if (link === this._current) return;
        if (this._current) this._current.removeAttribute('aria-current');
        link.setAttribute('aria-current', 'true');
        this._current = link;
    }

    private onIdle = (cb: IdleRequestCallback) =>
        (window.requestIdleCallback || ((cb) => setTimeout(cb, 1)))(cb);

    constructor() {
        super();
        this.onIdle(() => this.init());
    }

    private init = (): void => {
        /** All the links in the table of contents. */
        const links = [...this.querySelectorAll('a')];

        /** Test if an element is a table-of-contents heading. */
        const isHeading = (el: Element): el is HTMLHeadingElement => {
            if (el instanceof HTMLHeadingElement) {
                // Special case for page title h1
                if (el.id === PAGE_TITLE_ID) return true;
                // Check the heading level is within the user-configured limits for the ToC
                const level = el.tagName[1];
                if (level) {
                    const int = Number.parseInt(level, 10);
                    if (int >= this.minH && int <= this.maxH) return true;
                }
            }
            return false;
        };

        /** Walk up the DOM to find the nearest heading. */
        const getElementHeading = (el: Element | null): HTMLHeadingElement | null => {
            if (!el) return null;
            const origin = el;
            while (el) {
                if (isHeading(el)) return el;
                // Assign the previous sibling’s last, most deeply nested child to el.
                el = el.previousElementSibling;
                while (el?.lastElementChild) {
                    el = el.lastElementChild;
                }
                // Look for headings amongst siblings.
                const h = getElementHeading(el);
                if (h) return h;
            }
            // Walk back up the parent.
            return getElementHeading(origin.parentElement);
        };

        /** Handle intersections and set the current link to the heading for the current intersection. */
        const setCurrent: IntersectionObserverCallback = (entries) => {
            for (const { isIntersecting, target } of entries) {
                if (!isIntersecting) continue;
                const heading = getElementHeading(target);
                if (!heading) continue;
                const link = links.find(
                    (link) => link.hash === `#${encodeURIComponent(heading.id)}`
                );
                if (link) {
                    this.current = link;
                    break;
                }
            }
        };

        // Observe elements with an `id` (most likely headings) and their siblings.
        // Also observe direct children of `.content` to include elements before
        // the first heading.
        const toObserve = document.querySelectorAll('main [id], main [id] ~ *, main .content > *');

        let observer: IntersectionObserver | undefined;
        const observe = () => {
            if (observer) return;
            observer = new IntersectionObserver(setCurrent, { rootMargin: this.getRootMargin() });
            toObserve.forEach((h) => observer!.observe(h));
        };
        observe();

        let timeout: NodeJS.Timeout;
        window.addEventListener('resize', () => {
            // Disable intersection observer while window is resizing.
            if (observer) {
                observer.disconnect();
                observer = undefined;
            }
            clearTimeout(timeout);
            timeout = setTimeout(() => this.onIdle(observe), 200);
        });

        this.trackScroll(links);
    };

    /**
     * Move the marker with the page rather than with the current heading.
     *
     * The intersection observer above answers a different question — which
     * heading is in view — and it answers it in steps. A marker driven from it
     * sits still through a long section and then jumps. This interpolates
     * between two entries by how far the reader is between their headings, so
     * the marker travels continuously as the page scrolls.
     *
     * Nothing here reads layout during a scroll. Positions are measured once
     * up front and again on resize; each frame only reads scrollY and writes
     * two custom properties, which is what keeps it off the layout path.
     */
    private trackScroll(links: HTMLAnchorElement[]): void {
        const body = this.querySelector<HTMLElement>('.toc-body');
        const marker = this.querySelector<HTMLElement>('.toc-marker');
        if (!body || !marker) return;

        interface Stop {
            /** Scroll position at which this heading reaches the reading line. */
            arrive: number;
            /** Where the fill should end when it does, within the list. */
            edge: number;
        }

        let stops: Stop[] = [];
        let anchor = 0;

        /** Distance from the top of `root`, walking offsetParent. */
        const offsetWithin = (element: HTMLElement, root: HTMLElement): number => {
            let top = 0;
            let node: HTMLElement | null = element;
            while (node && node !== root) {
                top += node.offsetTop;
                node = node.offsetParent as HTMLElement | null;
            }
            return top;
        };

        const measure = (): void => {
            // The reading line the intersection observer above uses, so the
            // fill and the emboldened link agree about where "here" is.
            const header = document.querySelector('header')?.getBoundingClientRect().height || 0;
            anchor = header + 32;

            const maxScroll = Math.max(
                0,
                document.documentElement.scrollHeight - window.innerHeight
            );

            const found: { arrive: number; edge: number }[] = [];
            for (const link of links) {
                const id = decodeURIComponent(link.hash.slice(1));
                const heading = id ? document.getElementById(id) : null;
                if (!heading) continue;
                found.push({
                    arrive: heading.getBoundingClientRect().top + window.scrollY - anchor,
                    edge: offsetWithin(link, body) + link.offsetHeight,
                });
            }
            found.sort((a, b) => a.arrive - b.arrive);

            /*
             * The last screenful of headings never reaches the reading line —
             * the document runs out first — so their natural arrival positions
             * are all past the end of the scroll range. Left alone the fill
             * freezes for the whole final screen and never covers the entries
             * it is still scrolling through. They are respaced across whatever
             * scrolling remains instead, which also guarantees the rail is
             * full at the bottom of the page.
             */
            let tail = found.length;
            while (tail > 0 && found[tail - 1]!.arrive > maxScroll) tail--;
            const remaining = found.length - tail;
            if (remaining > 0) {
                const start = tail > 0 ? Math.min(found[tail - 1]!.arrive, maxScroll) : 0;
                const step = (maxScroll - start) / remaining;
                for (let i = 0; i < remaining; i++) {
                    found[tail + i]!.arrive = start + step * (i + 1);
                }
            }

            stops = found;
        };

        const update = (): void => {
            if (stops.length === 0) {
                body.removeAttribute('data-marker');
                return;
            }

            const y = window.scrollY;
            let index = 0;
            while (index < stops.length - 1 && stops[index + 1]!.arrive <= y) index++;

            const from = stops[index]!;
            const to = stops[index + 1];
            let edge = from.edge;

            if (to) {
                const span = to.arrive - from.arrive;
                // Clamped, so scrolling above the first heading holds the fill
                // at that heading rather than pulling it negative.
                const progress = span > 0 ? Math.min(1, Math.max(0, (y - from.arrive) / span)) : 1;
                edge += (to.edge - from.edge) * progress;
            }

            marker.style.setProperty('--toc-progress', `${Math.max(0, edge)}px`);
            body.setAttribute('data-marker', '');
        };

        let frame = 0;
        const schedule = (): void => {
            if (frame) return;
            frame = requestAnimationFrame(() => {
                frame = 0;
                update();
            });
        };

        const remeasure = (): void => {
            measure();
            schedule();
        };

        measure();
        update();

        window.addEventListener('scroll', schedule, { passive: true });
        window.addEventListener('resize', remeasure);
        // Images, fonts and code blocks settle after the first measurement and
        // move every heading under it.
        new ResizeObserver(remeasure).observe(document.body);
    }

    private getRootMargin(): `-${number}px 0% ${number}px` {
        const navBarHeight = document.querySelector('header')?.getBoundingClientRect().height || 0;
        // `<summary>` only exists in mobile ToC, so will fall back to 0 in large viewport component.
        const mobileTocHeight = this.querySelector('summary')?.getBoundingClientRect().height || 0;
        /** Start intersections at nav height + 2rem padding. */
        const top = navBarHeight + mobileTocHeight + 32;
        /** End intersections `53px` later. This is slightly more than the maximum `margin-top` in Markdown content. */
        const bottom = top + 53;
        const height = document.documentElement.clientHeight;
        return `-${top}px 0% ${bottom - height}px`;
    }
}

customElements.define('starlight-toc', StarlightTOC);
