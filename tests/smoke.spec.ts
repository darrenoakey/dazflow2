/**
 * Post-deploy smoke test for the real production instance.
 *
 * Run this MANUALLY after deployment to verify the server is working:
 *   npx playwright test tests/smoke.spec.ts --config=playwright.smoke.config.ts
 *
 * This tests against the REAL server on port 31415 (not the isolated test instance).
 */
import { test, expect } from '@playwright/test';

test.describe('Smoke Tests - Production Instance', () => {
  test('server responds and page loads without errors', async ({ page }) => {
    // Collect any console errors
    const consoleErrors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // Navigate to the dashboard
    await page.goto('/');

    // Page should load without network errors
    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 10000 });

    // Title should be correct
    await expect(page.getByTestId('dashboard-title')).toHaveText('dazflow');

    // No console errors (excluding expected ones like favicon 404)
    const criticalErrors = consoleErrors.filter(
      err => !err.includes('favicon') && !err.includes('404')
    );
    expect(criticalErrors).toHaveLength(0);
  });

  test('all main tabs are visible', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 10000 });

    // Verify all tabs exist
    await expect(page.getByTestId('tab-workflows')).toBeVisible();
    await expect(page.getByTestId('tab-executions')).toBeVisible();
    await expect(page.getByTestId('tab-agents')).toBeVisible();
    await expect(page.getByTestId('tab-concurrency')).toBeVisible();
  });

  test('workflows tab loads file list', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 10000 });

    // Workflows tab should be active by default
    await expect(page.getByTestId('tab-workflows')).toHaveClass(/active/);

    // File list should be visible
    await expect(page.getByTestId('file-list')).toBeVisible({ timeout: 10000 });
  });

  test('agents tab loads', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 10000 });

    // Click agents tab
    await page.getByTestId('tab-agents').click();
    await expect(page.getByTestId('tab-agents')).toHaveClass(/active/);

    // Agents tab content should be visible
    await expect(page.getByTestId('agents-tab')).toBeVisible();
    await expect(page.getByTestId('create-agent-btn')).toBeVisible();
  });

  test('executions tab loads', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 10000 });

    // Click executions tab
    await page.getByTestId('tab-executions').click();
    await expect(page.getByTestId('tab-executions')).toHaveClass(/active/);

    // Executions tab content should be visible
    await expect(page.getByTestId('executions-tab')).toBeVisible();
  });

  test('concurrency tab loads', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 10000 });

    // Click concurrency tab
    await page.getByTestId('tab-concurrency').click();
    await expect(page.getByTestId('tab-concurrency')).toHaveClass(/active/);

    // Concurrency tab content should be visible
    await expect(page.getByTestId('concurrency-tab')).toBeVisible();
  });

  test('health endpoint returns ok', async ({ request }) => {
    const response = await request.get('/health');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.status).toBe('ok');
    expect(data.start_time).toBeDefined();
  });

  test('editor shows header with workflow name and tabs', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 10000 });

    // Open sample.json workflow
    await page.getByTestId('file-item-sample.json').dblclick();
    await expect(page.getByTestId('editor')).toBeVisible({ timeout: 10000 });

    // Editor header should be visible
    await expect(page.getByTestId('editor-header')).toBeVisible();
    await expect(page.getByTestId('editor-workflow-name')).toHaveText('sample');

    // Tabs should be visible
    await expect(page.getByTestId('editor-tab-editor')).toBeVisible();
    await expect(page.getByTestId('editor-tab-executions')).toBeVisible();

    // Editor tab should be active by default
    await expect(page.getByTestId('editor-tab-editor')).toHaveClass(/active/);
  });

  test('editor executions tab shows workflow executions', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 10000 });

    // Open sample.json workflow
    await page.getByTestId('file-item-sample.json').dblclick();
    await expect(page.getByTestId('editor')).toBeVisible({ timeout: 10000 });

    // Click Executions tab
    await page.getByTestId('editor-tab-executions').click();
    await expect(page.getByTestId('editor-tab-executions')).toHaveClass(/active/);

    // Workflow executions tab should be visible
    await expect(page.getByTestId('workflow-executions-tab')).toBeVisible();
  });

  test('editor back button returns to dashboard', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 10000 });

    // Open sample.json workflow
    await page.getByTestId('file-item-sample.json').dblclick();
    await expect(page.getByTestId('editor')).toBeVisible({ timeout: 10000 });

    // Click back button
    await page.getByTestId('editor-back-btn').click();

    // Should return to dashboard
    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 10000 });
  });

  test('editor shows history tab', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 10000 });

    // Open sample.json workflow
    await page.getByTestId('file-item-sample.json').dblclick();
    await expect(page.getByTestId('editor')).toBeVisible({ timeout: 10000 });

    // History tab should be visible
    await expect(page.getByTestId('editor-tab-history')).toBeVisible();
  });

  test('history tab shows workflow history', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 10000 });

    // Open sample.json workflow
    await page.getByTestId('file-item-sample.json').dblclick();
    await expect(page.getByTestId('editor')).toBeVisible({ timeout: 10000 });

    // Click History tab
    await page.getByTestId('editor-tab-history').click();
    await expect(page.getByTestId('editor-tab-history')).toHaveClass(/active/);

    // History tab content should be visible
    await expect(page.getByTestId('workflow-history-tab')).toBeVisible();
  });
});
