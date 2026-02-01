const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();

  // Test against the actual running server
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });

  await page.goto('http://localhost:31415');
  await page.waitForSelector('.file-item');

  // Double-click first workflow to open editor
  await page.locator('.file-item').first().dblclick();
  await page.waitForTimeout(1000);

  // Check document dimensions
  const dims = await page.evaluate(() => {
    const root = document.getElementById('root');
    const body = document.body;
    const html = document.documentElement;

    // Get computed styles
    const bodyStyle = window.getComputedStyle(body);
    const htmlStyle = window.getComputedStyle(html);
    const rootStyle = root ? window.getComputedStyle(root) : null;

    return {
      viewport: { width: window.innerWidth, height: window.innerHeight },
      html: {
        scrollHeight: html.scrollHeight,
        clientHeight: html.clientHeight,
        offsetHeight: html.offsetHeight,
        overflow: htmlStyle.overflow,
        overflowY: htmlStyle.overflowY,
      },
      body: {
        scrollHeight: body.scrollHeight,
        clientHeight: body.clientHeight,
        offsetHeight: body.offsetHeight,
        overflow: bodyStyle.overflow,
        overflowY: bodyStyle.overflowY,
      },
      root: root ? {
        scrollHeight: root.scrollHeight,
        clientHeight: root.clientHeight,
        offsetHeight: root.offsetHeight,
        overflow: rootStyle.overflow,
        overflowY: rootStyle.overflowY,
      } : null,
      hasScrollbar: html.scrollHeight > html.clientHeight,
    };
  });

  console.log('=== Document Dimensions ===');
  console.log('Viewport:', dims.viewport);
  console.log('HTML:', dims.html);
  console.log('Body:', dims.body);
  console.log('Root:', dims.root);
  console.log('Has scrollbar:', dims.hasScrollbar);

  // Check key element heights
  const elements = await page.evaluate(() => {
    const getBox = (selector) => {
      const el = document.querySelector(selector);
      if (!el) return null;
      const rect = el.getBoundingClientRect();
      return {
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
        bottom: rect.bottom,
      };
    };
    return {
      editorHeader: getBox('[data-testid="editor-header"]'),
      editor: getBox('[data-testid="editor"]'),
      sidebar: getBox('.sidebar'),
      chatPanel: getBox('.chat-panel'),
      dashboardWithChat: getBox('.dashboard-with-chat'),
      dashboardMain: getBox('.dashboard-main'),
    };
  });

  console.log('\n=== Element Boxes ===');
  for (const [name, box] of Object.entries(elements)) {
    if (box) {
      console.log(`${name}: y=${box.y}, height=${box.height}, bottom=${box.bottom}`);
    }
  }

  await page.screenshot({ path: '/tmp/editor-view.png' });
  console.log('\nScreenshot saved to /tmp/editor-view.png');

  await browser.close();
})();
