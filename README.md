![](banner.jpg)

# dazflow2

A visual workflow automation platform where you design automated tasks by connecting nodes in a web-based editor — like building with blocks, but for automating your digital life.

## What is dazflow2?

dazflow2 lets you create automated workflows without writing code. Want to run a task every 5 minutes? Process incoming emails? Send notifications to Discord? Just drag nodes onto a canvas, connect them together, and let dazflow2 handle the rest.

Think of it as your personal automation hub — workflows run in the background, triggered by schedules, events, or other workflows, so you can focus on more interesting things.

## Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** (for running tests)

### Installation

1. Clone the repository and install dependencies:

```bash
pip install -r requirements.txt
```

2. If you plan to run tests, install Playwright:

```bash
npm install
npx playwright install
```

### Starting the Server

dazflow2 uses the `auto` service manager to keep things running smoothly:

```bash
auto start dazflow    # Start the server
auto stop dazflow     # Stop the server
auto restart dazflow  # Restart after changes
```

Once started, open your browser and visit **http://localhost:31415** — that's your workflow dashboard.

## Features

### Visual Workflow Editor

The heart of dazflow2 is its node-based editor. You build workflows by:

1. **Adding nodes** from the sidebar — triggers, transforms, actions, and more
2. **Connecting them** by dragging wires between nodes
3. **Configuring each node** with its own settings
4. **Saving** — changes autosave after 1 second of inactivity

The sidebar organizes nodes into collapsible categories: Input, Transform, Logic, Action, Pipeline, Output, AI, Discord, System, and Database.

### Node Types

Here's a taste of what you can do:

| Category | Examples |
|----------|---------|
| **Input** | Scheduled triggers, email triggers, webhooks |
| **Transform** | Set values, transform data, extract fields |
| **Logic** | Conditionals, branching, filtering |
| **Action** | Run shell commands, append to files, call APIs |
| **Pipeline** | State-based data processing with automatic change detection |
| **AI** | Claude-powered nodes for text analysis and generation |
| **Discord** | Send messages to Discord channels |
| **Database** | Read and write data |

### Scheduled Workflows

Set up tasks to run on a schedule — every few minutes, hourly, daily, or with custom cron expressions. Great for:

- Periodic data collection
- Regular file cleanup
- Scheduled notifications
- Recurring reports

### Pipeline Workflows

For more advanced use cases, pipeline nodes let you build state-aware data processing chains. They automatically detect when something has changed and only reprocess what's needed — perfect for things like content feeds, data syncing, or multi-step processing pipelines.

### Workflow Version History

Every time you save a workflow, dazflow2 keeps a version in its history. You can:

- **Browse past versions** in the History tab
- **Compare changes** between versions
- **Restore any previous version** with one click

Never worry about losing your work or breaking something — you can always go back.

### AI Assistant

dazflow2 includes a built-in AI assistant that understands your workflows. Use it to:

- Create new workflows from natural language descriptions
- Modify existing workflows through conversation
- Manage folders, tags, and organization
- Get help with workflow design

Access it through the chat panel in the dashboard or editor, or from the command line:

```bash
./run ai list                              # List all workflows
./run ai enable my-workflow                # Enable a workflow
./run ai create a workflow that does x y z # Describe what you want
```

### Distributed Agents

Need more power? dazflow2 supports multiple execution agents:

- **Built-in agent** — runs on the same machine as the server
- **Remote agents** — run on other machines and connect back to the server

This lets you spread work across multiple machines or dedicate specific agents to specific tasks.

### Workflow Settings

Each workflow can have its own settings:

- **Data Directory** — restrict file operations to a specific folder for safety
- **Tags** — organize workflows with labels
- **Concurrency Groups** — prevent workflows from stepping on each other

### File and Directory Browsing

Nodes that work with files (like "append to file" or "run command") include a built-in file browser. Toggle between browsing mode and typing a path directly, with real-time validation to catch typos.

## Tips and Tricks

- **Autosave is your friend** — changes save automatically after 1 second, and the status indicator in the header shows you the current state (Saved, Modified, Saving)

- **Use the keyboard** — the editor supports standard shortcuts for common operations

- **Check the Executions tab** — every time a workflow runs, the results appear in the Executions tab so you can see exactly what happened

- **Pipeline nodes stand out** — they're colored teal instead of purple, making them easy to spot in complex workflows

- **Collapse sidebar categories** — click category headers to hide node types you don't need right now

- **Test your workflows** — create test workflows (name them `*_test.json` or `test_*.json`) and run them with:
  ```bash
  ./run workflow-test
  ```

- **Cross-workflow communication** — pipeline workflows can trigger each other through shared state patterns. Workflow A writes data, Workflow B automatically picks it up

- **AI commit messages** — when you save a workflow, the system automatically generates a descriptive commit message for the version history

## Running Tests

```bash
./run check              # Full test suite and quality gates
./run test tests/e2e/    # Run end-to-end tests
./run lint               # Check code style
./run workflow-test      # Run workflow-based tests
```

## CLI Reference

| Command | What it does |
|---------|-------------|
| `./run start` | Start the development server |
| `./run check` | Run all tests and quality checks |
| `./run test <target>` | Run a specific test |
| `./run lint` | Run the linter |
| `./run ai <command>` | Talk to the AI assistant |
| `./run workflow-test` | Run workflow tests |

## License

Private project.