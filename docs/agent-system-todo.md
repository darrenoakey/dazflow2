# Distributed Agent System - Implementation TODO

## PR 1: Test Infrastructure + Agent Data Model

### 1.1 Server Configuration
- [ ] Create `src/config.py` with ServerConfig dataclass
- [ ] Add port, data_dir, workflows_dir, agents_file properties
- [ ] Update `src/api.py` to use ServerConfig
- [ ] Update `src/executor.py` to use ServerConfig
- [ ] Add CLI arguments for --port and --data-dir
- [ ] Tests: Server starts on custom port with custom data dir

### 1.2 Agent Data Model
- [ ] Create `src/agents.py` with Agent dataclass
- [ ] Create AgentRegistry class with JSON file storage
- [ ] Implement list_agents(), get_agent(), create_agent(), update_agent()
- [ ] Implement _load() (read once) and _save() (write on change)
- [ ] Generate secure secret on agent creation
- [ ] Tests: CRUD operations on agents, persistence to JSON

### 1.3 Agent API Endpoints
- [ ] GET /api/agents - List all agents
- [ ] POST /api/agents - Create agent (name in body)
- [ ] GET /api/agents/{name} - Get single agent
- [ ] PUT /api/agents/{name} - Update agent (enable/disable, priority, tags)
- [ ] Tests: API endpoints return correct data

### 1.4 Agents Tab UI
- [ ] Add "Agents" tab to main navigation
- [ ] Display list of agents with status, priority, tags, task count
- [ ] Show online/offline indicator
- [ ] Show IP address and version
- [ ] Show "current task" if agent is working
- [ ] Tests: Playwright tests for agents tab display

---

## PR 2: WebSocket Connection + Remote Agent

### 2.1 WebSocket Endpoint
- [ ] Create `src/agent_ws.py` with WebSocket handler
- [ ] Handle connection with agent name and secret validation
- [ ] Track connected agents in registry
- [ ] Handle disconnect (mark offline, update last_seen)
- [ ] Tests: WebSocket accepts valid connections, rejects invalid

### 2.2 Heartbeat Mechanism
- [ ] Agent sends heartbeat every 30 seconds
- [ ] Server responds with heartbeat_ack
- [ ] Server marks agent offline if no heartbeat for 60 seconds
- [ ] Tests: Agent stays online with heartbeats, goes offline without

### 2.3 Agent Program
- [ ] Create `agent/agent.py` - single file agent
- [ ] Parse CLI arguments (--server, --name, --secret)
- [ ] Connect to server WebSocket
- [ ] Send connect message with name, secret, version
- [ ] Handle connect_ok / connect_rejected
- [ ] Run heartbeat loop
- [ ] Reconnect on disconnect with exponential backoff
- [ ] Tests: Spawn real agent process, verify connects

### 2.4 Integration Tests
- [ ] Start test server on port 5099
- [ ] Spawn real agent process
- [ ] Verify agent appears online in API
- [ ] Kill agent process
- [ ] Verify agent goes offline after timeout
- [ ] Restart agent, verify reconnects

---

## PR 3: Built-in Agent

### 3.1 Built-in Agent Initialization
- [ ] Auto-create "built-in" agent on first startup if not exists
- [ ] Start built-in agent in background thread/task
- [ ] Built-in agent uses exact same code as remote agent
- [ ] Connects via internal WebSocket to self
- [ ] Tests: Server starts, built-in agent appears online

### 3.2 Enable/Disable Built-in Agent
- [ ] Can disable built-in agent from UI
- [ ] Disabled agent disconnects
- [ ] Re-enable causes reconnect
- [ ] Tests: Disable/enable built-in agent via API

---

## PR 4: Task Queue + Distribution

### 4.1 Task Queue Implementation
- [ ] Create `src/task_queue.py` with Task dataclass
- [ ] Implement TaskQueue class with pending and in_progress lists
- [ ] enqueue(), get_available_task(), claim_task(), complete_task(), fail_task()
- [ ] requeue_agent_tasks() for disconnect handling
- [ ] Tests: Queue operations work correctly

### 4.2 Executor Integration
- [ ] Modify executor to enqueue task instead of executing directly
- [ ] Task contains full execution snapshot
- [ ] After task complete, continue to next node
- [ ] Tests: Workflow execution goes through queue

### 4.3 Agent Task Handling
- [ ] Server sends task_available to eligible agents
- [ ] Agent sends task_claim
- [ ] Server responds task_claimed_ok or task_claimed_fail
- [ ] Agent executes node, sends task_complete or task_failed
- [ ] Server updates execution, queues next node
- [ ] Tests: Agent receives and executes tasks

### 4.4 Disconnect Handling
- [ ] When agent disconnects, requeue its tasks
- [ ] Agent kills in-progress work on disconnect
- [ ] Tests: Kill agent mid-task, verify task requeued and completes

---

## PR 5: Agent Selection Per Node

### 5.1 Node Agent Configuration Schema
- [ ] Add agentConfig to node schema (agents array, requiredTags array)
- [ ] Store in workflow JSON
- [ ] Default is empty (any agent)
- [ ] Tests: Agent config saved and loaded correctly

### 5.2 Matching Logic
- [ ] Update can_agent_run_task() to check agents list
- [ ] If agents specified, agent.name must be in list (OR logic)
- [ ] Tests: Task only runs on specified agents

### 5.3 Agent Selection UI
- [ ] Add agent config section to node editor
- [ ] Multi-select dropdown with "Any agent" and agent names
- [ ] "Any agent" is mutually exclusive with specific agents
- [ ] Tests: Playwright tests for agent selection UI

---

## PR 6: Tags

### 6.1 Tags Data Model
- [ ] Create tags.json storage
- [ ] Add to AgentRegistry or separate TagsRegistry
- [ ] CRUD operations for tags
- [ ] Tests: Tag CRUD operations

### 6.2 Tags API
- [ ] GET /api/tags - List all tags
- [ ] POST /api/tags - Create tag
- [ ] DELETE /api/tags/{name} - Delete tag
- [ ] PUT /api/agents/{name}/tags - Set agent tags
- [ ] Tests: Tag API endpoints

### 6.3 Tags UI
- [ ] Display tags list in Agents tab
- [ ] Create new tag button
- [ ] Double-click tag to assign to selected agent
- [ ] Show agent tags in agent list
- [ ] Tests: Playwright tests for tag management

### 6.4 Required Tags Matching
- [ ] Add requiredTags to node agentConfig
- [ ] Update matching: agent must have ALL required tags (AND logic)
- [ ] UI: Checkbox list of tags in node editor
- [ ] Tests: Task only runs on agents with required tags

---

## PR 7: Credentials Distribution

### 7.1 Agent Credential Selection
- [ ] Add agents array to credential storage
- [ ] UI: Checkbox list of agents when saving credential
- [ ] Tests: Credential saved with agent list

### 7.2 Credential Push Protocol
- [ ] Server sends credential_push message to agent
- [ ] Agent stores in local keyring (dazflow-agent-{name} service)
- [ ] Agent sends credential_ack
- [ ] Tests: Credential pushed and stored on agent

### 7.3 Credential-based Matching
- [ ] Agent reports credential names on connect
- [ ] Matching checks required credential
- [ ] Tests: Task only runs on agents with credential

### 7.4 Auto-push on Update
- [ ] When credential updated, push to all agents that have it
- [ ] Tests: Update credential, verify pushed to agents

---

## PR 8: Concurrency Groups

### 8.1 Concurrency Groups Data Model
- [ ] Create concurrency_groups.json storage
- [ ] ConcurrencyGroup dataclass (name, limit)
- [ ] CRUD operations
- [ ] Tests: Concurrency group CRUD

### 8.2 Concurrency Groups API
- [ ] GET /api/concurrency-groups
- [ ] POST /api/concurrency-groups
- [ ] PUT /api/concurrency-groups/{name}
- [ ] DELETE /api/concurrency-groups/{name}
- [ ] Tests: API endpoints

### 8.3 Concurrency Tab UI
- [ ] Add "Concurrency" tab to main navigation
- [ ] List groups with name, limit, current active count
- [ ] Create/edit/delete groups
- [ ] Tests: Playwright tests for concurrency tab

### 8.4 Concurrency Tracking
- [ ] ConcurrencyTracker class (in-memory counts)
- [ ] Increment on task start, decrement on complete/fail/timeout
- [ ] Rebuild counts on server restart
- [ ] Tests: Counts maintained correctly

### 8.5 Concurrency Limit Enforcement
- [ ] Add concurrencyGroup to node agentConfig
- [ ] Matching checks concurrency limit
- [ ] UI: Dropdown to select concurrency group in node editor
- [ ] Tests: Concurrency limit enforced

---

## PR 9: Agent Install + Self-Upgrade

### 9.1 Install Script Generator
- [ ] API endpoint to generate install script
- [ ] Script checks Python, creates directory, downloads agent
- [ ] Script stores secret securely
- [ ] Platform-specific scripts (linux, macos, windows)
- [ ] Tests: Generated script works

### 9.2 Agent Updater Shim
- [ ] Create `agent/agent_updater.py` - rarely changes
- [ ] Starts agent.py as subprocess
- [ ] If exit code 42, download new agent.py and restart
- [ ] Tests: Updater restarts agent after upgrade

### 9.3 Version Checking
- [ ] Server compares agent version on connect
- [ ] Send upgrade_required if out of date
- [ ] Agent downloads new version, exits with code 42
- [ ] Tests: Agent upgrades when server version newer

---

## PR 10: Log Streaming

### 10.1 Log Buffer on Agent
- [ ] LogBuffer class with async shipping
- [ ] Buffer logs locally
- [ ] Ship batches every 500ms in background thread
- [ ] Tests: Logs buffered and shipped

### 10.2 Log Protocol
- [ ] Agent sends logs message with entries
- [ ] Server appends to execution log
- [ ] Tests: Logs appear on server

### 10.3 Offline Buffering
- [ ] If disconnected, keep buffering locally
- [ ] Ship buffered logs on reconnect
- [ ] Tests: Disconnect, buffer, reconnect, logs arrive

---

## Current Status

**Current PR:** PR 1 - Test Infrastructure + Agent Data Model
**Current Step:** 1.1 - Server Configuration
