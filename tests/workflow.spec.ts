import { test, expect } from '@playwright/test';

test.describe('Workflow Editor', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
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

  test('workflow state persists across page reload', async ({ page }) => {
    // Clear localStorage first
    await page.evaluate(() => localStorage.removeItem('dazflow2-workflow'));

    // Add nodes
    await page.getByTestId('node-type-rss').click();
    await page.getByTestId('node-type-http').click();

    // Verify nodes exist
    await expect(page.getByTestId('workflow-node-rss')).toHaveCount(1);
    await expect(page.getByTestId('workflow-node-http')).toHaveCount(1);

    // Wait for localStorage to be updated
    await page.waitForTimeout(100);

    // Reload the page
    await page.reload();

    // Verify nodes are restored after reload
    await expect(page.getByTestId('workflow-node-rss')).toHaveCount(1);
    await expect(page.getByTestId('workflow-node-http')).toHaveCount(1);

    // Clean up
    await page.evaluate(() => localStorage.removeItem('dazflow2-workflow'));
  });
});
