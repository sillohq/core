// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PAGE_TITLE_ID } from '../../packages/lucode-starlight/core/config/constants';

type MockObserverInstance = {
    callback: IntersectionObserverCallback;
    observed: Element[];
    disconnect: ReturnType<typeof vi.fn>;
    options: IntersectionObserverInit | undefined;
};

let idleCallbacks: IdleRequestCallback[] = [];
let observer: MockObserverInstance;
let observers: MockObserverInstance[] = [];

const flushIdleCallbacks = () => {
    const callbacks = [...idleCallbacks];
    idleCallbacks = [];

    const idleDeadline = {
        didTimeout: false,
        timeRemaining: () => 1,
    } as IdleDeadline;

    for (const callback of callbacks) {
        callback(idleDeadline);
    }
};

beforeEach(() => {
    document.body.innerHTML = '';
    idleCallbacks = [];
    observers = [];
    vi.useFakeTimers();

    Object.defineProperty(document.documentElement, 'clientHeight', {
        configurable: true,
        value: 900,
    });

    vi.stubGlobal('requestIdleCallback', (callback: IdleRequestCallback) => {
        idleCallbacks.push(callback);
        return 1 as never;
    });

    class MockIntersectionObserver {
        callback: IntersectionObserverCallback;
        observed: Element[] = [];
        disconnect = vi.fn();
        options: IntersectionObserverInit | undefined;

        constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {
            this.callback = callback;
            this.options = options;
            observer = this;
            observers.push(this);
        }

        observe(element: Element) {
            this.observed.push(element);
        }
    }

    vi.stubGlobal('IntersectionObserver', MockIntersectionObserver as never);
});

afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
});

describe('StarlightTOC', () => {
    it('tracks the intersecting heading link', async () => {
        if (!customElements.get('starlight-toc')) {
            await import('../../packages/lucode-starlight/components/overrides/parts/toc/starlight-toc');
        }

        const header = document.createElement('header');
        Object.defineProperty(header, 'getBoundingClientRect', {
            value: () => ({ height: 64 }),
        });
        document.body.appendChild(header);

        const main = document.createElement('main');
        main.innerHTML = `
            <div class="content">
                <h1 id="${PAGE_TITLE_ID}">Overview</h1>
                <h2 id="section">Section</h2>
                <p id="copy">Body copy</p>
            </div>
        `;
        document.body.appendChild(main);

        const toc = document.createElement('starlight-toc');
        toc.setAttribute('data-min-h', '1');
        toc.setAttribute('data-max-h', '2');
        toc.innerHTML = `
            <summary>On this page</summary>
            <a href="#${PAGE_TITLE_ID}">Overview</a>
            <a href="#section">Section</a>
        `;

        const summary = toc.querySelector('summary');
        Object.defineProperty(summary, 'getBoundingClientRect', {
            value: () => ({ height: 20 }),
        });

        document.body.appendChild(toc);

        flushIdleCallbacks();

        expect(observer.options?.rootMargin).toBe('-116px 0% -731px');
        expect(observer.observed.length).toBeGreaterThan(0);

        const sectionHeading = main.querySelector('#section');
        observer.callback(
            [
                {
                    isIntersecting: true,
                    target: sectionHeading,
                } as IntersectionObserverEntry,
            ],
            {} as IntersectionObserver
        );

        const currentLink = toc.querySelector('a[href="#section"]');
        expect(currentLink?.getAttribute('aria-current')).toBe('true');
    });

    it('resolves nested content back to the nearest heading and re-observes on resize', async () => {
        if (!customElements.get('starlight-toc')) {
            await import('../../packages/lucode-starlight/components/overrides/parts/toc/starlight-toc');
        }

        const header = document.createElement('header');
        Object.defineProperty(header, 'getBoundingClientRect', {
            value: () => ({ height: 32 }),
        });
        document.body.appendChild(header);

        const main = document.createElement('main');
        main.innerHTML = `
            <div class="content">
                <h1 id="${PAGE_TITLE_ID}">Overview</h1>
                <div>
                    <div>
                        <h2 id="section">Section</h2>
                    </div>
                </div>
                <p id="after-heading">Body copy</p>
            </div>
        `;
        document.body.appendChild(main);

        const toc = document.createElement('starlight-toc');
        toc.innerHTML = `
            <a href="#${PAGE_TITLE_ID}" aria-current="true">Overview</a>
            <a href="#section">Section</a>
        `;
        document.body.appendChild(toc);

        flushIdleCallbacks();

        const pageTitle = main.querySelector(`#${PAGE_TITLE_ID}`);
        const afterHeading = main.querySelector('#after-heading');
        observer.callback(
            [
                {
                    isIntersecting: true,
                    target: pageTitle,
                } as IntersectionObserverEntry,
            ],
            {} as IntersectionObserver
        );

        observer.callback(
            [
                {
                    isIntersecting: false,
                    target: afterHeading,
                } as IntersectionObserverEntry,
                {
                    isIntersecting: true,
                    target: afterHeading,
                } as IntersectionObserverEntry,
            ],
            {} as IntersectionObserver
        );

        const topLink = toc.querySelector(`a[href="#${PAGE_TITLE_ID}"]`);
        const sectionLink = toc.querySelector('a[href="#section"]');

        expect(topLink?.hasAttribute('aria-current')).toBe(false);
        expect(sectionLink?.getAttribute('aria-current')).toBe('true');

        window.dispatchEvent(new Event('resize'));

        const firstObserver = observers[0];
        if (!firstObserver) {
            throw new Error('Expected the initial observer to exist.');
        }

        expect(firstObserver.disconnect).toHaveBeenCalledTimes(1);

        const observerCountBeforeReobserve = observers.length;

        vi.advanceTimersByTime(200);

        flushIdleCallbacks();

        expect(observers.length).toBeGreaterThan(observerCountBeforeReobserve);
    });

    it('falls back to a timeout when requestIdleCallback is unavailable', async () => {
        if (!customElements.get('starlight-toc')) {
            await import('../../packages/lucode-starlight/components/overrides/parts/toc/starlight-toc');
        }

        vi.stubGlobal('requestIdleCallback', undefined as never);

        const main = document.createElement('main');
        main.innerHTML = `
            <div class="content">
                <h2 id="section">Section</h2>
            </div>
        `;
        document.body.appendChild(main);

        const toc = document.createElement('starlight-toc');
        toc.innerHTML = '<a href="#section">Section</a>';
        document.body.appendChild(toc);

        expect(observers).toHaveLength(0);

        vi.advanceTimersByTime(1);

        expect(observers.length).toBeGreaterThan(0);
    });

    it('walks back up parent elements to find the nearest heading', async () => {
        if (!customElements.get('starlight-toc')) {
            await import('../../packages/lucode-starlight/components/overrides/parts/toc/starlight-toc');
        }

        const main = document.createElement('main');
        main.innerHTML = `
            <div class="content">
                <h2 id="section">Section</h2>
                <div>
                    <div>
                        <p id="nested-copy">Nested copy</p>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(main);

        const toc = document.createElement('starlight-toc');
        toc.innerHTML = '<a href="#section">Section</a>';
        document.body.appendChild(toc);

        flushIdleCallbacks();

        const nestedCopy = main.querySelector('#nested-copy');
        observer.callback(
            [
                {
                    isIntersecting: true,
                    target: nestedCopy,
                } as IntersectionObserverEntry,
            ],
            {} as IntersectionObserver
        );

        const sectionLink = toc.querySelector('a[href="#section"]');
        expect(sectionLink?.getAttribute('aria-current')).toBe('true');
    });
});
