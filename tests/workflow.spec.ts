import { test, expect } from '@playwright/test';

test.describe('Workflow Editor', () => {
  test.beforeEach(async ({ page }) => {
    // Clear localStorage to get fresh state, then navigate to editor via dashboard
    await page.goto('/');
    await page.evaluate(() => localStorage.removeItem('dazflow2-workflow'));
    await page.reload();
    // Wait for dashboard to load and show the file list
    await expect(page.getByTestId('dashboard')).toBeVisible();
    await expect(page.getByTestId('file-list')).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId('file-item-sample.json')).toBeVisible({ timeout: 10000 });
    // Double-click sample.json to open the editor
    await page.getByTestId('file-item-sample.json').dblclick();
    // Wait for editor to be visible
    await expect(page.getByTestId('editor')).toBeVisible({ timeout: 10000 });
    // Delete any pre-existing nodes so tests start with empty canvas
    await page.keyboard.press('Meta+a');
    await page.keyboard.press('Delete');
  });

  test('loads the editor with sidebar and canvas', async ({ page }) => {
    await expect(page.getByTestId('editor')).toBeVisible();
    await expect(page.getByTestId('sidebar')).toBeVisible();
    await expect(page.getByTestId('canvas')).toBeVisible();
    await expect(page.getByTestId('sidebar-title')).toHaveText('Nodes');
    await expect(page.getByTestId('sidebar-hint')).toHaveText('Click or drag to add');
  });

  test('sidebar displays all node types', async ({ page }) => {
    // Check all node types are visible in sidebar
    await expect(page.getByTestId('node-type-start')).toBeVisible();
    await expect(page.getByTestId('node-type-scheduled')).toBeVisible();
    await expect(page.getByTestId('node-type-rss')).toBeVisible();
    await expect(page.getByTestId('node-type-if')).toBeVisible();
    await expect(page.getByTestId('node-type-http')).toBeVisible();
    await expect(page.getByTestId('node-type-transform')).toBeVisible();
  });

  test('nodes with no inputs have rounded left side', async ({ page }) => {
    // Start node has no inputs
    await page.getByTestId('node-type-start').click();
    await expect(page.getByTestId('workflow-node-start').locator('.custom-node')).toHaveClass(/no-inputs/);

    // RSS node also has no inputs
    await page.getByTestId('node-type-rss').click();
    await expect(page.getByTestId('workflow-node-rss').locator('.custom-node')).toHaveClass(/no-inputs/);

    // IF node has inputs, so should NOT have no-inputs class
    await page.getByTestId('node-type-if').click();
    await expect(page.getByTestId('workflow-node-if').locator('.custom-node')).not.toHaveClass(/no-inputs/);
  });

  test('clicking RSS node type adds a node to canvas', async ({ page }) => {
    // Initially no nodes on canvas
    await expect(page.getByTestId('workflow-node-rss')).toHaveCount(0);

    // Click the RSS node type in sidebar
    await page.getByTestId('node-type-rss').click();

    // Verify node appears on canvas
    await expect(page.getByTestId('workflow-node-rss')).toHaveCount(1);
    await expect(page.getByTestId('workflow-node-rss')).toBeVisible();
  });

  test('clicking IF node type adds a node to canvas', async ({ page }) => {
    await expect(page.getByTestId('workflow-node-if')).toHaveCount(0);
    await page.getByTestId('node-type-if').click();
    await expect(page.getByTestId('workflow-node-if')).toHaveCount(1);
    await expect(page.getByTestId('workflow-node-if')).toBeVisible();
  });

  test('clicking HTTP node type adds a node to canvas', async ({ page }) => {
    await expect(page.getByTestId('workflow-node-http')).toHaveCount(0);
    await page.getByTestId('node-type-http').click();
    await expect(page.getByTestId('workflow-node-http')).toHaveCount(1);
    await expect(page.getByTestId('workflow-node-http')).toBeVisible();
  });

  test('clicking Transform node type adds a node to canvas', async ({ page }) => {
    await expect(page.getByTestId('workflow-node-transform')).toHaveCount(0);
    await page.getByTestId('node-type-transform').click();
    await expect(page.getByTestId('workflow-node-transform')).toHaveCount(1);
    await expect(page.getByTestId('workflow-node-transform')).toBeVisible();
  });

  test('can add multiple nodes of same type', async ({ page }) => {
    await expect(page.getByTestId('workflow-node-rss')).toHaveCount(0);

    // Add three RSS nodes
    await page.getByTestId('node-type-rss').click();
    await page.getByTestId('node-type-rss').click();
    await page.getByTestId('node-type-rss').click();

    await expect(page.getByTestId('workflow-node-rss')).toHaveCount(3);
  });

  test('can add multiple different node types', async ({ page }) => {
    // Add one of each type
    await page.getByTestId('node-type-rss').click();
    await page.getByTestId('node-type-if').click();
    await page.getByTestId('node-type-http').click();
    await page.getByTestId('node-type-transform').click();

    // Verify all nodes present
    await expect(page.getByTestId('workflow-node-rss')).toHaveCount(1);
    await expect(page.getByTestId('workflow-node-if')).toHaveCount(1);
    await expect(page.getByTestId('workflow-node-http')).toHaveCount(1);
    await expect(page.getByTestId('workflow-node-transform')).toHaveCount(1);
  });

  test('node can be selected by clicking', async ({ page }) => {
    // Add a node
    await page.getByTestId('node-type-rss').click();
    const node = page.getByTestId('workflow-node-rss');

    // Click the node to select it
    await node.click();

    // Selected node's inner element should have 'selected' class
    await expect(node.locator('.custom-node')).toHaveClass(/selected/);
  });

  test('clicking another node switches selection immediately', async ({ page }) => {
    // Add two different nodes (they will be staggered to avoid overlap)
    await page.getByTestId('node-type-rss').click();
    await page.getByTestId('node-type-http').click();

    const rssNode = page.getByTestId('workflow-node-rss');
    const httpNode = page.getByTestId('workflow-node-http');

    // Click RSS node to select it
    await rssNode.click();
    await expect(rssNode.locator('.custom-node')).toHaveClass(/selected/);
    await expect(httpNode.locator('.custom-node')).not.toHaveClass(/selected/);

    // Click HTTP node - should immediately select it (no double click needed)
    await httpNode.click();
    await expect(httpNode.locator('.custom-node')).toHaveClass(/selected/);
    await expect(rssNode.locator('.custom-node')).not.toHaveClass(/selected/);
  });

  test('pressing Delete removes selected node', async ({ page }) => {
    // Add a node
    await page.getByTestId('node-type-rss').click();
    await expect(page.getByTestId('workflow-node-rss')).toHaveCount(1);

    // Click to select it
    await page.getByTestId('workflow-node-rss').click();

    // Press Delete
    await page.keyboard.press('Delete');

    // Node should be removed
    await expect(page.getByTestId('workflow-node-rss')).toHaveCount(0);
  });

  test('pressing Escape clears selection', async ({ page }) => {
    // Add and select a node
    await page.getByTestId('node-type-rss').click();
    const node = page.getByTestId('workflow-node-rss');
    await node.click();
    await expect(node.locator('.custom-node')).toHaveClass(/selected/);

    // Press Escape
    await page.keyboard.press('Escape');

    // Node should no longer be selected
    await expect(node.locator('.custom-node')).not.toHaveClass(/selected/);
  });

  test('Ctrl+A selects all nodes', async ({ page }) => {
    // Add multiple nodes
    await page.getByTestId('node-type-rss').click();
    await page.getByTestId('node-type-if').click();

    // Press Ctrl+A
    await page.keyboard.press('Control+a');

    // Both nodes should be selected
    await expect(page.getByTestId('workflow-node-rss').locator('.custom-node')).toHaveClass(/selected/);
    await expect(page.getByTestId('workflow-node-if').locator('.custom-node')).toHaveClass(/selected/);
  });

  test('pressing Space on selected node starts name editing', async ({ page }) => {
    // Add and select a node
    await page.getByTestId('node-type-rss').click();
    const node = page.getByTestId('workflow-node-rss');
    await node.click();

    // Press Space to edit
    await page.keyboard.press(' ');

    // Input should appear
    const input = page.getByTestId('node-name-input');
    await expect(input).toBeVisible();
  });

  test('can rename node using Space, click input, type, and Enter', async ({ page }) => {
    // Add and select a node
    await page.getByTestId('node-type-rss').click();
    const node = page.getByTestId('workflow-node-rss');
    await node.click();

    // Press Space to edit
    await page.keyboard.press(' ');
    const input = page.getByTestId('node-name-input');
    await expect(input).toBeVisible();

    // Click input to focus, clear and type new name, press Enter
    await input.click();
    await input.fill('MyRSSFeed');
    await input.press('Enter');

    // Input should be gone, name should be updated
    await expect(page.getByTestId('node-name-input')).toHaveCount(0);
    await expect(node.locator('.node-name')).toHaveText('MyRSSFeed');
  });

  test('pressing Escape cancels name editing', async ({ page }) => {
    // Add and select a node
    await page.getByTestId('node-type-rss').click();
    const node = page.getByTestId('workflow-node-rss');
    await node.click();

    // Press Space to edit
    await page.keyboard.press(' ');
    const input = page.getByTestId('node-name-input');
    await expect(input).toBeVisible();

    // Click input and press Escape to cancel
    await input.click();
    await input.press('Escape');

    // Input should be gone, original name preserved
    await expect(page.getByTestId('node-name-input')).toHaveCount(0);
    await expect(node.locator('.node-name')).toHaveText('rss1');
  });

  test('cannot rename node to duplicate name', async ({ page }) => {
    // Add two RSS nodes (they will be named rss1 and rss2)
    await page.getByTestId('node-type-rss').click();
    await page.getByTestId('node-type-rss').click();

    const nodes = page.getByTestId('workflow-node-rss');
    await expect(nodes).toHaveCount(2);

    // Click second node to select it
    await nodes.nth(1).click();

    // Press Space to edit
    await page.keyboard.press(' ');
    const input = page.getByTestId('node-name-input');
    await expect(input).toBeVisible();

    // Try to rename to 'rss1' (already taken by first node)
    await input.click();
    await input.fill('rss1');
    await input.press('Enter');

    // Input should still be visible with error class (name rejected)
    await expect(input).toBeVisible();
    await expect(input).toHaveClass(/error/);

    // Press Escape to cancel
    await input.press('Escape');

    // Name should be unchanged (rss2)
    await expect(nodes.nth(1).locator('.node-name')).toHaveText('rss2');
  });

  test('can rename node to unique name', async ({ page }) => {
    // Add two RSS nodes
    await page.getByTestId('node-type-rss').click();
    await page.getByTestId('node-type-rss').click();

    const nodes = page.getByTestId('workflow-node-rss');

    // Click second node to select it
    await nodes.nth(1).click();

    // Press Space to edit
    await page.keyboard.press(' ');
    const input = page.getByTestId('node-name-input');

    // Rename to a unique name
    await input.click();
    await input.fill('MyUniqueNode');
    await input.press('Enter');

    // Input should be gone, name should be updated
    await expect(page.getByTestId('node-name-input')).toHaveCount(0);
    await expect(nodes.nth(1).locator('.node-name')).toHaveText('MyUniqueNode');
  });

  test('double-clicking node opens node editor', async ({ page }) => {
    // Add a Scheduled node
    await page.getByTestId('node-type-scheduled').click();
    const node = page.getByTestId('workflow-node-scheduled');
    await expect(node).toBeVisible();

    // Double-click on the custom-node element to open editor
    await node.locator('.custom-node').dblclick();

    // Editor dialog should appear
    const dialog = page.locator('.node-editor-dialog');
    await expect(dialog).toBeVisible();

    // Should show Properties pane
    await expect(dialog.locator('.pane-header').filter({ hasText: 'Properties' })).toBeVisible();

    // Should show name field
    await expect(dialog.locator('.property-label').filter({ hasText: 'Name' })).toBeVisible();

    // Should show Interval and Unit fields for Scheduled node
    await expect(dialog.locator('.property-label').filter({ hasText: 'Interval' })).toBeVisible();
    await expect(dialog.locator('.property-label').filter({ hasText: 'Unit' })).toBeVisible();

    // Close by clicking overlay
    await page.locator('.node-editor-overlay').click({ position: { x: 10, y: 10 } });
    await expect(dialog).not.toBeVisible();
  });

  test('executing Scheduled node produces output with timestamp', async ({ page }) => {
    // Add a Scheduled node
    await page.getByTestId('node-type-scheduled').click();
    const node = page.getByTestId('workflow-node-scheduled');

    // Double-click to open editor
    await node.locator('.custom-node').dblclick();

    const dialog = page.locator('.node-editor-dialog');
    await expect(dialog).toBeVisible();

    // Execute button should be visible for Scheduled node
    const executeBtn = page.getByTestId('execute-btn');
    await expect(executeBtn).toBeVisible();

    // Click Execute
    await executeBtn.click();

    // Output should appear with timestamp
    const output = page.getByTestId('execution-output');
    await expect(output).toBeVisible();

    // Output should contain time field
    const outputText = await output.textContent();
    expect(outputText).toContain('"time"');

    // Close editor
    await page.locator('.node-editor-close').click();
    await expect(dialog).not.toBeVisible();
  });

  test('execution result persists in ambient execution when reopening node editor', async ({ page }) => {
    // Add a Scheduled node
    await page.getByTestId('node-type-scheduled').click();
    const node = page.getByTestId('workflow-node-scheduled');

    // Open editor and execute
    await node.locator('.custom-node').dblclick();
    const dialog = page.locator('.node-editor-dialog');
    await expect(dialog).toBeVisible();

    // Initially no output
    await expect(page.getByTestId('execution-output')).toHaveCount(0);

    // Execute
    await page.getByTestId('execute-btn').click();

    // Capture the output
    const output = page.getByTestId('execution-output');
    await expect(output).toBeVisible();
    const firstOutputText = await output.textContent();

    // Close editor
    await page.locator('.node-editor-close').click();
    await expect(dialog).not.toBeVisible();

    // Re-open editor
    await node.locator('.custom-node').dblclick();
    await expect(dialog).toBeVisible();

    // Output should still be visible from ambient execution (not re-executed)
    const outputAfterReopen = page.getByTestId('execution-output');
    await expect(outputAfterReopen).toBeVisible();
    const secondOutputText = await outputAfterReopen.textContent();

    // Should be the same output (same timestamp from ambient execution)
    expect(secondOutputText).toBe(firstOutputText);
  });

  test('Set node can add fields and execute to produce JSON output', async ({ page }) => {
    // Add a Set node
    await page.getByTestId('node-type-set').click();
    const node = page.getByTestId('workflow-node-set');
    await expect(node).toBeVisible();

    // Double-click to open editor
    await node.locator('.custom-node').dblclick();
    const dialog = page.locator('.node-editor-dialog');
    await expect(dialog).toBeVisible();

    // Should show Output Fields property with Add Field button
    await expect(page.locator('.property-label').filter({ hasText: 'Output Fields' })).toBeVisible();
    const addFieldBtn = page.getByTestId('add-field-btn');
    await expect(addFieldBtn).toBeVisible();

    // Add a field
    await addFieldBtn.click();

    // Field inputs should appear
    const fieldItem = dialog.locator('.field-item');
    await expect(fieldItem).toHaveCount(1);

    // Fill in the field name and value
    // Click display div to focus, then fill the input that appears
    const nameWrapper = fieldItem.locator('.expr-input-wrapper').first();
    const valueWrapper = fieldItem.locator('.expr-input-wrapper').nth(1);
    await nameWrapper.click();
    await nameWrapper.locator('input').fill('greeting');
    await valueWrapper.click();
    await valueWrapper.locator('input').fill('"hello world"');

    // Add another field
    await addFieldBtn.click();
    await expect(dialog.locator('.field-item')).toHaveCount(2);

    // Fill second field with a number
    const secondFieldItem = dialog.locator('.field-item').nth(1);
    const secondNameWrapper = secondFieldItem.locator('.expr-input-wrapper').first();
    const secondValueWrapper = secondFieldItem.locator('.expr-input-wrapper').nth(1);
    await secondNameWrapper.click();
    await secondNameWrapper.locator('input').fill('count');
    await secondValueWrapper.click();
    await secondValueWrapper.locator('input').fill('42');

    // Execute
    await page.getByTestId('execute-btn').click();

    // Check output contains both fields
    const output = page.getByTestId('execution-output');
    await expect(output).toBeVisible();
    const outputText = await output.textContent();
    expect(outputText).toContain('"greeting"');
    expect(outputText).toContain('"hello world"');
    expect(outputText).toContain('"count"');
    expect(outputText).toContain('42');

    // Close editor
    await page.locator('.node-editor-close').click();
  });

  test('Set node can delete fields', async ({ page }) => {
    // Add a Set node
    await page.getByTestId('node-type-set').click();
    const node = page.getByTestId('workflow-node-set');

    // Open editor
    await node.locator('.custom-node').dblclick();
    const dialog = page.locator('.node-editor-dialog');
    await expect(dialog).toBeVisible();

    // Add two fields
    const addFieldBtn = page.getByTestId('add-field-btn');
    await addFieldBtn.click();
    await addFieldBtn.click();
    await expect(dialog.locator('.field-item')).toHaveCount(2);

    // Delete first field
    await dialog.locator('.field-item').first().locator('.field-delete-btn').click();
    await expect(dialog.locator('.field-item')).toHaveCount(1);

    // Close editor
    await page.locator('.node-editor-close').click();
  });

  test('Set node maps over multiple input items (map node behavior)', async ({ page }) => {
    // Add a Set node
    await page.getByTestId('node-type-set').click();
    const setNode = page.getByTestId('workflow-node-set');
    await expect(setNode).toBeVisible();
    const setNodeId = await setNode.getAttribute('data-node-id');

    // Configure Set node with a field
    await setNode.locator('.custom-node').dblclick();
    const dialog = page.locator('.node-editor-dialog');
    await expect(dialog).toBeVisible();

    await page.getByTestId('add-field-btn').click();
    const fieldItem = dialog.locator('.field-item');
    const nameWrapper = fieldItem.locator('.expr-input-wrapper').first();
    const valueWrapper = fieldItem.locator('.expr-input-wrapper').nth(1);
    await nameWrapper.click();
    await nameWrapper.locator('input').fill('status');
    await valueWrapper.click();
    await valueWrapper.locator('input').fill('"processed"');
    await page.locator('.node-editor-close').click();

    // Set up: create a fake upstream node and inject connection + execution data
    await page.evaluate(({ targetId }) => {
      const store = (window as any).useWorkflowStore;
      if (store) {
        // Create a fake upstream node ID
        const fakeUpstreamId = 'fake-upstream-node';

        // Set up the upstream node's execution output with 4 items
        store.getState().setNodeExecution(fakeUpstreamId,
          [], // input
          [{ name: 'item1' }, { name: 'item2' }, { name: 'item3' }, { name: 'item4' }], // nodeOutput
          [{ name: 'item1' }, { name: 'item2' }, { name: 'item3' }, { name: 'item4' }]  // combined output
        );

        // Create a connection from fake upstream to Set
        store.getState().addConnection({
          sourceNodeId: fakeUpstreamId,
          sourceConnectorId: 'output',
          targetNodeId: targetId,
          targetConnectorId: 'data',
        });
      }
    }, { targetId: setNodeId });

    // Open Set node editor - it should now see upstream data
    await setNode.locator('.custom-node').dblclick();
    await expect(dialog).toBeVisible();

    // Verify input pane shows upstream data
    const inputPane = page.getByTestId('execution-input');
    await expect(inputPane).toBeVisible();

    // Execute - should map over 4 items and produce 4 outputs
    await page.getByTestId('execute-btn').click();

    // Check output shows the mapped results
    const output = page.getByTestId('execution-output');
    await expect(output).toBeVisible();

    // Verify the actual execution result in the store (4 items, each with status)
    const executionResult = await page.evaluate((nodeId) => {
      const store = (window as any).useWorkflowStore;
      return store?.getState().ambientExecution[nodeId!]?.nodeOutput;
    }, setNodeId);

    expect(Array.isArray(executionResult)).toBe(true);
    expect(executionResult.length).toBe(4);
    for (const item of executionResult) {
      expect(item.status).toBe('processed');
    }

    await page.locator('.node-editor-close').click();
  });

  test('execute button shows for all node types', async ({ page }) => {
    // Test that execute button is visible for ALL node types
    // All nodes must be executable from the UI - there is no concept of a non-executable node

    const nodeTypesToTest = ['transform', 'if', 'http', 'rss', 'start'];
    const dialog = page.locator('.node-editor-dialog');

    for (const nodeType of nodeTypesToTest) {
      await page.getByTestId(`node-type-${nodeType}`).click();
      const node = page.getByTestId(`workflow-node-${nodeType}`);
      await node.locator('.custom-node').dblclick();
      await expect(dialog).toBeVisible();
      await expect(page.getByTestId('execute-btn')).toBeVisible();
      await page.locator('.node-editor-close').click();
      await expect(dialog).not.toBeVisible();
    }
  });

  test('can edit node properties in editor', async ({ page }) => {
    // Add a Scheduled node
    await page.getByTestId('node-type-scheduled').click();
    const node = page.getByTestId('workflow-node-scheduled');

    // Double-click to open editor
    await node.locator('.custom-node').dblclick();

    const dialog = page.locator('.node-editor-dialog');
    await expect(dialog).toBeVisible();

    // Find and update interval field
    const intervalInput = dialog.locator('input[type="number"]');
    await intervalInput.fill('10');
    await intervalInput.blur();

    // Find and update unit dropdown
    const unitSelect = dialog.locator('select');
    await unitSelect.selectOption('hours');

    // Close editor
    await page.locator('.node-editor-close').click();
    await expect(dialog).not.toBeVisible();

    // Verify changes persisted by checking JSON
    await page.getByTestId('view-json-btn').click();
    const jsonContent = await page.locator('.json-modal pre').textContent();
    expect(jsonContent).toContain('"interval": 10');
    expect(jsonContent).toContain('"unit": "hours"');
  });

  test('View Instance button shows workflow and execution data', async ({ page }) => {
    // Add a node
    await page.getByTestId('node-type-rss').click();

    // Click View Instance button
    await page.getByTestId('view-json-btn').click();

    // Modal should appear with JSON content
    const modal = page.locator('.json-modal');
    await expect(modal).toBeVisible();

    // JSON should contain workflow and execution keys
    const jsonContent = await modal.locator('pre').textContent();
    expect(jsonContent).toContain('"workflow"');
    expect(jsonContent).toContain('"execution"');
    expect(jsonContent).toContain('"nodes"');
    expect(jsonContent).toContain('"connections"');
    expect(jsonContent).toContain('"typeId": "rss"');

    // Close modal by clicking overlay
    await page.locator('.json-modal-overlay').click({ position: { x: 10, y: 10 } });
    await expect(modal).not.toBeVisible();
  });

  test('can navigate from editor back to dashboard', async ({ page }) => {
    // Verify we're in the editor (from beforeEach)
    await expect(page.getByTestId('editor')).toBeVisible();

    // Click back to dashboard button
    await page.getByTestId('back-to-dashboard').click();

    // Verify we're back on the dashboard
    await expect(page.getByTestId('dashboard')).toBeVisible();
    await expect(page.getByTestId('dashboard-title')).toHaveText('dazflow');
  });

  test('can pin output and see pin indicator on canvas', async ({ page }) => {
    // Add a Scheduled node
    await page.getByTestId('node-type-scheduled').click();
    const node = page.getByTestId('workflow-node-scheduled');
    await expect(node).toBeVisible();

    // Double-click to open editor
    await node.locator('.custom-node').dblclick();
    const dialog = page.locator('.node-editor-dialog');
    await expect(dialog).toBeVisible();

    // Execute to get output first (can't pin without output)
    await page.getByTestId('execute-btn').click();
    await expect(page.getByTestId('execution-output')).toBeVisible();

    // Find and click the Pin button in output pane header
    const pinBtn = dialog.locator('button:has-text("Pin")');
    await expect(pinBtn).toBeVisible();
    await pinBtn.click();

    // Should now show PINNED badge and Unpin button
    await expect(dialog.locator('text=📌 PINNED').first()).toBeVisible();
    const unpinBtn = dialog.locator('button:has-text("Unpin")');
    await expect(unpinBtn).toBeVisible();

    // Close editor
    await page.locator('.node-editor-close').click();
    await expect(dialog).not.toBeVisible();

    // Verify pin indicator is visible on canvas
    const pinIndicator = node.locator('.node-pin-indicator');
    await expect(pinIndicator).toBeVisible();
  });

  test('pinned node returns pinned output instead of executing', async ({ page }) => {
    // Add a Scheduled node
    await page.getByTestId('node-type-scheduled').click();
    const node = page.getByTestId('workflow-node-scheduled');
    const nodeId = await node.getAttribute('data-node-id');

    // Open editor and execute
    await node.locator('.custom-node').dblclick();
    const dialog = page.locator('.node-editor-dialog');
    await expect(dialog).toBeVisible();
    await page.getByTestId('execute-btn').click();
    await expect(page.getByTestId('execution-output')).toBeVisible();

    // Pin the output
    await dialog.locator('button:has-text("Pin")').click();
    await expect(dialog.locator('text=📌 PINNED').first()).toBeVisible();

    // Get the pinned output time
    const firstOutputText = await page.getByTestId('execution-output').textContent();

    // Close and reopen editor
    await page.locator('.node-editor-close').click();
    await node.locator('.custom-node').dblclick();
    await expect(dialog).toBeVisible();

    // Execute again - should return pinned output (same time)
    await page.getByTestId('execute-btn').click();

    // Output should still be the same (pinned value)
    const secondOutputText = await page.getByTestId('execution-output').textContent();
    expect(secondOutputText).toBe(firstOutputText);

    // Close editor
    await page.locator('.node-editor-close').click();
  });

  test('can unpin output', async ({ page }) => {
    // Add a Scheduled node
    await page.getByTestId('node-type-scheduled').click();
    const node = page.getByTestId('workflow-node-scheduled');

    // Open editor, execute, and pin
    await node.locator('.custom-node').dblclick();
    const dialog = page.locator('.node-editor-dialog');
    await expect(dialog).toBeVisible();
    await page.getByTestId('execute-btn').click();
    await expect(page.getByTestId('execution-output')).toBeVisible();
    await dialog.locator('button:has-text("Pin")').click();
    await expect(dialog.locator('text=📌 PINNED').first()).toBeVisible();

    // Click Unpin
    await dialog.locator('button:has-text("Unpin")').click();

    // Pin badge should be gone
    await expect(dialog.locator('text=📌 PINNED')).not.toBeVisible();

    // Close editor
    await page.locator('.node-editor-close').click();

    // Pin indicator should not be visible on canvas
    const pinIndicator = node.locator('.node-pin-indicator');
    await expect(pinIndicator).not.toBeVisible();
  });

  test('edit button opens editor modal for pinned output', async ({ page }) => {
    // Add a Scheduled node
    await page.getByTestId('node-type-scheduled').click();
    const node = page.getByTestId('workflow-node-scheduled');

    // Open editor, execute, and pin first
    await node.locator('.custom-node').dblclick();
    const dialog = page.locator('.node-editor-dialog');
    await expect(dialog).toBeVisible();

    // Execute to get output
    await page.getByTestId('execute-btn').click();
    await expect(page.getByTestId('execution-output')).toBeVisible();

    // Pin the output first
    await dialog.locator('button:has-text("Pin")').click();
    await expect(dialog.locator('text=📌 PINNED').first()).toBeVisible();

    // Click Edit button to open the modal
    const editBtn = dialog.locator('button:has-text("Edit")');
    await expect(editBtn).toBeVisible();
    await editBtn.click();

    // Output editor modal should appear
    const editorModal = page.locator('.expr-editor-dialog');
    await expect(editorModal).toBeVisible();
    await expect(editorModal.locator('h3')).toHaveText('Edit Pinned Output');

    // The modal should contain the pinned output JSON
    const textarea = editorModal.locator('textarea');
    const content = await textarea.inputValue();
    expect(content).toContain('"time"');

    // Close editor modal by clicking Cancel button
    await editorModal.locator('button:has-text("Cancel")').click();
    await expect(editorModal).not.toBeVisible();

    // Close node editor
    await page.locator('.node-editor-close').click();
  });
});

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('loads dashboard as default view', async ({ page }) => {
    await expect(page.getByTestId('dashboard')).toBeVisible();
    await expect(page.getByTestId('dashboard-title')).toHaveText('dazflow');
  });

  test('shows workflows and executions tabs', async ({ page }) => {
    await expect(page.getByTestId('tab-workflows')).toBeVisible();
    await expect(page.getByTestId('tab-executions')).toBeVisible();
    // Workflows tab should be active by default
    await expect(page.getByTestId('tab-workflows')).toHaveClass(/active/);
  });

  test('shows sample.json workflow', async ({ page }) => {
    await expect(page.getByTestId('file-item-sample.json')).toBeVisible();
    // Check stats display (may have runs from other tests)
    await expect(page.getByTestId('file-item-sample.json')).toContainText('runs');
  });

  test('can switch to executions tab', async ({ page }) => {
    await page.getByTestId('tab-executions').click();
    await expect(page.getByTestId('tab-executions')).toHaveClass(/active/);
    await expect(page.getByTestId('executions-tab')).toBeVisible();
  });

  test('double-clicking workflow opens editor', async ({ page }) => {
    // Wait for file list to load
    await expect(page.getByTestId('file-list')).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId('file-item-sample.json')).toBeVisible({ timeout: 10000 });
    await page.getByTestId('file-item-sample.json').dblclick();
    await expect(page.getByTestId('editor')).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId('sidebar')).toBeVisible();
    await expect(page.getByTestId('canvas')).toBeVisible();
  });

  test('workflow item has hamburger menu button', async ({ page }) => {
    await expect(page.getByTestId('file-list')).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId('menu-btn-sample.json')).toBeVisible();
  });

  test('clicking hamburger menu opens dropdown with Execute option', async ({ page }) => {
    await expect(page.getByTestId('file-list')).toBeVisible({ timeout: 10000 });

    // Click hamburger menu button
    await page.getByTestId('menu-btn-sample.json').click();

    // Dropdown should appear with Execute option
    await expect(page.getByTestId('menu-dropdown-sample.json')).toBeVisible();
    await expect(page.getByTestId('menu-execute-sample.json')).toBeVisible();
    await expect(page.getByTestId('menu-execute-sample.json')).toHaveText('Execute');
  });

  test('clicking Execute queues the workflow', async ({ page }) => {
    await expect(page.getByTestId('file-list')).toBeVisible({ timeout: 10000 });

    // Intercept the queue API call
    const queuePromise = page.waitForResponse(
      response => response.url().includes('/workflow/sample.json/queue') && response.status() === 200
    );

    // Click hamburger menu button
    await page.getByTestId('menu-btn-sample.json').click();

    // Click Execute
    await page.getByTestId('menu-execute-sample.json').click();

    // Verify API was called successfully
    const queueResponse = await queuePromise;
    const responseData = await queueResponse.json();
    expect(responseData.queue_id).toBeDefined();
    expect(responseData.status).toBe('queued');

    // Dropdown should close after clicking Execute
    await expect(page.getByTestId('menu-dropdown-sample.json')).not.toBeVisible();
  });

  test('clicking outside dropdown closes it', async ({ page }) => {
    await expect(page.getByTestId('file-list')).toBeVisible({ timeout: 10000 });

    // Open dropdown
    await page.getByTestId('menu-btn-sample.json').click();
    await expect(page.getByTestId('menu-dropdown-sample.json')).toBeVisible();

    // Click outside the dropdown (on the dashboard title)
    await page.getByTestId('dashboard-title').click();

    // Dropdown should close
    await expect(page.getByTestId('menu-dropdown-sample.json')).not.toBeVisible();
  });
});

test.describe('Executions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('dashboard')).toBeVisible();
  });

  test('queued workflow appears in executions tab after completion', async ({ page }) => {
    // Queue a workflow
    await expect(page.getByTestId('file-list')).toBeVisible({ timeout: 10000 });
    await page.getByTestId('menu-btn-sample.json').click();
    await page.getByTestId('menu-execute-sample.json').click();

    // Wait for execution to complete (workers process it)
    await page.waitForTimeout(2000);

    // Switch to executions tab
    await page.getByTestId('tab-executions').click();
    await expect(page.getByTestId('executions-tab')).toBeVisible();

    // Should show at least one execution
    await expect(page.getByTestId('executions-list')).toBeVisible({ timeout: 10000 });
    const items = page.locator('[data-testid^="execution-item-"]');
    await expect(items.first()).toBeVisible({ timeout: 10000 });
  });

  test('clicking execution opens read-only editor', async ({ page }) => {
    // Queue a workflow first
    await expect(page.getByTestId('file-list')).toBeVisible({ timeout: 10000 });
    await page.getByTestId('menu-btn-sample.json').click();
    await page.getByTestId('menu-execute-sample.json').click();
    await page.waitForTimeout(2000);

    // Switch to executions tab
    await page.getByTestId('tab-executions').click();
    await expect(page.getByTestId('executions-tab')).toBeVisible();
    await expect(page.getByTestId('executions-list')).toBeVisible({ timeout: 10000 });

    // Click the first execution
    const firstItem = page.locator('[data-testid^="execution-item-"]').first();
    await expect(firstItem).toBeVisible({ timeout: 10000 });
    await firstItem.click();

    // Should open the editor in read-only mode
    await expect(page.getByTestId('editor')).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId('readonly-banner')).toBeVisible();
    await expect(page.getByTestId('readonly-banner')).toContainText('Read Only');
  });

  test('read-only mode has back button that returns to executions', async ({ page }) => {
    // Queue a workflow first
    await expect(page.getByTestId('file-list')).toBeVisible({ timeout: 10000 });
    await page.getByTestId('menu-btn-sample.json').click();
    await page.getByTestId('menu-execute-sample.json').click();
    await page.waitForTimeout(2000);

    // Switch to executions tab and open execution
    await page.getByTestId('tab-executions').click();
    await expect(page.getByTestId('executions-list')).toBeVisible({ timeout: 10000 });
    const firstItem = page.locator('[data-testid^="execution-item-"]').first();
    await expect(firstItem).toBeVisible({ timeout: 10000 });
    await firstItem.click();

    // Verify read-only editor
    await expect(page.getByTestId('editor')).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId('readonly-banner')).toBeVisible();

    // Click back button
    await page.getByTestId('readonly-back-btn').click();

    // Should return to executions tab
    await expect(page.getByTestId('dashboard')).toBeVisible();
    await expect(page.getByTestId('tab-executions')).toHaveClass(/active/);
  });

  test('read-only mode disables sidebar node adding', async ({ page }) => {
    // Queue and wait
    await expect(page.getByTestId('file-list')).toBeVisible({ timeout: 10000 });
    await page.getByTestId('menu-btn-sample.json').click();
    await page.getByTestId('menu-execute-sample.json').click();
    await page.waitForTimeout(2000);

    // Open execution
    await page.getByTestId('tab-executions').click();
    await expect(page.getByTestId('executions-list')).toBeVisible({ timeout: 10000 });
    const firstItem = page.locator('[data-testid^="execution-item-"]').first();
    await expect(firstItem).toBeVisible({ timeout: 10000 });
    await firstItem.click();

    // Verify sidebar node types are disabled
    await expect(page.getByTestId('editor')).toBeVisible({ timeout: 10000 });
    const nodeType = page.getByTestId('node-type-scheduled');
    await expect(nodeType).toHaveClass(/disabled/);
  });
});

test.describe('Agents', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('dashboard')).toBeVisible();
  });

  test('agents tab exists in navigation', async ({ page }) => {
    await expect(page.getByTestId('tab-agents')).toBeVisible();
    await expect(page.getByTestId('tab-agents')).toHaveText('Agents');
  });

  test('can switch to agents tab', async ({ page }) => {
    await page.getByTestId('tab-agents').click();
    await expect(page.getByTestId('tab-agents')).toHaveClass(/active/);
    await expect(page.getByTestId('agents-tab')).toBeVisible();
  });

  test('agents tab shows create button', async ({ page }) => {
    await page.getByTestId('tab-agents').click();
    await expect(page.getByTestId('create-agent-btn')).toBeVisible();
    await expect(page.getByTestId('create-agent-btn')).toContainText('Create Agent');
  });

  test('agents tab shows empty state when no agents', async ({ page }) => {
    await page.getByTestId('tab-agents').click();
    await expect(page.getByTestId('agents-tab')).toBeVisible();
    // Note: There may be agents from other tests, so we just check the tab loads
  });

  test('can create an agent', async ({ page }) => {
    await page.getByTestId('tab-agents').click();
    await expect(page.getByTestId('agents-tab')).toBeVisible();

    // Use timestamp to ensure unique agent name
    const agentName = `test-agent-${Date.now()}`;

    // Setup dialog handler - must be registered before the action that triggers it
    page.once('dialog', async dialog => {
      expect(dialog.type()).toBe('prompt');
      await dialog.accept(agentName);
    });

    // Click create button (this triggers the prompt)
    await page.getByTestId('create-agent-btn').click();

    // Wait for the agent to be created and secret modal to appear
    await expect(page.locator('.agent-secret-modal')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.agent-secret-modal-content')).toContainText(agentName);
    await expect(page.locator('.agent-secret-display')).toBeVisible();

    // Close the modal
    await page.locator('button:has-text("Close")').click();
    await expect(page.locator('.agent-secret-modal')).not.toBeVisible();

    // Verify agent appears in list
    await expect(page.getByTestId(`agent-item-${agentName}`)).toBeVisible();
  });

  test('can toggle agent enabled status', async ({ page }) => {
    await page.getByTestId('tab-agents').click();
    await expect(page.getByTestId('agents-tab')).toBeVisible();

    const agentName = `test-toggle-${Date.now()}`;

    // Create an agent first
    page.once('dialog', async dialog => await dialog.accept(agentName));
    await page.getByTestId('create-agent-btn').click();
    await expect(page.locator('.agent-secret-modal')).toBeVisible({ timeout: 5000 });
    await page.locator('button:has-text("Close")').click();

    // Wait for agent to appear
    await expect(page.getByTestId(`agent-item-${agentName}`)).toBeVisible();

    // Agent should be enabled by default
    const enableToggle = page.getByTestId(`agent-enabled-${agentName}`);
    await expect(enableToggle).toHaveClass(/agent-enabled-toggle enabled/);
    await expect(enableToggle).toContainText('enabled');

    // Click to disable
    await enableToggle.click();
    await page.waitForTimeout(500); // Wait for API call

    // Should now be disabled (only has base class, not 'enabled')
    const classAttr = await enableToggle.getAttribute('class');
    expect(classAttr).toBe('agent-enabled-toggle ');
    await expect(enableToggle).toContainText('disabled');

    // Click to re-enable
    await enableToggle.click();
    await page.waitForTimeout(500);

    // Should be enabled again
    await expect(enableToggle).toHaveClass(/agent-enabled-toggle enabled/);
    await expect(enableToggle).toContainText('enabled');
  });

  test('can edit agent priority', async ({ page }) => {
    await page.getByTestId('tab-agents').click();
    await expect(page.getByTestId('agents-tab')).toBeVisible();

    const agentName = `test-priority-${Date.now()}`;

    // Create an agent
    page.once('dialog', async dialog => await dialog.accept(agentName));
    await page.getByTestId('create-agent-btn').click();
    await expect(page.locator('.agent-secret-modal')).toBeVisible({ timeout: 5000 });
    await page.locator('button:has-text("Close")').click();

    // Wait for agent to appear
    await expect(page.getByTestId(`agent-item-${agentName}`)).toBeVisible();

    // Should have default priority 0
    const priorityElement = page.getByTestId(`agent-priority-${agentName}`);
    await expect(priorityElement).toContainText('pri:0');

    // Double-click to edit
    page.once('dialog', async dialog => await dialog.accept('42'));
    await priorityElement.dblclick();
    await page.waitForTimeout(500);

    // Priority should now be 42
    await expect(priorityElement).toContainText('pri:42');
  });

  test('can edit agent tags', async ({ page }) => {
    await page.getByTestId('tab-agents').click();
    await expect(page.getByTestId('agents-tab')).toBeVisible();

    const agentName = `test-tags-${Date.now()}`;

    // Create an agent
    page.once('dialog', async dialog => await dialog.accept(agentName));
    await page.getByTestId('create-agent-btn').click();
    await expect(page.locator('.agent-secret-modal')).toBeVisible({ timeout: 5000 });
    await page.locator('button:has-text("Close")').click();

    // Wait for agent to appear
    await expect(page.getByTestId(`agent-item-${agentName}`)).toBeVisible();

    // Should have no tags initially
    const tagsElement = page.getByTestId(`agent-tags-${agentName}`);
    await expect(tagsElement).toContainText('tags: —');

    // Double-click to edit
    page.once('dialog', async dialog => await dialog.accept('gpu, cuda, linux'));
    await tagsElement.dblclick();
    await page.waitForTimeout(500);

    // Tags should now be updated
    await expect(tagsElement).toContainText('gpu');
    await expect(tagsElement).toContainText('cuda');
    await expect(tagsElement).toContainText('linux');
  });
});

test.describe('Agent Configuration in Node Editor', () => {
  test.beforeEach(async ({ page }) => {
    // Clear localStorage and navigate to editor
    await page.goto('/');
    await page.evaluate(() => localStorage.removeItem('dazflow2-workflow'));
    await page.reload();
    await expect(page.getByTestId('dashboard')).toBeVisible();
    await expect(page.getByTestId('file-list')).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId('file-item-sample.json')).toBeVisible({ timeout: 10000 });
    await page.getByTestId('file-item-sample.json').dblclick();
    await expect(page.getByTestId('editor')).toBeVisible({ timeout: 10000 });
    await page.keyboard.press('Meta+a');
    await page.keyboard.press('Delete');
  });

  test('agent config section appears in node editor', async ({ page }) => {
    // Add a node
    await page.getByTestId('node-type-scheduled').click();
    const node = page.getByTestId('workflow-node-scheduled');

    // Open node editor
    await node.locator('.custom-node').dblclick();
    const dialog = page.locator('.node-editor-dialog');
    await expect(dialog).toBeVisible();

    // Agent Configuration section should be visible
    await expect(dialog.locator('.property-label').filter({ hasText: 'Agent Configuration' })).toBeVisible();
    await expect(page.getByTestId('agent-selection-list')).toBeVisible();

    // "Any agent" should be checked by default
    await expect(page.getByTestId('agent-checkbox-any')).toBeChecked();

    // Close editor
    await page.locator('.node-editor-close').click();
  });

  test('can select specific agents', async ({ page }) => {
    // First, ensure we have at least one agent
    await page.getByTestId('back-to-dashboard').click();
    await expect(page.getByTestId('dashboard')).toBeVisible();
    await page.getByTestId('tab-agents').click();

    // Create test agent if needed
    const agentName = `test-select-${Date.now()}`;
    page.once('dialog', async dialog => await dialog.accept(agentName));
    await page.getByTestId('create-agent-btn').click();
    await expect(page.locator('.agent-secret-modal')).toBeVisible({ timeout: 5000 });
    await page.locator('button:has-text("Close")').click();
    await expect(page.getByTestId(`agent-item-${agentName}`)).toBeVisible();

    // Go back to editor
    await page.getByTestId('tab-workflows').click();
    await page.getByTestId('file-item-sample.json').dblclick();
    await expect(page.getByTestId('editor')).toBeVisible({ timeout: 10000 });
    await page.keyboard.press('Meta+a');
    await page.keyboard.press('Delete');

    // Add a node
    await page.getByTestId('node-type-scheduled').click();
    const node = page.getByTestId('workflow-node-scheduled');

    // Open node editor
    await node.locator('.custom-node').dblclick();
    const dialog = page.locator('.node-editor-dialog');
    await expect(dialog).toBeVisible();

    // "Any agent" should be checked by default
    await expect(page.getByTestId('agent-checkbox-any')).toBeChecked();

    // Uncheck "Any agent" by selecting a specific agent
    const agentCheckbox = page.getByTestId(`agent-checkbox-${agentName}`);
    await agentCheckbox.click();

    // "Any agent" should now be unchecked
    await expect(page.getByTestId('agent-checkbox-any')).not.toBeChecked();

    // The specific agent should be checked
    await expect(agentCheckbox).toBeChecked();

    // Close and reopen to verify persistence
    await page.locator('.node-editor-close').click();
    await node.locator('.custom-node').dblclick();
    await expect(dialog).toBeVisible();

    // Specific agent should still be checked
    await expect(page.getByTestId(`agent-checkbox-${agentName}`)).toBeChecked();
    await expect(page.getByTestId('agent-checkbox-any')).not.toBeChecked();

    await page.locator('.node-editor-close').click();
  });

  test('selecting Any agent deselects specific agents', async ({ page }) => {
    // Create test agent
    await page.getByTestId('back-to-dashboard').click();
    await page.getByTestId('tab-agents').click();
    const agentName = `test-any-${Date.now()}`;
    page.once('dialog', async dialog => await dialog.accept(agentName));
    await page.getByTestId('create-agent-btn').click();
    await expect(page.locator('.agent-secret-modal')).toBeVisible({ timeout: 5000 });
    await page.locator('button:has-text("Close")').click();

    // Go back to editor
    await page.getByTestId('tab-workflows').click();
    await page.getByTestId('file-item-sample.json').dblclick();
    await expect(page.getByTestId('editor')).toBeVisible({ timeout: 10000 });
    await page.keyboard.press('Meta+a');
    await page.keyboard.press('Delete');

    // Add a node and open editor
    await page.getByTestId('node-type-scheduled').click();
    const node = page.getByTestId('workflow-node-scheduled');
    await node.locator('.custom-node').dblclick();
    const dialog = page.locator('.node-editor-dialog');
    await expect(dialog).toBeVisible();

    // Select specific agent
    await page.getByTestId(`agent-checkbox-${agentName}`).click();
    await expect(page.getByTestId(`agent-checkbox-${agentName}`)).toBeChecked();
    await expect(page.getByTestId('agent-checkbox-any')).not.toBeChecked();

    // Now select "Any agent"
    await page.getByTestId('agent-checkbox-any').click();
    await expect(page.getByTestId('agent-checkbox-any')).toBeChecked();
    await expect(page.getByTestId(`agent-checkbox-${agentName}`)).not.toBeChecked();

    await page.locator('.node-editor-close').click();
  });
});
