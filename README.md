![](banner.jpg)

# dazflow2

A visual workflow automation platform that lets you create, manage, and execute automated workflows through a web-based interface.

## Purpose

dazflow2 provides a workflow automation system where you can:

- Design workflows visually using a node-based editor
- Schedule automated tasks with various triggers
- Distribute workflow execution across multiple agents
- Monitor workflow executions and their status

## Installation

### Prerequisites

- Python 3.10+
- Node.js 18+ (for running Playwright tests)

### Setup

1. Clone the repository and install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Install Playwright browsers (for testing):

```bash
npm install
npx playwright install
```

## Usage

### Starting the Server

The server is managed through the `auto` service manager:

```bash
# Start the server
auto start dazflow

# Stop the server
auto stop dazflow

# Restart the server
auto restart dazflow
```

The web interface will be available at `http://localhost:31415`.

### Creating Workflows

1. Open the web interface in your browser
2. Use the visual editor to add nodes (triggers, actions)
3. Connect nodes to define the workflow logic
4. Save and enable the workflow

### Workflow Example

A simple workflow that appends timestamps to a file every 5 minutes:

```json
{
  "nodes": [
    {
      "id": "node-1",
      "typeId": "scheduled",
      "name": "scheduled1",
      "position": { "x": 100, "y": 150 },
      "data": {
        "interval": 5,
        "unit": "minutes"
      }
    },
    {
      "id": "node-2",
      "typeId": "append_to_file",
      "name": "append1",
      "position": { "x": 400, "y": 150 },
      "data": {
        "filepath": "local/work/output/timestamps.txt",
        "content": "{{$.scheduled1.time}}"
      }
    }
  ],
  "connections": [
    {
      "id": "conn-1",
      "sourceNodeId": "node-1",
      "sourceConnectorId": "trigger",
      "targetNodeId": "node-2",
      "targetConnectorId": "data"
    }
  ]
}
```

### Running Tests

```bash
# Run the full test suite and quality gates
./run check

# Run a specific test
./run test tests/e2e/

# Run linter
./run lint

# Run Playwright tests with UI
npm run test:e2e:ui
```

### CLI Commands

The `./run` script provides several commands:

| Command | Description |
|---------|-------------|
| `./run check` | Run full test suite and quality gates |
| `./run test <target>` | Run a specific test target |
| `./run lint` | Run the linter |
| `./run start` | Start the development server (use `auto` for production) |

### Agents

dazflow2 supports distributed execution through agents. Agents can be:

- **Built-in**: Runs on the same machine as the server
- **Remote**: Runs on separate machines and connects to the server

Configure agents through the web interface under the Agents section.